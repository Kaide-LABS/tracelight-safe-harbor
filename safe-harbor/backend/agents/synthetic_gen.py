import time
import json
import asyncio
import functools
import logging
from google import genai
from google.genai import types
from backend.models.schemas import TemplateSchema, SyntheticPayload, GenerationMetadata, TokenUsage, CellValue
from backend.config import Settings

logger = logging.getLogger(__name__)

# Smaller chunks = LLM never skips. 25 cells × ~5 tokens each = tiny output.
MAX_CELLS_PER_CHUNK = 25

FINANCIAL_CONTEXT = """FINANCIAL PARAMETERS:
- Base revenue: $150M-$500M with 8-12% annual growth
- COGS: 50-65% of revenue
- SG&A: 10-20% of revenue
- R&D: 3-8% of revenue
- D&A: 3-6% of revenue
- Effective tax rate: 21-28% (as decimal, e.g. 0.25)
- EBITDA margins: 15-35%
- Senior debt interest rate: 5-8% (as decimal, e.g. 0.065)
- Mezzanine/PIK interest rate: 8-14% (as decimal, e.g. 0.10)
- Senior debt beginning balance: $200M-$500M, repaying 5-15% annually
- Mezzanine beginning balance: $50M-$150M
- CapEx: $10M-$30M annually
- Working capital changes: negative 2-5% of revenue change
- Cash beginning of period: $20M-$50M
- Entry EV/EBITDA multiple: 8x-12x
- Exit EV/EBITDA multiple: 8x-12x
- Investment horizon: 5 years

RULES:
- Revenue should grow steadily. Costs should scale proportionally.
- Percentages/rates as DECIMALS (25% = 0.25, NOT 25)
- Currency values as whole numbers (no decimals for large amounts)
- Generate REALISTIC values — no zeros, no ones, no placeholder values
- EVERY key must have a value. Do NOT skip any."""


async def _llm_generate_values(client, model: str, prompt: str) -> tuple[dict, int]:
    """Call Gemini and return a parsed dict of {key: value} + token count."""
    response = await asyncio.to_thread(
        functools.partial(
            client.models.generate_content,
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=1.0,
                max_output_tokens=8192,
                thinking_config=types.ThinkingConfig(thinking_budget=512),
                response_mime_type="application/json",
            ),
        )
    )
    raw_text = response.text
    if raw_text.startswith("```json"):
        raw_text = raw_text[7:]
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]
    parsed = json.loads(raw_text)
    # Normalize: if it returned a list, convert to dict by index
    if isinstance(parsed, list):
        parsed = {str(i + 1): v for i, v in enumerate(parsed)}
    # If nested (e.g. {"values": {...}}), unwrap
    if len(parsed) == 1 and isinstance(list(parsed.values())[0], dict):
        parsed = list(parsed.values())[0]
    usage_meta = getattr(response, 'usage_metadata', None)
    tokens = getattr(usage_meta, 'candidates_token_count', 0) if usage_meta else 0
    return parsed, tokens


def _build_cell_grid(cells: list) -> str:
    """Build a numbered grid: 1. B4 Revenue [FY2020] (currency)"""
    lines = []
    for i, c in enumerate(cells, 1):
        header = c["header"]
        period = c.get("period", "")
        cell_ref = c["cell_ref"]
        # Infer type hint from header
        h_lower = header.lower()
        if any(k in h_lower for k in ["rate", "margin", "%", "yield", "irr"]):
            hint = "decimal 0-1"
        elif any(k in h_lower for k in ["multiple", "moic", "ev/"]):
            hint = "ratio e.g. 10.5"
        elif any(k in h_lower for k in ["year", "horizon"]):
            hint = "integer e.g. 2020 or 5"
        else:
            hint = "currency integer"
        lines.append(f'{i}. [{cell_ref}] {header} | {period} | {hint}')
    return "\n".join(lines)


