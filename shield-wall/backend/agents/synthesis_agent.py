import json
import logging
import asyncio
from google import genai
from google.genai import types
from backend.models.schemas import SecurityQuestion, TelemetryEvidence, PolicyCitation, DraftAnswer
from backend.config import ShieldWallSettings

logger = logging.getLogger(__name__)

SYNTHESIS_SYSTEM_PROMPT = """
You are a senior information security analyst drafting responses to a vendor
security questionnaire. You have access to:
1. Live infrastructure telemetry evidence (retrieved moments ago)
2. Internal compliance policy citations (from our SOC 2 Type 2 report and security policies)

RULES:
- Ground every claim in provided evidence. Quote policy sections verbatim where possible.
- Reference specific telemetry findings with timestamps.
- If telemetry is unavailable, answer from policy only and set confidence to "medium".
- If neither telemetry nor policy covers the question, set confidence to "low" and needs_human_review to true.
- NEVER fabricate evidence, configurations, or policy language.
- Write in professional, concise enterprise security prose.
- Use present tense ("Tracelight enforces..." not "Tracelight will enforce...").
- If the telemetry evidence explicitly contradicts the policy citation, set drift_detected to true and explain the contradiction in drift_detail.

You MUST respond with a JSON object with these exact keys:
{
  "question_id": <int>,
  "answer_text": "<string>",
  "confidence": "high" | "medium" | "low",
  "evidence_sources": ["telemetry" | "policy" | "both" | "none"],
  "drift_detected": true | false,
  "drift_detail": "<string or null>",
  "needs_human_review": true | false
}
"""


async def synthesize_answers(questions: list[SecurityQuestion], telemetry: dict[int, list[TelemetryEvidence]], citations: dict[int, list[PolicyCitation]], settings: ShieldWallSettings) -> list[DraftAnswer]:
    client = genai.Client(api_key=settings.gemini_api_key)
    semaphore = asyncio.Semaphore(10)

    async def _synth(q: SecurityQuestion):
        t_ev = telemetry.get(q.id, [])
        p_cit = citations.get(q.id, [])

        context = {
            "question_id": q.id,
            "question": q.normalized_query,
            "category": q.category,
            "telemetry_evidence": [e.model_dump() for e in t_ev],
            "policy_citations": [c.model_dump() for c in p_cit],
        }

        try:
            async with semaphore:
                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model=settings.gemini_model,
                    contents=f"{SYNTHESIS_SYSTEM_PROMPT}\n\nContext:\n{json.dumps(context)}",
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        response_mime_type="application/json",
                    ),
                )

            raw_text = response.text
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:-3]
            parsed = json.loads(raw_text)
            parsed["question_id"] = q.id

            # Ensure valid enum values
            if parsed.get("confidence") not in ("high", "medium", "low"):
                parsed["confidence"] = "low"
            if not isinstance(parsed.get("evidence_sources"), list):
                parsed["evidence_sources"] = ["none"]

            ans = DraftAnswer(
                question_id=q.id,
                answer_text=parsed.get("answer_text", "No answer generated."),
                confidence=parsed["confidence"],
                evidence_sources=parsed["evidence_sources"],
                drift_detected=parsed.get("drift_detected", False),
                drift_detail=parsed.get("drift_detail"),
                needs_human_review=parsed.get("needs_human_review", True),
                telemetry_evidence=t_ev,
                policy_citations=p_cit,
            )
            return ans
        except Exception as e:
            logger.error(f"Error synthesizing Q{q.id}: {e}")
            return DraftAnswer(
                question_id=q.id,
                answer_text="Error generating answer.",
                confidence="low",
                evidence_sources=["none"],
                drift_detected=False,
                needs_human_review=True,
            )

    tasks = [_synth(q) for q in questions]
    answers = await asyncio.gather(*tasks)
    return list(answers)
