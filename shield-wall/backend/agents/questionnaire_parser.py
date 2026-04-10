import json
import logging
import asyncio
from google import genai
from google.genai import types
from openai import OpenAI
from backend.models.schemas import ParsedQuestionnaire, SecurityQuestion
from backend.config import ShieldWallSettings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an information security analyst classifying vendor security questionnaire questions.

CRITICAL: You will receive exactly N numbered questions. You MUST return EXACTLY N classified items in the same order. Do NOT skip, merge, or omit any question.

For each question:
1. Assign a category from: access_control, encryption, network_security, incident_response, data_classification, business_continuity, vendor_management, physical_security, compliance, logging_monitoring, change_management, other.
2. Rewrite it as a clear, unambiguous normalized query.
3. Determine if answering requires live infrastructure telemetry (e.g., "Is MFA enforced?" -> true).
4. Determine if answering requires policy document citation (e.g., "What is your IR plan?" -> true).

Output a JSON object with a "questions" key containing an array of EXACTLY N objects (one per input question, same order), each with keys:
idx (the 0-based index matching input), category, original_text, normalized_query, requires_telemetry, requires_policy.
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


def _build_numbered_prompt(chunk: list[dict]) -> str:
    """Build a numbered list so Gemini knows exactly how many to return."""
    lines = [f"[{i}] {q.get('text', '')}" for i, q in enumerate(chunk)]
    return f"Classify ALL {len(chunk)} questions below. Return EXACTLY {len(chunk)} items.\n\n" + "\n".join(lines)


def _reconcile(gemini_result: list[dict], chunk: list[dict]) -> list[dict]:
    """Ensure we have exactly len(chunk) results by filling gaps with passthrough."""
    if len(gemini_result) >= len(chunk):
        return gemini_result[:len(chunk)]

    # Build a lookup by idx if Gemini returned idx fields
    by_idx = {}
    for item in gemini_result:
        idx = item.get("idx")
        if idx is not None and isinstance(idx, int):
            by_idx[idx] = item

    result = []
    for i, rq in enumerate(chunk):
        if i in by_idx:
            result.append(by_idx[i])
        elif i < len(gemini_result) and i not in by_idx:
            # No idx field — assume positional order
            result.append(gemini_result[i] if i < len(gemini_result) else None)
        else:
            result.append(None)

    # Fill any Nones with passthrough
    for i, item in enumerate(result):
        if item is None:
            result[i] = {
                "category": "other",
                "original_text": chunk[i].get("text", ""),
                "normalized_query": chunk[i].get("text", ""),
                "requires_telemetry": True,
                "requires_policy": True,
            }

    return result


def _try_gemini(chunk: list[dict], settings: ShieldWallSettings) -> list[dict] | None:
    """Attempt classification via Gemini with reconciliation."""
    client = genai.Client(api_key=settings.gemini_api_key)
    prompt = _build_numbered_prompt(chunk)

    for attempt in range(2):
        try:
            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=f"{SYSTEM_PROMPT}\n\n{prompt}",
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
                reconciled = _reconcile(questions, chunk)
                logger.info(f"Gemini returned {len(questions)}/{len(chunk)} — reconciled to {len(reconciled)}")
                return reconciled
        except Exception as e:
            logger.warning(f"Gemini attempt {attempt + 1} failed: {e}")
    return None


def _fallback_gpt4o(chunk: list[dict], settings: ShieldWallSettings) -> list[dict] | None:
    """Fallback to GPT-4o if Gemini fails."""
    logger.info("Falling back to GPT-4o for questionnaire parsing")
    client = OpenAI(api_key=settings.openai_api_key)
    prompt = _build_numbered_prompt(chunk)
    try:
        completion = client.chat.completions.create(
            model=settings.gpt4o_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        parsed = json.loads(completion.choices[0].message.content)
        questions = parsed.get("questions", parsed) if isinstance(parsed, dict) else parsed
        if isinstance(questions, list):
            return _reconcile(questions, chunk)
    except Exception as e:
        logger.error(f"GPT-4o fallback also failed: {e}")
    return None


async def parse_questionnaire(
    raw_questions: list[dict],
    file_name: str,
    file_ext: str,
    settings: ShieldWallSettings,
) -> ParsedQuestionnaire:
    batch = raw_questions[: settings.max_questions]

    # Process in chunks of 30 concurrently
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
