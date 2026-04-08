import json
import logging
import asyncio
import functools
from google import genai
from google.genai import types
from openai import OpenAI
from backend.models.schemas import TemplateSchema
from backend.config import Settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are a financial model analyst specializing in LBO, DCF, and 3-statement models.

Given the following Excel template structure (JSON), perform these tasks:
1. Classify each column header by its financial data type: currency_USD, currency_EUR, currency_GBP, percentage, ratio, integer, date, or text.
2. Identify the temporal range (e.g., FY2020-FY2025) for each column with time-series data.
3. Detect inter-sheet dependencies from the formula references provided.
4. Classify the overall model type as LBO, DCF, 3-statement, or unknown.
5. Infer the likely industry sector from any contextual clues in the headers or sheet names. If no clues, default to "General Corporate".
6. Set realistic constraints for each input column:
    - Revenue: growth_rate_range of (-0.10, 0.30), must_be_positive=True
    - COGS/OpEx: must_be_positive=True
    - Margins: min 0.0, max 1.0
    - Debt tranches: must_be_positive=True
    - Interest rates: min 0.0, max 0.25

Output ONLY valid JSON conforming exactly to the required schema.
"""


def _enrich_schema_with_cell_refs(schema: TemplateSchema, parsed_template: dict) -> TemplateSchema:
    """Map cell references and periods from the original parsed template onto the schema."""
    for sheet in schema.sheets:
        pt_sheet = next((s for s in parsed_template["sheets"] if s["name"] == sheet.name), None)
        if pt_sheet:
            for col in sheet.columns:
                refs = []
                periods = []
                for ic in pt_sheet["input_cells"]:
                    if ic["column_header"] == col.header:
                        refs.append(ic["ref"])
                        if "period" in ic and ic["period"]:
                            periods.append(ic["period"])
                col.cell_references = refs
                col.periods = list(dict.fromkeys(periods))
    return schema


async def _try_gemini(parsed_template: dict, settings: Settings) -> TemplateSchema:
    """Attempt schema extraction via Gemini 2.0 Flash. Single attempt with 30s timeout."""
    client = genai.Client(api_key=settings.gemini_api_key)
    schema_json = TemplateSchema.model_json_schema()
    contents = f"{SYSTEM_PROMPT}\n\nRequired Schema:\n{json.dumps(schema_json)}\n\nTemplate Structure:\n{json.dumps(parsed_template)}"

    last_error = None
    for attempt in range(1):
        try:
            response = await asyncio.to_thread(
                functools.partial(
                    client.models.generate_content,
                    model=settings.gemini_model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        temperature=1.0,
                        max_output_tokens=65536,
                        thinking_config=types.ThinkingConfig(thinking_budget=1024),
                        response_mime_type="application/json",
                    ),
                )
            )
            raw_text = response.text
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:-3]
            parsed = json.loads(raw_text)
            return TemplateSchema.model_validate(parsed)
        except Exception as e:
            last_error = e
            logger.warning(f"Gemini attempt {attempt + 1} failed: {e}")
    raise last_error


async def _fallback_gpt4o(parsed_template: dict, settings: Settings) -> TemplateSchema:
    """Fallback to GPT-4o Structured Outputs if Gemini fails."""
    logger.info("Falling back to GPT-4o for schema extraction")
    client = OpenAI(api_key=settings.openai_api_key)
    schema_json = TemplateSchema.model_json_schema()
    completion = await asyncio.to_thread(
        functools.partial(
            client.beta.chat.completions.parse,
            model=settings.gpt4o_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Required Schema:\n{json.dumps(schema_json)}\n\nTemplate Structure:\n{json.dumps(parsed_template)}"},
            ],
            response_format=TemplateSchema,
        )
    )
    result = completion.choices[0].message.parsed
    if result is None:
        raise ValueError("GPT-4o returned no parsed result for schema extraction")
    return result


async def extract_schema(parsed_template: dict, settings: Settings, on_progress=None) -> TemplateSchema:
    async def _report(msg):
        if on_progress:
            await on_progress(msg)

    await _report("Attempting Gemini 3 Flash...")
    try:
        schema = await asyncio.wait_for(_try_gemini(parsed_template, settings), timeout=45)
        await _report("Gemini schema extraction succeeded")
    except (asyncio.TimeoutError, Exception) as e:
        reason = "timed out" if isinstance(e, asyncio.TimeoutError) else str(e)
        logger.warning(f"Gemini failed, falling back to GPT-4o: {reason}")
        await _report(f"Gemini failed ({reason}), falling back to GPT-4o...")
        schema = await _fallback_gpt4o(parsed_template, settings)
        await _report("GPT-4o schema extraction succeeded")

    return _enrich_schema_with_cell_refs(schema, parsed_template)
