import time
import json
import asyncio
import functools
import logging
from google import genai
from google.genai import types
from google.genai.errors import ClientError
from backend.models.schemas import TemplateSchema, SyntheticPayload, GenerationMetadata, TokenUsage, CellValue
from backend.config import Settings

logger = logging.getLogger(__name__)

# Smaller chunks = LLM never skips. 25 cells × ~5 tokens each = tiny output.
MAX_CELLS_PER_CHUNK = 25

##############################################################################
# SCENARIO ENGINE — LBO Archetype Profiles
#
# Each profile constrains the statistical bounds used for synthetic generation.
# Sources:
#   - Guo, Hotchkiss & Song (2011), J. Finance 66(2) — 192 LBOs
#   - Axelson, Jenkinson, Strömberg & Weisbach (2013), J. Finance 68(6) — 1,157 LBOs
#   - Bain & Company (2024), Global Private Equity Report
#   - RL Hulett (2024), Software & Tech-Enabled Services M&A Update Q3 2024
##############################################################################

_ABSOLUTE_RULES = """
ABSOLUTE RULES:
- NO zeros for debt repayments (senior must amortize every period)
- NO constant/flat values across all periods (margins, revenue, costs MUST vary)
- Percentages/rates as DECIMALS (25% = 0.25, NOT 25)
- Currency values as whole numbers (no decimals)
- Negative values where appropriate: Accumulated Depreciation, CapEx, Working Capital changes
- EVERY key must have a non-zero value unless explicitly stated as $0 above
- Values must tell a coherent story across all periods"""