async def _generate_chunk(client, model: str, schema: TemplateSchema, sheet_name: str,
                          cells: list, prior_sheets: dict, chunk_label: str = "") -> tuple[list, int]:
    """Generate values for a chunk. LLM returns {"1": value, "2": value, ...}. Python maps back to cells."""
    cell_count = len(cells)
    grid = _build_cell_grid(cells)

    prompt = f"""Generate {cell_count} realistic values for a {schema.model_type} financial model ({schema.industry}, {schema.currency}).
Sheet: "{sheet_name}"

{FINANCIAL_CONTEXT}

{"PRIOR VALUES (for cross-sheet consistency):" + chr(10) + json.dumps(prior_sheets, indent=2) if prior_sheets else ""}

Return a JSON object with keys "1" through "{cell_count}", each mapping to a numeric value.
Example: {{"1": 300000000, "2": 330000000, "3": 0.55}}

CELLS (generate a value for ALL {cell_count}):
{grid}"""

    values_dict, tokens = await _llm_generate_values(client, model, prompt)
    total_tokens = tokens

    # Map values back to cells deterministically
    result = []
    missing_indices = []
    for i, cell in enumerate(cells, 1):
        key = str(i)
        if key in values_dict:
            val = values_dict[key]
            # Handle nested objects (LLM sometimes returns {"1": {"value": 300}})
            if isinstance(val, dict):
                val = val.get("value", val.get("v", 0))
            result.append({
                "sheet_name": cell["sheet_name"],
                "cell_ref": cell["cell_ref"],
                "header": cell["header"],
                "period": cell.get("period", ""),
                "value": val,
            })
        else:
            missing_indices.append(i)

    # Backfill any missing keys
    if missing_indices:
        logger.info(f"  {sheet_name}{chunk_label}: backfilling {len(missing_indices)} missing values")
        missing_cells = [cells[i - 1] for i in missing_indices]
        missing_grid = _build_cell_grid(missing_cells)

        backfill_prompt = f"""Generate {len(missing_cells)} values for a {schema.model_type} model. Sheet: "{sheet_name}".

{FINANCIAL_CONTEXT}

Return JSON: {{"1": value, "2": value, ...}}

CELLS:
{missing_grid}"""

        backfill_dict, bf_tokens = await _llm_generate_values(client, model, backfill_prompt)
        total_tokens += bf_tokens

        for j, cell in enumerate(missing_cells, 1):
            val = backfill_dict.get(str(j), 0)
            if isinstance(val, dict):
                val = val.get("value", val.get("v", 0))
            result.append({
                "sheet_name": cell["sheet_name"],
                "cell_ref": cell["cell_ref"],
                "header": cell["header"],
                "period": cell.get("period", ""),
                "value": val,
            })

    logger.info(f"  {sheet_name}{chunk_label}: {len(result)}/{cell_count} cells")
    return result, total_tokens


def _split_chunks(cells: list, max_size: int = MAX_CELLS_PER_CHUNK) -> list[list]:
    return [cells[i:i + max_size] for i in range(0, len(cells), max_size)]


def _extract_cross_sheet_values(cells: list) -> dict:
    """Extract key financial values for cross-sheet consistency."""
    context = {}
    keywords = [
        "revenue", "net income", "ebitda", "total assets", "total liabilities",
        "total equity", "beginning balance", "ending balance", "d&a",
        "depreciation", "capex", "interest", "cash", "debt"
    ]
    for cell in cells:
        header = cell.get("header", "").lower()
        if any(kw in header for kw in keywords):
            key = f"{cell.get('header', '')}|{cell.get('period', '')}"
            context[key] = cell.get("value")
    return context


async def _generate_sheet(client, model: str, schema: TemplateSchema, sheet_name: str,
                          cells: list, prior_sheets: dict) -> tuple[list, int]:
    """Generate all cells for a sheet, sub-chunking and parallelizing."""
    chunks = _split_chunks(cells)
    if len(chunks) == 1:
        return await _generate_chunk(client, model, schema, sheet_name, cells, prior_sheets)

    tasks = []
    for i, chunk in enumerate(chunks):
        label = f" [{i+1}/{len(chunks)}]"
        tasks.append(_generate_chunk(client, model, schema, sheet_name, chunk, prior_sheets, label))

    results = await asyncio.gather(*tasks)
    all_cells = []
    total_tokens = 0
    for cells_result, tokens in results:
        all_cells.extend(cells_result)
        total_tokens += tokens
    return all_cells, total_tokens


