import json
import logging
from google import genai
from google.genai import types
from openai import OpenAI
from backend.models.schemas import ParsedQuestionnaire, SecurityQuestion
from backend.config import ShieldWallSettings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are an information security analyst classifying vendor security questionnaire questions.

For each question:
1. Assign a category from: access_control, encryption, network_security, incident_response, data_classification, business_continuity, vendor_management, physical_security, compliance, logging_monitoring, change_management, other.
2. Rewrite it as a clear, unambiguous normalized query.
3. Determine if answering requires live infrastructure telemetry (e.g., "Is MFA enforced?" -> true).
4. Determine if answering requires policy document citation (e.g., "What is your IR plan?" -> true).

Output a JSON object with a "questions" key containing an array of objects, each with keys:
category, original_text, normalized_query, requires_telemetry, requires_policy.
"""


def _enrich_questions(structured_questions: list[dict], batch: list[dict]) -> list[dict]:
    """Assign IDs and map source metadata from the original batch."""
    for i, sq in enumerate(structured_questions):
        sq["id"] = i + 1
        if i < len(batch):
            sq["source_row"] = batch[i].get("row")
            sq["source_sheet"] = batch[i].get("sheet")
            sq["original_text"] = batch[i].get("text", sq.get("original_text", ""))
    return structured_questions


def _try_gemini(batch: list[dict], settings: ShieldWallSettings) -> list[dict] | None:
    """Attempt classification via Gemini. Retries up to 2 times."""
    client = genai.Client(api_key=settings.gemini_api_key)
    for attempt in range(2):
        try:
            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=f"{SYSTEM_PROMPT}\n\nQuestions:\n{json.dumps(batch)}",
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    top_p=0.9,
                    response_mime_type="application/json",
                ),
            )
            raw_text = response.text
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:-3]
            parsed = json.loads(raw_text)
            questions = parsed.get("questions", parsed) if isinstance(parsed, dict) else parsed
            if isinstance(questions, list) and len(questions) > 0:
                return questions
        except Exception as e:
            logger.warning(f"Gemini attempt {attempt + 1} failed: {e}")
    return None


def _fallback_gpt4o(batch: list[dict], settings: ShieldWallSettings) -> list[dict] | None:
    """Fallback to GPT-4o if Gemini fails."""
    logger.info("Falling back to GPT-4o for questionnaire parsing")
    client = OpenAI(api_key=settings.openai_api_key)
    try:
        completion = client.chat.completions.create(
            model=settings.gpt4o_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(batch)},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        parsed = json.loads(completion.choices[0].message.content)
        questions = parsed.get("questions", parsed) if isinstance(parsed, dict) else parsed
        if isinstance(questions, list):
            return questions
    except Exception as e:
        logger.error(f"GPT-4o fallback also failed: {e}")
    return None


async def parse_questionnaire(
    raw_questions: list[dict],
    file_name: str,
    file_ext: str,
    settings: ShieldWallSettings,
) -> ParsedQuestionnaire:
    import asyncio
    batch = raw_questions[: settings.max_questions]

    # Process in chunks of 30 concurrently to avoid Gemini truncating output
    CHUNK_SIZE = 30
    chunks = [batch[i:i + CHUNK_SIZE] for i in range(0, len(batch), CHUNK_SIZE)]

    async def _classify_chunk(chunk):
        result = await asyncio.to_thread(_try_gemini, chunk, settings)
        if result is None:
            result = await asyncio.to_thread(_fallback_gpt4o, chunk, settings)
        if result is None:
            result = [
                {
                    "category": "other",
                    "original_text": rq.get("text", ""),
                    "normalized_query": rq.get("text", ""),
                    "requires_telemetry": True,
                    "requires_policy": True,
                }
                for rq in chunk
            ]
        return result

    chunk_results = await asyncio.gather(*[_classify_chunk(c) for c in chunks])
    structured_questions = []
    for cr in chunk_results:
        structured_questions.extend(cr)

    structured_questions = _enrich_questions(structured_questions, batch)
    final_questions = [SecurityQuestion(**sq) for sq in structured_questions]

    return ParsedQuestionnaire(
        source_file=file_name,
        source_format=file_ext,
        total_questions=len(final_questions),
        questions=final_questions,
        metadata={},
    )
