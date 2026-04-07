import json
import logging
import asyncio
from openai import AsyncOpenAI
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
"""

async def synthesize_answers(questions: list[SecurityQuestion], telemetry: dict[int, list[TelemetryEvidence]], citations: dict[int, list[PolicyCitation]], settings: ShieldWallSettings) -> list[DraftAnswer]:
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    
    async def _synth(q: SecurityQuestion):
        t_ev = telemetry.get(q.id, [])
        p_cit = citations.get(q.id, [])
        
        context = {
            "question": q.normalized_query,
            "category": q.category,
            "telemetry_evidence": [e.model_dump() for e in t_ev],
            "policy_citations": [c.model_dump() for c in p_cit],
        }
        
        try:
            completion = await openai_client.chat.completions.parse(
                model=settings.gpt4o_model,
                messages=[
                    {"role": "system", "content": SYNTHESIS_SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(context)},
                ],
                response_format=DraftAnswer,
            )
            ans = completion.choices[0].message.parsed
            ans.question_id = q.id
            ans.telemetry_evidence = t_ev
            ans.policy_citations = p_cit
            return ans
        except Exception as e:
            logger.error(f"Error synthesizing Q{q.id}: {e}")
            return DraftAnswer(
                question_id=q.id,
                answer_text="Error generating answer.",
                confidence="low",
                evidence_sources=["none"],
                drift_detected=False,
                needs_human_review=True
            )

    tasks = [_synth(q) for q in questions]
    answers = await asyncio.gather(*tasks)
    return list(answers)