async def generate_synthetic_data(schema: TemplateSchema, settings: Settings,
                                  retry_instructions: str = None, parsed_template: dict = None) -> SyntheticPayload:
    client = genai.Client(api_key=settings.gemini_api_key)

    # Group input cells by sheet from parser output
    sheets_cells = {}
    if parsed_template:
        for sheet in parsed_template["sheets"]:
            cells = []
            for ic in sheet["input_cells"]:
                cells.append({
                    "sheet_name": sheet["name"],
                    "header": ic["column_header"],
                    "period": ic.get("period", ""),
                    "cell_ref": ic["ref"],
                })
            if cells:
                sheets_cells[sheet["name"]] = cells
    else:
        for sheet in schema.sheets:
            for col in sheet.columns:
                if col.is_input and col.periods:
                    for period in col.periods:
                        idx = col.periods.index(period)
                        if sheet.name not in sheets_cells:
                            sheets_cells[sheet.name] = []
                        sheets_cells[sheet.name].append({
                            "sheet_name": sheet.name,
                            "header": col.header,
                            "period": period,
                            "cell_ref": col.cell_references[idx] if idx < len(col.cell_references) else ""
                        })

    total_cells = sum(len(cells) for cells in sheets_cells.values())
    logger.info(f"Generating {total_cells} cells across {len(sheets_cells)} sheets (max {MAX_CELLS_PER_CHUNK}/chunk)")

    start_time = time.time()
    all_cells = []
    total_tokens = 0
    prior_sheets = {}

    # Phase 1: Income Statement (baseline revenue/costs)
    # Phase 2: Debt Schedule (needs IS context)
    # Phase 3: Everything else in parallel
    phase1 = ["Income Statement"]
    phase2 = ["Debt Schedule"]
    phase3 = [name for name in sheets_cells if name not in phase1 + phase2]

    for phase_sheets in [phase1, phase2]:
        for sheet_name in phase_sheets:
            if sheet_name not in sheets_cells:
                continue
            cells = sheets_cells[sheet_name]
            result, tokens = await _generate_sheet(client, settings.gemini_model, schema, sheet_name, cells, prior_sheets)
            all_cells.extend(result)
            total_tokens += tokens
            prior_sheets.update(_extract_cross_sheet_values(result))

    if phase3:
        tasks = [
            _generate_sheet(client, settings.gemini_model, schema, sheet_name, sheets_cells[sheet_name], prior_sheets)
            for sheet_name in phase3
        ]
        results = await asyncio.gather(*tasks)
        for result, tokens in results:
            all_cells.extend(result)
            total_tokens += tokens

    generation_time = int((time.time() - start_time) * 1000)

    cell_values = []
    for c in all_cells:
        try:
            cell_values.append(CellValue(
                sheet_name=c.get("sheet_name", ""),
                cell_ref=c.get("cell_ref", ""),
                header=c.get("header", ""),
                period=c.get("period", ""),
                value=c.get("value", 0),
            ))
        except Exception as e:
            logger.warning(f"Skipping malformed cell: {c} — {e}")

    result = SyntheticPayload(
        model_type=schema.model_type,
        industry=schema.industry,
        currency=schema.currency,
        cells=cell_values,
        generation_metadata=GenerationMetadata(
            model_used=settings.gemini_model,
            temperature=1.0,
            token_usage=TokenUsage(
                prompt_tokens=0,
                completion_tokens=total_tokens,
                total_tokens=total_tokens
            ),
            generation_time_ms=generation_time
        )
    )

    logger.info(f"Total: {len(result.cells)} cells generated (expected {total_cells}) in {generation_time}ms")
    return result
