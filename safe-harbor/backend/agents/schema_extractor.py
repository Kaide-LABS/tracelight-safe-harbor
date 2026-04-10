import json
import time
import logging
import asyncio
import functools
from google import genai
from google.genai import types
from google.genai.errors import ClientError
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


CLASSIFY_PROMPT = """You are a financial model analyst. Given the sheet names and column headers from an Excel template, classify:
1. model_type: "LBO", "DCF", "3-statement", or "unknown"
2. industry: infer from headers or default to "General Corporate"
3. currency: infer from headers or default to "USD"
4. inter_sheet_refs: detect cross-sheet dependencies from formula references

Return ONLY valid JSON:
{"model_type": "...", "industry": "...", "currency": "...", "inter_sheet_refs": [{"source_sheet": "...", "source_column": "...", "target_sheet": "...", "target_column": "...", "relationship": "equals|feeds_into|delta"}, ...]}
"""

SHEET_PROMPT = """You are a financial model analyst. Classify EVERY column in this single sheet.

For each column header, determine:
- data_type: currency_USD, currency_EUR, currency_GBP, percentage, ratio, integer, date, or text
- temporal_range: e.g. "FY2020-FY2025" if time-series
- is_input: from the input_cells data provided
- constraints: realistic financial constraints (revenue: growth_rate_range [-0.1, 0.3], must_be_positive=true; margins: min 0.0, max 1.0; rates: min 0.0, max 0.25; etc.)

Return ONLY a JSON array of column objects:
[{"header": "...", "data_type": "...", "temporal_range": "..." or null, "periods": [], "is_input": true/false, "cell_references": [], "sheet_name": "...", "constraints": {"min_value": null, "max_value": null, "growth_rate_range": null, "must_be_positive": false, "must_be_negative": false, "sum_equals": null}}]
"""


async def _gemini_call(client, model: str, prompt: str) -> dict | list:
    """Single Gemini call with JSON output. Retries up to 3 times on 429 RESOURCE_EXHAUSTED."""
    max_retries = 3
    backoff_delays = [2, 4, 8]

    for attempt in range(max_retries + 1):
        try:
            response = await asyncio.to_thread(
                functools.partial(
                    client.models.generate_content,
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=1.0,
                        max_output_tokens=16384,
                        thinking_config=types.ThinkingConfig(thinking_budget=1024),
                        response_mime_type="application/json",
                    ),
                )
            )
            raw_text = response.text
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            return json.loads(raw_text)
        except ClientError as e:
            if e.code == 429 and attempt < max_retries:
                delay = backoff_delays[attempt]
                logger.warning(f"[SCHEMA] 429 RESOURCE_EXHAUSTED — retry {attempt + 1}/{max_retries} in {delay}s")
                await asyncio.to_thread(time.sleep, delay)
            else:
                raise


async def _try_gemini(parsed_template: dict, settings: Settings, on_progress=None) -> TemplateSchema:
    """Chunked schema extraction via Gemini 3 Flash — classify first, then each sheet."""
    client = genai.Client(api_key=settings.gemini_api_key)
    model = settings.gemini_fast_model

    # Step 1: Classify model type, industry, currency, inter-sheet refs
    sheet_summary = [{"name": s["name"], "headers": [ic["column_header"] for ic in s["input_cells"]], "formula_refs": s.get("formula_refs", [])} for s in parsed_template["sheets"]]
    classify_prompt = f"{CLASSIFY_PROMPT}\n\nSheets:\n{json.dumps(sheet_summary)}"

    if on_progress:
        await on_progress("[SCHEMA] Classifying model type...")
    classification = await asyncio.wait_for(_gemini_call(client, model, classify_prompt), timeout=30)
    logger.info(f"Classification: {classification.get('model_type', 'unknown')}")

    # Step 2: Extract columns for each sheet in parallel
    async def _extract_sheet(sheet_data: dict) -> list:
        prompt = f"{SHEET_PROMPT}\n\nSheet: {sheet_data['name']}\nInput cells ({len(sheet_data['input_cells'])} total):\n{json.dumps(sheet_data['input_cells'])}"
        if on_progress:
            await on_progress(f"[SCHEMA] Extracting {sheet_data['name']} ({len(sheet_data['input_cells'])} cells)...")
        return await asyncio.wait_for(_gemini_call(client, model, prompt), timeout=30)

    sheet_tasks = [_extract_sheet(s) for s in parsed_template["sheets"]]
    sheet_results = await asyncio.gather(*sheet_tasks)

    # Step 3: Assemble the full TemplateSchema
    sheets = []
    total_input = 0
    for sheet_data, columns_raw in zip(parsed_template["sheets"], sheet_results):
        if isinstance(columns_raw, dict) and "columns" in columns_raw:
            columns_raw = columns_raw["columns"]
        if not isinstance(columns_raw, list):
            columns_raw = [columns_raw]
        from backend.models.schemas import ColumnSchema, SheetSchema, ColumnConstraints
        columns = []
        for c in columns_raw:
            try:
                col = ColumnSchema(
                    header=c.get("header", ""),
                    data_type=c.get("data_type", "currency_USD"),
                    temporal_range=c.get("temporal_range"),
                    periods=c.get("periods", []),
                    is_input=c.get("is_input", True),
                    cell_references=c.get("cell_references", []),
                    sheet_name=c.get("sheet_name", sheet_data["name"]),
                    constraints=ColumnConstraints(**(c.get("constraints", {}))),
                )
                columns.append(col)
                if col.is_input:
                    total_input += max(len(col.periods), 1)
            except Exception as e:
                logger.warning(f"Skipping malformed column in {sheet_data['name']}: {e}")
        sheets.append(SheetSchema(name=sheet_data["name"], columns=columns))

    inter_refs = []
    from backend.models.schemas import InterSheetReference
    for ref in classification.get("inter_sheet_refs", []):
        try:
            inter_refs.append(InterSheetReference(**ref))
        except Exception:
            pass

    return TemplateSchema(
        model_type=classification.get("model_type", "unknown"),
        industry=classification.get("industry", "General Corporate"),
        currency=classification.get("currency", "USD"),
        sheets=sheets,
        inter_sheet_refs=inter_refs,
        total_input_cells=total_input or parsed_template.get("total_input_cells", 0),
    )


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

    await _report("Extracting financial schema...")
    try:
        schema = await _try_gemini(parsed_template, settings, on_progress=_report)
        await _report("Schema extraction complete")
    except Exception as e:
        reason = "timed out" if isinstance(e, asyncio.TimeoutError) else str(e)
        logger.warning(f"Gemini failed, falling back to GPT-4o: {reason}")
        await _report(f"Gemini failed ({reason}), falling back to GPT-4o...")
        schema = await _fallback_gpt4o(parsed_template, settings)
        await _report("GPT-4o schema extraction succeeded")

    return _enrich_schema_with_cell_refs(schema, parsed_template)