SCENARIO_PROFILES = {

"general": """You are generating synthetic data for a LEVERAGED BUYOUT (LBO) financial model.
This data will be reviewed by private equity professionals. It must look realistic.

FINANCIAL PARAMETERS:
- Base revenue: $250M-$500M in FY2020, growing 8-12% annually (MUST increase every year)
- COGS: 55-65% of revenue (vary ±1-2% each year, NOT constant)
- SG&A: 12-18% of revenue (vary ±0.5-1% each year)
- R&D: 3-6% of revenue (grow slightly each year)
- Other Operating Expenses: 1-3% of revenue
- D&A: Start $10M-$20M, grow 5-10% annually as PP&E grows
- Effective tax rate: 0.25 (as decimal, constant)
- EBITDA margins: 18-30% (vary ±1-2% each year, NEVER identical across periods)
- Senior debt interest rate: 0.055-0.075 (as decimal, constant across periods)
- Mezzanine/PIK interest rate: 0.09-0.13 (as decimal, constant across periods)

DEBT SCHEDULE (CRITICAL — no zeros):
- Senior debt opening balance: $300M-$500M in FY2020
- Senior debt MUST be repaid: mandatory amortization of $30M-$80M per year (NEVER zero)
- Senior drawdowns: $0 after FY2020 (typical LBO — no new senior draws post-close)
- Mezzanine opening balance: $80M-$150M in FY2020
- Mezzanine repayments: $0 in early years, $5M-$20M in FY2024-FY2025 (bullet repayment)
- Mezzanine drawdowns: $0 (PIK accrues, no new draws)

BALANCE SHEET:
- Cash: $25M-$50M, varying each period (NOT constant)
- AR: 8-12% of revenue, growing with revenue
- Inventory: 5-10% of revenue
- PP&E Gross: $80M-$200M, increasing $15M-$25M annually (CapEx additions)
- Accumulated Depreciation: starts -$20M, grows by D&A amount each year (NEGATIVE values)
- Goodwill: $100M-$200M (constant — acquired at LBO entry)
- Intangible Assets: $30M-$60M, declining 5-10% annually (amortization)
- AP: 6-10% of revenue
- Accrued Liabilities: 3-5% of revenue
- Deferred Revenue: 1-3% of revenue
- Common Equity: $100M-$200M (constant — sponsor equity at entry)
- AOCI: small, $0-$5M

CASH FLOW:
- Working capital changes: -$5M to -$15M (negative = cash used as company grows)
- CapEx: -$15M to -$30M (NEGATIVE, growing 5-8% annually)
- Acquisitions: $0 (no bolt-ons in base case)
- Dividends: $0 (all cash goes to debt paydown in LBO)
- Debt drawdowns: $0 after FY2020 (no new borrowing)
- Debt repayments: MUST match debt schedule senior repayments

RETURNS ANALYSIS:
- Entry year: 2020, Exit year: 2025, Horizon: 5
- LTM EBITDA at entry: match FY2020 EBITDA from Income Statement
- Entry EV/EBITDA multiple: 8x-12x
- Exit EV/EBITDA multiple: 9x-12x (slight expansion)
- Entry Equity = Entry EV - Net Debt at Entry
- Sponsor equity invested: $100M-$200M
- Management rollover: $5M-$15M
- LTM EBITDA at exit: match FY2025 EBITDA
- IRR Cash Flow: Year 0 = negative equity invested, Years 1-4 = $0 (no interim distributions), Year 5 = exit equity proceeds
- IRR: 0.15-0.30 (as decimal)
- MOIC: 2.0x-3.5x""",


"distressed_turnaround": """You are generating synthetic data for a DISTRESSED TURNAROUND LBO financial model.
This is a distressed asset acquisition — the company has severely depressed margins at entry,
high debt burden, and the PE sponsor's thesis is aggressive operational improvement over 5 years.
Data must reflect the V-shaped recovery arc: poor initial performance improving dramatically.
[Sources: Guo et al. (2011) Table 6 Panel B; Axelson et al. (2013) Table III; Bain PE Report 2024 p15-16]

FINANCIAL PARAMETERS:
- Base revenue: $100M-$400M in FY2020 (smaller distressed target)
- Revenue growth: DECLINING -5% to +2% in FY2021-FY2022 (restructuring drag), then RECOVERING +4% to +10% in FY2023-FY2025
- COGS: 70-78% of revenue in FY2020 (margin-compressed), improving 1-3% annually as ops improve
- SG&A: 15-18% of revenue in FY2020 (bloated), declining 1-2% per year (cost-cutting)
- R&D: 1-2% of revenue (minimal in distressed industrial)
- Other Operating Expenses: 2-4% of revenue (restructuring charges in FY2020-FY2021)
- CRITICAL: COGS + SG&A + R&D + Other OpEx in FY2020 MUST sum to 92-97% of revenue (leaving 3-8% EBITDA margin). By FY2025, costs must sum to 80-86% of revenue (leaving 14-20% EBITDA margin). Do NOT generate negative EBITDA.
- D&A: Start $8M-$15M, grow 3-6% annually
- Effective tax rate: 0.25 (as decimal, constant)
- EBITDA margins: 3-8% at entry (FY2020) — MUST be POSITIVE (the company is barely profitable, NOT loss-making)
- EBITDA margins MUST expand to 14-20% by exit (FY2025) — aggressive operational improvement over 5 years
- CRITICAL: Entry EBITDA must be positive (3-8% of revenue). Exit EBITDA must be 14-20% of revenue. Show clear upward trajectory every year.
- Senior debt interest rate: 0.09-0.13 (distressed = high cost of debt)
- Mezzanine/PIK interest rate: 0.13-0.17 (CCC-rated credit)

DEBT SCHEDULE (CRITICAL — no zeros):
- Senior debt opening balance: $400M-$600M in FY2020 (heavy debt burden, 6.5-8.5x EBITDA)
- Senior debt MUST be repaid: mandatory amortization of $20M-$50M per year (NEVER zero, but lower amort due to cash constraints)
- Senior drawdowns: $0 after FY2020
- Mezzanine opening balance: $100M-$200M in FY2020
- Mezzanine repayments: $0 in FY2020-FY2023 (cash-strapped), $10M-$30M in FY2024-FY2025
- Mezzanine drawdowns: $0 (PIK accrues, no new draws)

BALANCE SHEET:
- Cash: $10M-$30M (tight liquidity), varying each period
- AR: 10-15% of revenue (slower collections in distressed)
- Inventory: 8-14% of revenue (excess inventory being worked down)
- PP&E Gross: $60M-$150M, increasing only $5M-$15M annually (minimal CapEx during turnaround)
- Accumulated Depreciation: starts -$25M, grows by D&A amount each year (NEGATIVE values)
- Goodwill: $50M-$120M (constant — lower due to distressed purchase price)
- Intangible Assets: $15M-$40M, declining 8-12% annually
- AP: 8-14% of revenue (stretching payables)
- Accrued Liabilities: 4-7% of revenue (higher accruals in distress)
- Deferred Revenue: 0-2% of revenue
- Common Equity: $60M-$150M (constant — lower sponsor equity, higher leverage)
- AOCI: small, $0-$3M

CASH FLOW:
- Working capital changes: -$2M to +$5M (releasing working capital through inventory reduction)
- CapEx: -$5M to -$15M (NEGATIVE, minimal maintenance CapEx during turnaround)
- Acquisitions: $0
- Dividends: $0 (all cash to debt service)
- Debt drawdowns: $0 after FY2020
- Debt repayments: MUST match debt schedule

RETURNS ANALYSIS:
- Entry year: 2020, Exit year: 2025, Horizon: 5
- LTM EBITDA at entry: match FY2020 EBITDA (will be low — 3-8% margin on $100M-$400M revenue)
- Entry EV/EBITDA multiple: 5x-7x (distressed discount)
- Exit EV/EBITDA multiple: 7x-10x (re-rating as margins normalize)
- Entry Equity = Entry EV - Net Debt at Entry
- Sponsor equity invested: $60M-$150M
- Management rollover: $3M-$10M
- LTM EBITDA at exit: match FY2025 EBITDA (substantially higher due to margin expansion)
- IRR Cash Flow: Year 0 = negative equity invested, Years 1-4 = $0, Year 5 = exit equity proceeds
- IRR: 0.20-0.35 (high return compensates for high risk)
- MOIC: 2.5x-4.0x""",


"high_growth_tech": """You are generating synthetic data for a HIGH-GROWTH TECHNOLOGY BUYOUT LBO financial model.
This is a software/SaaS company acquisition — high revenue growth, low or negative initial EBITDA,
the thesis is that operating leverage at scale will drive profitability. Asset-light business = lower debt.
[Sources: RL Hulett Q3 2024 p7 (EV/Rev 4.96x, EV/EBITDA 53.4x); Bain PE Report 2024 p14,28]

FINANCIAL PARAMETERS:
- Base revenue: $50M-$250M in FY2020 (smaller, high-growth target)
- Revenue growth: 18-30% annually (MUST increase every year, high growth is the thesis)
- COGS: 20-35% of revenue (software gross margins 65-80%)
- SG&A: 35-55% of revenue in FY2020 (heavy sales & marketing spend), declining 2-4% of revenue per year as scale efficiencies kick in
- R&D: 15-25% of revenue (critical for tech — maintain or grow slightly)
- Other Operating Expenses: 1-3% of revenue
- D&A: Start $3M-$8M, grow 8-12% annually (servers, capitalized software)
- Effective tax rate: 0.25 (as decimal, constant)
- EBITDA margins: -5% to +10% at entry (FY2020), expanding to 18-28% by exit (FY2025) — operating leverage story
- Senior debt interest rate: 0.07-0.10 (better-rated tech credits)
- Mezzanine/PIK interest rate: 0.10-0.13

DEBT SCHEDULE (CRITICAL — no zeros):
- Senior debt opening balance: $50M-$200M in FY2020 (LOW leverage — 2.0-4.0x EBITDA, asset-light)
- Senior debt MUST be repaid: mandatory amortization of $10M-$30M per year (NEVER zero)
- Senior drawdowns: $0 after FY2020
- Mezzanine opening balance: $30M-$80M in FY2020
- Mezzanine repayments: $0 in FY2020-FY2023, $5M-$15M in FY2024-FY2025
- Mezzanine drawdowns: $0 (PIK accrues, no new draws)

BALANCE SHEET:
- Cash: $20M-$60M (tech companies hold more cash), varying each period
- AR: 12-18% of revenue (SaaS billing cycles)
- Inventory: $0-$2M (software = no physical inventory)
- PP&E Gross: $10M-$40M (asset-light), increasing $3M-$8M annually
- Accumulated Depreciation: starts -$5M, grows by D&A amount each year (NEGATIVE values)
- Goodwill: $150M-$400M (constant — high goodwill due to premium acquisition price)
- Intangible Assets: $80M-$200M (customer lists, IP, capitalized software), declining 5-8% annually
- AP: 3-6% of revenue
- Accrued Liabilities: 5-10% of revenue (accrued comp, commissions)
- Deferred Revenue: 8-15% of revenue (annual SaaS subscriptions paid upfront — CRITICAL for tech)
- Common Equity: $150M-$350M (constant — MORE equity, less debt in tech buyouts)
- AOCI: small, $0-$5M

CASH FLOW:
- Working capital changes: -$5M to -$20M (negative = cash consumed by rapid growth)
- CapEx: -$3M to -$10M (NEGATIVE, asset-light but growing infrastructure)
- Acquisitions: $0
- Dividends: $0
- Debt drawdowns: $0 after FY2020
- Debt repayments: MUST match debt schedule

RETURNS ANALYSIS:
- Entry year: 2020, Exit year: 2025, Horizon: 5
- LTM EBITDA at entry: match FY2020 EBITDA (may be very low or near-zero due to SG&A/R&D burn)
- Entry EV/EBITDA multiple: 25x-50x (growth premium — these deals price on revenue, not EBITDA)
- Exit EV/EBITDA multiple: 15x-25x (multiple compresses as company matures, but EBITDA is now substantial)
- Entry Equity = Entry EV - Net Debt at Entry
- Sponsor equity invested: $150M-$350M (majority equity-funded)
- Management rollover: $10M-$25M
- LTM EBITDA at exit: match FY2025 EBITDA (dramatically higher due to operating leverage)
- IRR Cash Flow: Year 0 = negative equity invested, Years 1-4 = $0, Year 5 = exit equity proceeds
- IRR: 0.20-0.30 (as decimal)
- MOIC: 2.5x-3.5x""",


"mature_cashcow": """You are generating synthetic data for a MATURE CASH-COW / MANUFACTURING LBO financial model.
This is a stable industrial/manufacturing acquisition — low growth, high and steady EBITDA margins,
heavy leverage supported by predictable cash flows, value from financial engineering + modest margin gains.
[Sources: Axelson et al. (2013) Table III (D/EBITDA 5.6x mean); Guo et al. (2011) Table 8 Panel B; Bain PE Report 2024 p16 (5.9x 2023)]

FINANCIAL PARAMETERS:
- Base revenue: $250M-$750M in FY2020 (established mid-market industrial)
- Revenue growth: 2-5% annually (stable, low-growth — MUST increase but slowly)
- COGS: 58-65% of revenue (vary ±1-2% each year, NOT constant)
- SG&A: 12-16% of revenue (lean, well-optimized cost structure)
- R&D: 2-4% of revenue (maintenance R&D in mature industrial)
- Other Operating Expenses: 2-4% of revenue (facilities, insurance, misc)
- D&A: Start $12M-$25M, grow 3-6% annually as PP&E grows
- Effective tax rate: 0.25 (as decimal, constant)
- EBITDA margins: 16-20% at entry, stable/slightly expanding to 17-22% by exit — NEVER volatile
- CRITICAL: COGS + SG&A + R&D + Other OpEx MUST sum to 80-86% of revenue (leaving 14-20% EBITDA margin). Do NOT generate margins above 22%.
- Senior debt interest rate: 0.06-0.085 (stable credits get better spreads)
- Mezzanine/PIK interest rate: 0.09-0.12

DEBT SCHEDULE (CRITICAL — no zeros):
- Senior debt opening balance: $400M-$600M in FY2020 (HIGH leverage — 5.5-7.0x EBITDA, supported by stable cash flows)
- Senior debt MUST be repaid: mandatory amortization of $40M-$90M per year (NEVER zero, aggressive deleveraging)
- Senior drawdowns: $0 after FY2020
- Mezzanine opening balance: $80M-$150M in FY2020
- Mezzanine repayments: $0 in FY2020-FY2022, $10M-$25M in FY2023-FY2025 (earlier repayment — cash available)
- Mezzanine drawdowns: $0 (PIK accrues, no new draws)

BALANCE SHEET:
- Cash: $30M-$60M, varying each period (NOT constant)
- AR: 8-12% of revenue, growing with revenue
- Inventory: 8-14% of revenue (manufacturing carries physical inventory)
- PP&E Gross: $120M-$300M (capital-intensive), increasing $20M-$35M annually (CapEx additions)
- Accumulated Depreciation: starts -$30M, grows by D&A amount each year (NEGATIVE values)
- Goodwill: $100M-$250M (constant — acquired at LBO entry)
- Intangible Assets: $20M-$50M, declining 5-10% annually (amortization)
- AP: 7-12% of revenue
- Accrued Liabilities: 3-5% of revenue
- Deferred Revenue: 0-2% of revenue (minimal for manufacturing)
- Common Equity: $100M-$200M (constant — sponsor equity at entry)
- AOCI: small, $0-$5M

CASH FLOW:
- Working capital changes: -$3M to -$10M (negative = modest cash used as company grows slowly)
- CapEx: -$20M to -$40M (NEGATIVE, capital-intensive manufacturing, growing 3-5% annually)
- Acquisitions: $0 (no bolt-ons in base case)
- Dividends: $0 (all cash to debt paydown)
- Debt drawdowns: $0 after FY2020
- Debt repayments: MUST match debt schedule senior repayments

RETURNS ANALYSIS:
- Entry year: 2020, Exit year: 2025, Horizon: 5
- LTM EBITDA at entry: match FY2020 EBITDA from Income Statement
- Entry EV/EBITDA multiple: 8x-11x
- Exit EV/EBITDA multiple: 9x-12x (slight expansion)
- Entry Equity = Entry EV - Net Debt at Entry
- Sponsor equity invested: $100M-$200M
- Management rollover: $5M-$15M
- LTM EBITDA at exit: match FY2025 EBITDA
- IRR Cash Flow: Year 0 = negative equity invested, Years 1-4 = $0, Year 5 = exit equity proceeds
- IRR: 0.15-0.25 (as decimal)
- MOIC: 2.0x-3.0x""",

}

def _get_financial_context(scenario_type: str = "general") -> str:
    """Return the full financial context prompt for the given scenario type."""
    profile = SCENARIO_PROFILES.get(scenario_type, SCENARIO_PROFILES["general"])
    return profile + _ABSOLUTE_RULES


async def _llm_generate_values(client, model: str, prompt: str) -> tuple[dict, int]:
    """Call Gemini and return a parsed dict of {key: value} + token count. Retries up to 3 times on 429."""
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
                        temperature=0.3,
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
        except ClientError as e:
            if e.code == 429 and attempt < max_retries:
                delay = backoff_delays[attempt]
                logger.warning(f"[SYNTH] 429 RESOURCE_EXHAUSTED — retry {attempt + 1}/{max_retries} in {delay}s")
                await asyncio.to_thread(time.sleep, delay)
            else:
                raise


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
                          cells: list, prior_sheets: dict, chunk_label: str = "",
                          scenario_type: str = "general") -> tuple[list, int]:
    """Generate values for a chunk. LLM returns {"1": value, "2": value, ...}. Python maps back to cells."""
    cell_count = len(cells)
    grid = _build_cell_grid(cells)
    financial_context = _get_financial_context(scenario_type)

    prompt = f"""Generate {cell_count} realistic values for a {schema.model_type} financial model ({schema.industry}, {schema.currency}).
Sheet: "{sheet_name}"

{financial_context}

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

{financial_context}

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
                          cells: list, prior_sheets: dict, scenario_type: str = "general") -> tuple[list, int]:
    """Generate all cells for a sheet, sub-chunking and parallelizing."""
    chunks = _split_chunks(cells)
    if len(chunks) == 1:
        return await _generate_chunk(client, model, schema, sheet_name, cells, prior_sheets,
                                     scenario_type=scenario_type)

    tasks = []
    for i, chunk in enumerate(chunks):
        label = f" [{i+1}/{len(chunks)}]"
        tasks.append(_generate_chunk(client, model, schema, sheet_name, chunk, prior_sheets, label,
                                     scenario_type=scenario_type))

    results = await asyncio.gather(*tasks)
    all_cells = []
    total_tokens = 0
    for cells_result, tokens in results:
        all_cells.extend(cells_result)
        total_tokens += tokens
    return all_cells, total_tokens


async def generate_synthetic_data(schema: TemplateSchema, settings: Settings,
                                  retry_instructions: str = None, parsed_template: dict = None,
                                  scenario_type: str = "general") -> SyntheticPayload:
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
    logger.info(f"Generating {total_cells} cells across {len(sheets_cells)} sheets (max {MAX_CELLS_PER_CHUNK}/chunk, scenario={scenario_type})")

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
            result, tokens = await _generate_sheet(client, settings.gemini_model, schema, sheet_name, cells, prior_sheets,
                                                    scenario_type=scenario_type)
            all_cells.extend(result)
            total_tokens += tokens
            prior_sheets.update(_extract_cross_sheet_values(result))

    if phase3:
        tasks = [
            _generate_sheet(client, settings.gemini_model, schema, sheet_name, sheets_cells[sheet_name], prior_sheets,
                            scenario_type=scenario_type)
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
            temperature=0.3,
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
