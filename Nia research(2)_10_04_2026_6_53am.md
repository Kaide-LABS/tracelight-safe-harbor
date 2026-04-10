# Oracle Research Report

**Date:** 4/10/2026, 6:27:21 AM
**Duration:** 510.5s
**Iterations:** 20

---

## Research Query

Continue and expand on the following research:

ORIGINAL RESEARCH QUERY:
You have full access to the Kaide-LABS/tracelight-safe-harbor repository. Focus on the safe-harbor service — specifically the end-to-end pipeline from synthetic data generation to Google Sheets          
  validation output.                                                                                                                                                                              
                  
  ## The Problem                                                                                                                                                                                  
                  
  The generation pipeline produces synthetic LBO (Leveraged Buyout) financial data across 5 sheets (Income Statement, Debt Schedule, Balance Sheet, Cash Flow, Returns). A validation tab is      
  appended to the Google Sheets output with 8 sections of live formulas that check mathematical consistency. Currently, most validation checks are FAILING even though:
                                                                                                                                                                                                  
  1. A Banach fixed-point iteration solver (`safe-harbor/backend/agents/post_processor.py`) was implemented to resolve circular references (Interest → Net Income → Cash Flow → Debt Repayment →  
  Interest). It passes unit tests in isolation.
  2. The generation engine (`safe-harbor/backend/agents/synthetic_gen.py`) uses a value-only approach where the LLM returns indexed values and Python maps them back to cell references.          
  3. The parser (`safe-harbor/backend/excel_io/parser.py`) uses section-qualified headers to disambiguate duplicate column names across sheets.                                                   
                                                                                                                                                                                                  
  ## Specific Failures                                                                                                                                                                            
                                                                                                                                                                                                  
  1. **Balance Sheet Identity (Assets = Liabilities + Equity):** FAIL — the fixed-point solver modifies Retained Earnings, Beginning Cash, and Senior/Mezz Repayments, but the final values       
  written to Google Sheets don't produce a balanced BS. Suspect: either the solver's Python simulation of formulas diverges from the actual Excel/Sheets template formulas, or the cell references
   used by the solver don't match the template's actual row layout.                                                                                                                               
                  
  2. **Debt Rollforward:** FAIL — Beginning Balance(t) should equal Ending Balance(t-1) for each debt tranche. The solver handles repayments but something breaks in the mapping.                 
   
  3. **Revenue Growth validation:** Shows #ERROR! for FY2020 — this is a div-by-zero because there's no FY2019 prior period. The validation formula builder needs to handle the base year edge    
  case.           
                                                                                                                                                                                                  
  4. **Avg Growth:** Shows #NAME? — likely a formula syntax error in the validation sheet builder (wrong function name or malformed range reference).                                             
   
  ## What I Need You To Do                                                                                                                                                                        
                  
  1. **Trace the full data flow**: Follow a single generated value from LLM output → synthetic_gen.py cell mapping → post_processor.py solver adjustment → excel_io writer → Google Sheets API    
  batchUpdate. Identify every point where cell references could become misaligned with the actual template.
                                                                                                                                                                                                  
  2. **Compare solver assumptions vs template reality**: The solver in post_processor.py simulates formulas in Python (e.g., Total Assets = Cash + Other Assets). Read the actual template        
  structure and verify that every formula the solver assumes matches the real template layout. Flag any row number mismatches.
                                                                                                                                                                                                  
  3. **Diagnose the validation formula builder**: Find where the validation sheet formulas are constructed (likely in the Google Sheets writer or a dedicated validation module). Check for: wrong
   sheet name references, hardcoded row numbers that don't match the template, missing edge case handling (like the FY2020 div-by-zero), and any use of Excel-only functions not supported in
  Google Sheets.                                                                                                                                                                                  
                  
  4. **Propose a concrete fix strategy**: After the diagnosis, give me a prioritized list of exact code changes needed — file paths, function names, line-level descriptions of what to change and
   why. Focus on changes that will make the validation tab pass, not architectural rewrites.
                                                                                                                                                                                                  
  ## Constraints  
  - No virtual environments — everything runs globally
  - Models: gemini-3-flash-preview (schema extraction), gemini-3.1-pro-preview (generation)                                                                                                       
  - The template is an uploaded .xlsx file that gets parsed; generated output goes to Google Sheets via API                                                                                       
  - This is a pitch demo for investors with Jane Street/McKinsey/Cambridge backgrounds — mathematical rigor matters

[Pre-selected sources to focus on:
Codebase: Kaide-LABS/tracelight-safe-harbor:main (e83393b7-1ee7-4b81-b0a0-fffc1b7afa1b)]

PREVIOUS RESEARCH SUMMARY:
## Executive Summary

**The validation failures share a single root cause: a systemic row-number mismatch between the actual LBO template and every downstream component that references it.** The post-processor (`post_processor.py`), the validation formula builder (`_add_validation_sheet` in `main.py`), and the cross-sheet linkage checks were all coded against a theoretical 45-row Balance Sheet layout described in the design spec [Source 14], while the actual template generated by `generate_templates.py` [Source 13] uses a compact layout with roughly half the rows. Additionally, the validation builder references a sheet named `'Cash Flow Statement'` that doesn't exist — the actual sheet is named `'Cash Flow'` — causing the entire cash flow validation section to be silently skipped. Every single row reference is wrong, and several formula-level bugs compound the problem.

---

## 1. Full Data Flow Trace

### Stage 1: Template Parsing (`parser.py`)

The parser reads the `.xlsx` file with `openpyxl` (preserving formulas), scans row 1 for period headers (`FY2020`–`FY2025`), then iterates data rows to classify each cell as either an input cell (empty/numeric) or a formula cell (starts with `=`). It builds section-qualified headers like `"SENIOR SECURED DEBT > Beginning Balance"` to disambiguate duplicate row labels across debt tranches [Source 9].

**Key output shape**: Each input cell carries a `cell_ref` (e.g., `"B4"`), a `column_header` (qualified), a `period` label, and the `sheet_name`. This is the single source of truth for cell addresses.

### Stage 2: Synthetic Generation (`synthetic_gen.py`)

The generator receives the parsed cells, groups them by sheet, and sends them to Gemini in numbered chunks of ≤25 cells. The LLM returns `{"1": value, "2": value, ...}`, and Python maps each index back to the original `cell_ref` deterministically [Source 10]. This stage is **alignment-safe** — it never invents cell references; it uses exactly what the parser provided.

### Stage 3: Post-Processing / Circular Reference Solver (`post_processor.py`)

This is where alignment breaks. The solver parses each cell's `cell_ref` string to extract `(column_letter, row_number)`, maps column letters to period indices (`B→0, C→1, ...`), and builds per-period grids keyed by `(sheet_name, row_number)`. It then runs Banach fixed-point iteration using **hardcoded row numbers** to simulate the IS→DS→CF→BS formula chain [Source 3].

**Critical failure point**: The solver reads `cell_ref = "B2"` for Revenue (actual template row 2), but its simulation logic references row 4 for Revenue. The `_get(g, IS, 4)` call retrieves nothing (returns 0.0), while the actual Revenue value sits at `(IS, 2)` in the grid. **The entire simulation operates on phantom data.**

### Stage 4: Excel Writer (`writer.py`)

The writer loads the original template, iterates through payload cells, and writes values — but **skips any cell whose existing value starts with `=`** [Source 4]. This is critical: the post-processor attempts to write adjusted Retained Earnings to BS row 40 and Beginning Cash to CF row 31, but in the actual template, RE (row 19) and Beginning Cash (row 13) are both formula cells. The writer silently discards these corrections.

### Stage 5: Google Sheets Output & Validation Tab (`main.py`)

The `_create_sheet_from_xlsx` function reads the output `.xlsx`, creates a Google Spreadsheet via the Sheets API with `batchUpdate`, then calls `_add_validation_sheet` to append a `"✓ Validation"` tab with live formulas [Source 19]. These formulas use **hardcoded row numbers** that don't match the template.

---

## 2. Post-Processor Assumptions vs. Template Reality

The table below compares every row number the post-processor assumes [Source 3] against the actual row in the generated template [Source 13]. **Every single reference is wrong.**

| Financial Item | `post_processor.py` Row | Actual Template Row | Delta |
|---|---|---|---|
| **Income Statement** | | | |
| Revenue |

[Report truncated for context...]

ADDITIONAL CONTEXT/INSTRUCTIONS FROM USER:
You have full access to the Kaide-LABS/tracelight-safe-harbor repository. This is a FOLLOW-UP to a previous Oracle research session that diagnosed systematic row-number mismatches across the  
  entire pipeline.                                                                                                                                                                                
                                                                                                                                                                                                  
  ## Context From Previous Research
                                                                                                                                                                                                  
  The post-processor (safe-harbor/backend/agents/post_processor.py) and validation formula builder (_add_validation_sheet in safe-harbor/backend/main.py) both use hardcoded row numbers that only
   match one theoretical template layout. The actual templates (LBO, DCF, 3-Statement) each have different row layouts. We need to make BOTH components template-driven so they work with ANY     
  template automatically.                                                                                                                                                                    
                                                                                                                                                                                                  
  ## The Parser Already Has The Data                                                                                                                                                            
                                                                                                                                                                                                  
  The parser (safe-harbor/backend/excel_io/parser.py) already extracts section-qualified headers with row numbers for every cell. The parsed output contains cell_ref (e.g. "B4"), sheet_name,
  column_header (e.g. "SENIOR SECURED DEBT > Beginning Balance"), and period labels. This is the source of truth.                                                                                 
                                                                                                                                                                                                
  ## What I Need You To Research                                                                                                                                                                  
                                                                                                                                                                                                  
  ### 1. Row Map Builder Design
  Design a function that takes the parser's output and builds a universal row map like:                                                                                                           
  ```python                                                                                                                                                                                     
  {                                                                                                                                                                                               
      ("Income Statement", "revenue"): 2,
      ("Income Statement", "net_income"): 12,                                                                                                                                                     
      ("Debt Schedule", "senior_begin_bal"): 3,                                                                                                                                                 
      ("Balance Sheet", "total_assets"): 10,                                                                                                                                                      
      ...                                                                                                                                                                                         
  }                                                                                                                                                                                               
                                                                                                                                                                                                  
  Key challenge: the parser uses section-qualified headers like "SENIOR SECURED DEBT > Beginning Balance" while the post-processor needs canonical keys like "senior_begin_bal". Design the     
  normalization/matching strategy. Consider:                                                                                                                                                      
  - How to handle duplicate row labels across sections (e.g. "Beginning Balance" appears in Senior and Mezz)
  - How to distinguish formula rows from input rows (the solver must NEVER write to formula rows)                                                                                                 
  - How to handle templates that may have different section structures (LBO vs DCF vs 3-Statement)                                                                                              
                                                                                                                                                                                                  
  2. Post-Processor Refactor                                                                                                                                                                      
                                                                                                                                                                                                  
  Read the full post_processor.py simulate_period() function. For each hardcoded _get(g, SHEET, ROW) call:                                                                                        
  - Map it to the semantic meaning (e.g. _get(g, IS, 4) = "get Revenue from Income Statement")                                                                                                  
  - Show how it should be replaced with a row_map lookup                                                                                                                                          
  - Identify which rows are INPUT cells vs FORMULA cells — the solver must only write back to input cells                                                                                       
                                                                                                                                                                                                  
  Also analyze: does the simulate_period() logic itself need to change per template type? An LBO has debt tranches and leverage; a DCF has terminal value and WACC; a 3-Statement has working     
  capital cycle. Should there be separate simulation strategies, or can it be generalized?                                                                                                        
                                                                                                                                                                                                  
  3. Validation Builder Refactor                                                                                                                                                                  
                                                                                                                                                                                                
  Read the full _add_validation_sheet() function in main.py. For each hardcoded row reference:                                                                                                    
  - Map it to semantic meaning
  - Show the row_map lookup replacement                                                                                                                                                           
  - Identify which validation checks are LBO-specific vs universal                                                                                                                              
                                                                                                                                                                                                  
  Design a validation rule registry pattern:
  - Universal rules: BS Identity (Assets = Liab + Equity), CF Reconciliation, Margin Analysis                                                                                                     
  - Template-specific rules: Debt Rollforward (LBO only), IRR/MOIC checks (LBO only), DCF-specific checks                                                                                         
  - How does the system detect which template type it's dealing with and apply the right rules?          
                                                                                                                                                                                                  
  4. Interest Calculation Alignment                                                                                                                                                               
                                                                                                                                                                                                  
  The post-processor uses average balance method (Begin+End)/2 × Rate, but the LBO template uses Begin × Rate. Research:                                                                          
  - Read generate_templates.py to confirm how each template calculates interest                                                                                                                 
  - Should the solver detect the formula pattern from the template and match it?                                                                                                                  
  - Or should we standardize on one method?                                                                                                                                                     
                                                                                                                                                                                                  
  5. Writer Formula-Skip Problem                                                                                                                                                                  
                                                                                                                                                                                                  
  The writer (safe-harbor/backend/excel_io/writer.py) skips cells that contain formulas. The solver currently tries to write to formula cells (Retained Earnings, Beginning Cash). Research:      
  - For each template type, which cells are formula vs input?                                                                                                                                   
  - What is the minimal set of input cells the solver needs to modify to achieve convergence?                                                                                                     
  - Can the solver infer "this is a formula cell, don't write to it" from the parser output?                                                                                                    
                                                                                                                                                                                                  
  6. Concrete Implementation Plan                                                                                                                                                                 
   
  After all analysis, produce a DETAILED implementation plan with:                                                                                                                                
  - Exact file paths and function signatures                                                                                                                                                    
  - The row_map data structure definition                                                                                                                                                         
  - The normalization function for matching headers                                                                                                                                             
  - Code snippets for the refactored simulate_period() using row_map lookups
  - Code snippets for the refactored validation builder                                                                                                                                           
  - A template-type detection function                 
  - The validation rule registry structure                                                                                                                                                        
  - How to handle edge cases: missing rows, templates with extra sections, partial templates                                                                                                      
   
  Constraints                                                                                                                                                                                     
                                                                                                                                                                                                
  - Must work for LBO, DCF, and 3-Statement templates without any hardcoded row numbers                                                                                                           
  - The parser output is the ONLY source of truth for row layout                                                                                                                                
  - No virtual environments                                                                                                                                                                       
  - Formula cells must NEVER be overwritten                                                                                                                                                     
  - The solver's Python simulation must exactly match the template's Excel/Sheets formulas

Please conduct additional research to:
1. Explore any topics mentioned but not fully covered
2. Find more recent information if applicable
3. Dive deeper into the most important aspects
4. Verify and expand on key findings

Provide a comprehensive follow-up report that builds on the previous research.

---

## Research Report

## Executive Summary

**The parser already extracts every piece of data needed to eliminate all hardcoded row numbers — it's just never consumed.** The `post_process()` function receives `parsed_template` as a parameter but completely ignores it [Source 1]. Meanwhile, the validation builder in `_add_validation_sheet()` never receives template data at all [Source 3]. This report provides a complete architectural blueprint — with function signatures, data structures, normalization strategies, and code snippets — for making both components fully template-driven across LBO, DCF, and 3-Statement models.

---

## 1. Row Map Builder Design

### 1.1 The Parser's Output (Source of Truth)

The parser produces two separate lists per sheet: `input_cells` and `formula_cells` [Source 2]. Each entry carries:

```python
# input_cells entry
{"ref": "B2", "column_header": "Revenue", "period": "FY2020"}

# With section qualification for disambiguated items:
{"ref": "B3", "column_header": "SENIOR SECURED DEBT > Beginning Balance", "period": "FY2020"}

# formula_cells entry
{"ref": "B4", "formula": "=B2-B3", "column_header": "Gross Profit"}
```

The critical architectural insight: **section-qualified headers are only applied when a section context exists** — the parser tracks `current_section` and prepends it with `>` only when the row label would otherwise be ambiguous [Source 2]. For the LBO Debt Schedule, this means "Beginning Balance" under the "Senior Debt" section header becomes `"SENIOR SECURED DEBT > Beginning Balance"`, while "Beginning Balance" under "Mezzanine Debt" becomes `"MEZZANINE DEBT > Beginning Balance"`.

### 1.2 Canonical Alias Dictionary

The normalization challenge is mapping diverse qualified headers to stable canonical keys. I propose a two-layer approach: **exact match first, then fuzzy fallback**.

```python
# File: safe-harbor/backend/agents/row_map.py

import re
from typing import Optional

# ── Canonical alias dictionary ──────────────────────────────────────
# Maps (lowercase normalized header) → canonical key
# Section-qualified entries come first (higher specificity)
CANONICAL_ALIASES: dict[str, str] = {
    # ── Income Statement ──
    "revenue": "is_revenue",
    "sales": "is_revenue",
    "total revenue": "is_revenue",
    "cogs": "is_cogs",
    "cost of goods sold": "is_cogs",
    "cost of revenue": "is_cogs",
    "gross profit": "is_gross_profit",
    "sg&a": "is_sga",
    "sga": "is_sga",
    "selling general & administrative": "is_sga",
    "r&d": "is_rnd",
    "research and development": "is_rnd",
    "other operating expenses": "is_other_opex",
    "total operating expenses": "is_total_opex",
    "ebitda": "is_ebitda",
    "d&a": "is_da",
    "depreciation & amortization": "is_da",
    "depreciation": "is_da",
    "ebit": "is_ebit",
    "interest expense": "is_interest_expense",
    "total interest expense": "is_total_interest",
    "ebt": "is_ebt",
    "tax": "is_tax",
    "tax expense": "is_tax",
    "tax rate": "is_tax_rate",
    "net income": "is_net_income",

    # ── Balance Sheet ──
    "cash": "bs_cash",
    "cash and equivalents": "bs_cash",
    "accounts receivable": "bs_ar",
    "inventory": "bs_inventory",
    "other current assets": "bs_other_curr",
    "total current assets": "bs_total_curr_assets",
    "pp&e net": "bs_ppe_net",
    "ppe net": "bs_ppe_net",
    "goodwill": "bs_goodwill",
    "other non-current assets": "bs_other_noncurr",
    "total assets": "bs_total_assets",
    "accounts payable": "bs_ap",
    "accrued expenses": "bs_accrued",
    "current portion of debt": "bs_curr_debt",
    "total current liabilities": "bs_total_curr_liab",
    "senior debt": "bs_senior_debt",
    "mezzanine debt": "bs_mezz_debt",
    "debt": "bs_total_debt",  # 3-statement (single debt line)
    "total liabilities": "bs_total_liab",
    "common equity": "bs_common_equity",
    "retained earnings": "bs_retained_earnings",
    "total equity": "bs_total_equity",
    "total liabilities & equity": "bs_total_liab_equity",

    # ── Cash Flow ──
    "changes in working capital": "cf_wc_changes",
    "operating cf": "cf_ops",
    "capex": "cf_capex",
    "capital expenditures": "cf_capex",
    "investing cf": "cf_inv",
    "debt drawdowns": "cf_debt_draws",
    "debt repayments": "cf_debt_repay",
    "dividends": "cf_dividends",
    "financing cf": "cf_fin",
    "net change in cash": "cf_net_change",
    "beginning cash": "cf_begin_cash",
    "ending cash": "cf_end_cash",

    # ── Debt Schedule (section-qualified) ──
    "senior debt > beginning balance": "ds_senior_begin",
    "senior debt > drawdowns": "ds_senior_draw",
    "senior debt > repayments": "ds_senior_repay",
    "senior debt > ending balance": "ds_senior_end",
    "senior debt > interest rate": "ds_senior_rate",
    "senior debt > interest expense": "ds_senior_interest",
    "mezzanine debt > beginning balance": "ds_mezz_begin",
    "mezzanine debt > drawdowns": "ds_mezz_draw",
    "mezzanine debt > repayments": "ds_mezz_repay",
    "mezzanine debt > ending balance": "ds_mezz_end",
    "mezzanine debt > interest rate": "ds_mezz_rate",
    "mezzanine debt > interest expense": "ds_mezz_interest",
    "total interest expense": "ds_total_interest",
    "total ending debt": "ds_total_debt",

    # ── Returns Analysis ──
    "entry ev": "ra_entry_ev",
    "exit multiple": "ra_exit_multiple",
    "exit ev": "ra_exit_ev",
    "net debt at exit": "ra_net_debt",
    "exit equity": "ra_exit_equity",
    "equity invested": "ra_equity_invested",
    "moic": "ra_moic",
    "irr": "ra_irr",

    # ── DCF-specific ──
    "segment a revenue": "dcf_seg_a_rev",
    "segment b revenue": "dcf_seg_b_rev",
    "total revenue": "dcf_total_rev",
    "wacc": "dcf_wacc",
    "terminal growth rate": "dcf_terminal_growth",
    "terminal value": "dcf_terminal_value",
}
```

### 1.3 Normalization Function

The key challenge is that the parser uses section headers like `"SENIOR SECURED DEBT"` (all caps from the template's `_is_section_header` detection [Source 2]), while the generate_templates.py script creates sections named `"Senior Debt"` and `"Mezzanine Debt"` [Source 8]. The normalizer must handle both:

```python
def _normalize_header(raw_header: str) -> str:
    """Normalize a parser-produced header for canonical matching.
    
    Handles:
    - Case folding: "SENIOR SECURED DEBT > Beginning Balance" → "senior secured debt > beginning balance"
    - Whitespace normalization
    - Common variations: "Senior Debt" vs "SENIOR SECURED DEBT"
    """
    h = raw_header.strip().lower()
    # Normalize section separators
    h = re.sub(r'\s*>\s*', ' > ', h)
    # Normalize "senior secured debt" → "senior debt" for matching
    h = h.replace("senior secured debt", "senior debt")
    h = h.replace("senior secured", "senior")
    # Strip trailing whitespace within segments
    h = re.sub(r'\s+', ' ', h)
    return h


def _resolve_canonical(normalized_header: str) -> Optional[str]:
    """Look up canonical key. Try exact match, then substring match."""
    if normalized_header in CANONICAL_ALIASES:
        return CANONICAL_ALIASES[normalized_header]
    # Fuzzy fallback: check if any alias is a substring
    for alias, canonical in CANONICAL_ALIASES.items():
        if alias in normalized_header or normalized_header in alias:
            return canonical
    return None
```

### 1.4 The `build_row_map` Function

```python
def build_row_map(parsed_template: dict) -> dict:
    """Build universal row map from parser output.
    
    Returns:
        {
            "row_map": {
                ("Income Statement", "is_revenue"): 2,
                ("Debt Schedule", "ds_senior_begin"): 3,
                ...
            },
            "formula_rows": {
                ("Income Statement", 4),  # Gross Profit
                ("Balance Sheet", 19),    # Retained Earnings
                ...
            },
            "input_rows": {
                ("Income Statement", 2),  # Revenue
                ("Income Statement", 3),  # COGS
                ...
            },
            "sheet_names": {
                "is": "Income Statement",
                "bs": "Balance Sheet",
                "cf": "Cash Flow",       # actual name, not "Cash Flow Statement"
                "ds": "Debt Schedule",
                "ra": "Returns Analysis",
            },
            "template_type": "LBO",  # or "DCF" or "3-statement"
            "periods": ["FY2020", "FY2021", ...],
            "col_letters": ["B", "C", "D", "E", "F", "G"],
        }
    """
    row_map = {}
    formula_rows = set()
    input_rows = set()
    sheet_names = {}
    periods = []

    for sheet in parsed_template["sheets"]:
        sname = sheet["name"]
        
        # Detect sheet role
        s_lower = sname.lower()
        if "income" in s_lower: sheet_names["is"] = sname
        elif "balance" in s_lower: sheet_names["bs"] = sname
        elif "cash flow" in s_lower: sheet_names["cf"] = sname
        elif "debt" in s_lower: sheet_names["ds"] = sname
        elif "return" in s_lower: sheet_names["ra"] = sname
        elif "revenue build" in s_lower: sheet_names["rev_build"] = sname
        elif "dcf" in s_lower or "valuation" in s_lower: sheet_names["dcf"] = sname
        elif "free cash" in s_lower: sheet_names["fcf"] = sname

        # Extract periods from first sheet that has them
        if not periods and sheet.get("temporal_headers"):
            periods = sheet["temporal_headers"]

        # Process input cells
        for cell in sheet["input_cells"]:
            ref = cell["ref"]
            row_num = int(re.search(r'\d+', ref).group())
            header = cell["column_header"]
            canonical = _resolve_canonical(_normalize_header(header))
            
            if canonical:
                key = (sname, canonical)
                if key not in row_map:
                    row_map[key] = row_num
            
            input_rows.add((sname, row_num))

        # Process formula cells
        for cell in sheet["formula_cells"]:
            ref = cell["ref"]
            row_num = int(re.search(r'\d+', ref).group())
            header = cell["column_header"]
            canonical = _resolve_canonical(_normalize_header(header))
            
            if canonical:
                key = (sname, canonical)
                if key not in row_map:
                    row_map[key] = row_num
            
            formula_rows.add((sname, row_num))

    # Derive column letters from periods
    col_letters = [chr(66 + i) for i in range(len(periods))]  # B, C, D, ...

    # Detect template type
    template_type = _detect_template_type(sheet_names)

    return {
        "row_map": row_map,
        "formula_rows": formula_rows,
        "input_rows": input_rows,
        "sheet_names": sheet_names,
        "template_type": template_type,
        "periods": periods,
        "col_letters": col_letters,
    }


def _detect_template_type(sheet_names: dict) -> str:
    """Detect template type from available sheets."""
    if "ds" in sheet_names and "ra" in sheet_names:
        return "LBO"
    elif "dcf" in sheet_names or "fcf" in sheet_names:
        return "DCF"
    elif "is" in sheet_names and "bs" in sheet_names:
        return "3-statement"
    return "unknown"
```

### 1.5 How This Handles Each Challenge

**Duplicate row labels**: The parser's section-qualified headers (`"Senior Debt > Beginning Balance"` vs `"Mezzanine Debt > Beginning Balance"`) map to distinct canonical keys (`ds_senior_begin` vs `ds_mezz_begin`) [Source 2].

**Formula vs input distinction**: The parser already separates these into `input_cells` and `formula_cells` lists. The row map stores both in `formula_rows` and `input_rows` sets, allowing the solver to check `(sheet_name, row) in formula_rows` before writing [Source 2].

**Different template structures**: The canonical alias dictionary covers all three template types. For a 3-Statement model (no Debt Schedule, no Returns Analysis [Source 8]), the debt-related keys simply won't exist in `row_map`, and the template type detection returns `"3-statement"`, gating which simulation strategy to use.

---

## 2. Post-Processor Refactor

### 2.1 Complete Hardcoded Row Mapping

Every `_get()` and `_set()` call in `simulate_period()` [Source 1] uses hardcoded row numbers. Here is the **complete semantic mapping** against the actual LBO template from `generate_templates.py` [Source 8]:

| Solver Call | Semantic Meaning | Solver Row | Actual LBO Row | Cell Type |
|---|---|---|---|---|
| `_get(g, IS, 4)` | Revenue | 4 | **2** | INPUT |
| `_get(g, IS, 5)` | COGS | 5 | **3** | INPUT |
| `_set(g, IS, 6)` | Gross Profit | 6 | **4** | FORMULA |
| `_get(g, IS, 9)` | SG&A | 9 | **5** | INPUT |
| `_get(g, IS, 10)` | R&D | 10 | **N/A** | ❌ DOESN'T EXIST |
| `_get(g, IS, 11)` | Other OpEx | 11 | **N/A** | ❌ DOESN'T EXIST |
| `_set(g, IS, 12)` | Total OpEx | 12 | **N/A** | ❌ DOESN'T EXIST |
| `_set(g, IS, 14)` | EBITDA | 14 | **6** | FORMULA |
| `_get(g, IS, 17)` | D&A | 17 | **7** | INPUT |
| `_set(g, IS, 18)` | EBIT | 18 | **8** | FORMULA |
| `_set(g, IS, 21)` | Senior Interest | 21 | **N/A** | ❌ (single Interest row 9) |
| `_set(g, IS, 22)` | Mezz Interest | 22 | **N/A** | ❌ |
| `_set(g, IS, 23)` | Total Interest | 23 | **9** | FORMULA |
| `_set(g, IS, 25)` | EBT | 25 | **10** | FORMULA |
| `_get(g, IS, 26)` | Tax Rate | 26 | **N/A** | ❌ (Tax is row 11, not rate) |
| `_set(g, IS, 27)` | Tax Expense | 27 | **11** | INPUT |
| `_set(g, IS, 29)` | Net Income | 29 | **12** | FORMULA |

| Solver Call | Semantic Meaning | Solver Row | Actual LBO Row | Cell Type |
|---|---|---|---|---|
| `_get(g, BS, 5)` | Cash | 5 | **2** | INPUT |
| `_get(g, BS, 6)` | Accounts Receivable | 6 | **3** | INPUT |
| `_get(g, BS, 7)` | Inventory | 7 | **4** | INPUT |
| `_get(g, BS, 8)` | Other Current Assets | 8 | **5** | INPUT |
| `_set(g, BS, 9)` | Total Current Assets | 9 | **6** | FORMULA |
| `_get(g, BS, 11)` | PP&E Gross | 11 | **N/A** | ❌ (only PP&E Net at row 7) |
| `_get(g, BS, 12)` | Accum Depreciation | 12 | **N/A** | ❌ |
| `_set(g, BS, 13)` | PP&E Net | 13 | **7** | INPUT |
| `_get(g, BS, 14-17)` | Intangibles, Goodwill, etc. | 14-17 | **8-9** | INPUT |
| `_set(g, BS, 18)` | Non-Current Assets | 18 | **N/A** | ❌ (rolled into Total Assets) |
| `_set(g, BS, 20)` | Total Assets | 20 | **10** | FORMULA |
| `_get(g, BS, 23)` | Accounts Payable | 23 | **11** | INPUT |
| `_get(g, BS, 24)` | Accrued Expenses | 24 | **12** | INPUT |
| `_get(g, BS, 25)` | Deferred Revenue | 25 | **N/A** | ❌ |
| `_get(g, BS, 26)` | Current Debt | 26 | **13** | INPUT |
| `_set(g, BS, 27)` | Total Current Liab | 27 | **14** | FORMULA |
| `_set(g, BS, 29)` | Senior Debt | 29 | **15** | INPUT |
| `_set(g, BS, 30)` | Mezz Debt | 30 | **16** | INPUT |
| `_set(g, BS, 31)` | Total LT Debt | 31 | **N/A** | ❌ |
| `_set(g, BS, 34)` | Non-Current Liab | 34 | **N/A** | ❌ |
| `_set(g, BS, 36)` | Total Liabilities | 36 | **17** | FORMULA |
| `_get(g, BS, 39)` | Common Equity | 39 | **18** | INPUT |
| `_set(g, BS, 40)` | Retained Earnings | 40 | **19** | **FORMULA** ⚠️ |
| `_get(g, BS, 41)` | AOCI | 41 | **N/A** | ❌ |
| `_set(g, BS, 42)` | Total Equity | 42 | **20** | FORMULA |
| `_set(g, BS, 44)` | Total L&E | 44 | **21** | FORMULA |
| `_set(g, BS, 45)` | Check Row | 45 | **N/A** | ❌ |

| Solver Call | Semantic Meaning | Solver Row | Actual CF Row | Cell Type |
|---|---|---|---|---|
| `_set(g, CF, 5)` | Net Income | 5 | **2** | FORMULA |
| `_set(g, CF, 6)` | D&A Add-back | 6 | **3** | FORMULA |
| `_set(g, CF, 9-13)` | 5 WC items | 9-13 | **4** (single) | INPUT |
| `_set(g, CF, 14)` | Net WC | 14 | **N/A** | ❌ |
| `_set(g, CF, 16)` | Operating CF | 16 | **5** | FORMULA |
| `_get(g, CF, 19)` | CapEx | 19 | **6** | INPUT |
| `_set(g, CF, 22)` | Investing CF | 22 | **7** | FORMULA |
| `_set(g, CF, 25)` | Debt Draws | 25 | **8** | INPUT |
| `_set(g, CF, 26)` | Debt Repay | 26 | **9** | INPUT |
| `_get(g, CF, 27)` | Dividends | 27 | **10** | INPUT |
| `_set(g, CF, 28)` | Financing CF | 28 | **11** | FORMULA |
| `_set(g, CF, 30)` | Net Change | 30 | **12** | FORMULA |
| `_set(g, CF, 31)` | Beginning Cash | 31 | **13** | **FORMULA** ⚠️ |
| `_set(g, CF, 32)` | Ending Cash | 32 | **14** | FORMULA |

**The solver also uses `CF = "Cash Flow Statement"` but the actual sheet is named `"Cash Flow"` [Source 8].** This means every `_get(g, CF, ...)` call returns `0.0` (the default) because no grid entries exist for a sheet that doesn't exist.

### 2.2 The `parsed_template` Parameter Is Received But Ignored

This is the most critical architectural finding. In `orchestrator.py` [Source 11], the post-processor is called:

```python
fixed_cells = post_process(raw_cells, parsed)  # parsed_template IS passed
```

But in `post_processor.py` [Source 1], the function signature accepts it and does nothing:

```python
def post_process(cells, parsed_template=None):
    # ... never references parsed_template
```

**The fix is straightforward: call `build_row_map(parsed_template)` at the top of `post_process()` and use it everywhere.**

### 2.3 Refactored `simulate_period()` Using Row Map

The simulation logic needs to be template-type-aware. The LBO has a circular reference chain (Interest → NI → CF → Debt Repayment → Interest) that DCF and 3-Statement models don't have. I propose a strategy pattern:

```python
def simulate_period_lbo(grid, prev, senior_repay, mezz_repay, rm, default_tax_rate=0.25):
    """LBO simulation using row_map lookups. rm = row_map dict."""
    g = grid
    IS = rm["sheet_names"]["is"]
    BS = rm["sheet_names"]["bs"]
    CF = rm["sheet_names"]["cf"]
    DS = rm["sheet_names"]["ds"]
    
    def _row(sheet, canonical):
        """Look up row number from row_map."""
        return rm["row_map"].get((sheet, canonical))
    
    def _is_input(sheet, row):
        """Check if a cell is an input (writable) cell."""
        return (sheet, row) in rm["input_rows"]
    
    # ── 0. Cross-period linkages ──
    # Beginning Balance(t) = Ending Balance(t-1) for debt tranches
    r_sen_end = _row(DS, "ds_senior_end")
    r_sen_begin = _row(DS, "ds_senior_begin")
    if r_sen_end and r_sen_begin:
        prev_sen_end = _get(prev, DS, r_sen_end, default=_get(prev, DS, r_sen_begin))
        if _is_input(DS, r_sen_begin):
            _set(g, DS, r_sen_begin, prev_sen_end)
    
    r_mezz_end = _row(DS, "ds_mezz_end")
    r_mezz_begin = _row(DS, "ds_mezz_begin")
    if r_mezz_end and r_mezz_begin:
        prev_mezz_end = _get(prev, DS, r_mezz_end, default=_get(prev, DS, r_mezz_begin))
        if _is_input(DS, r_mezz_begin):
            _set(g, DS, r_mezz_begin, prev_mezz_end)
    
    # ── 1. Plug repayment guesses ──
    r_sen_repay = _row(DS, "ds_senior_repay")
    r_mezz_repay = _row(DS, "ds_mezz_repay")
    if r_sen_repay and _is_input(DS, r_sen_repay):
        _set(g, DS, r_sen_repay, senior_repay)
    if r_mezz_repay and _is_input(DS, r_mezz_repay):
        _set(g, DS, r_mezz_repay, mezz_repay)
    
    # ── 2. Debt Schedule ──
    sen_begin = _get(g, DS, r_sen_begin) if r_sen_begin else 0
    r_sen_draw = _row(DS, "ds_senior_draw")
    sen_draw = _get(g, DS, r_sen_draw) if r_sen_draw else 0
    sen_end = sen_begin + sen_draw - senior_repay
    
    r_sen_rate = _row(DS, "ds_senior_rate")
    sen_rate = _get(g, DS, r_sen_rate) if r_sen_rate else 0
    # CRITICAL: Use beginning balance × rate (matches template formula)
    sen_interest = sen_begin * sen_rate
    
    mezz_begin = _get(g, DS, r_mezz_begin) if r_mezz_begin else 0
    r_mezz_draw = _row(DS, "ds_mezz_draw")
    mezz_draw = _get(g, DS, r_mezz_draw) if r_mezz_draw else 0
    mezz_end = mezz_begin + mezz_draw - mezz_repay
    
    r_mezz_rate = _row(DS, "ds_mezz_rate")
    mezz_rate = _get(g, DS, r_mezz_rate) if r_mezz_rate else 0
    mezz_interest = mezz_begin * mezz_rate  # BEGIN × RATE
    
    total_interest = sen_interest + mezz_interest
    
    # ── 3. Income Statement (read inputs, simulate formulas) ──
    r_rev = _row(IS, "is_revenue")
    r_cogs = _row(IS, "is_cogs")
    revenue = _get(g, IS, r_rev) if r_rev else 0
    cogs = _get(g, IS, r_cogs) if r_cogs else 0
    gross = revenue - cogs
    
    r_sga = _row(IS, "is_sga")
    sga = _get(g, IS, r_sga) if r_sga else 0
    ebitda = gross - sga  # Template: =Gross Profit - SG&A
    
    r_da = _row(IS, "is_da")
    da = _get(g, IS, r_da) if r_da else 0
    ebit = ebitda - da  # Template: =EBITDA - D&A
    
    ebt = ebit - total_interest  # Template: =EBIT - Interest
    
    r_tax = _row(IS, "is_tax")
    tax = _get(g, IS, r_tax) if r_tax else (max(0, ebt * default_tax_rate))
    
    net_income = ebt - tax  # Template: =EBT - Tax
    
    # ── 4. Cash Flow ──
    r_wc = _row(CF, "cf_wc_changes")
    wc_changes = _get(g, CF, r_wc) if r_wc else 0
    
    ops_cf = net_income + da + wc_changes  # Template: =NI + D&A + WC
    
    r_capex = _row(CF, "cf_capex")
    capex = _get(g, CF, r_capex) if r_capex else 0
    inv_cf = -capex  # Template: =-CapEx
    
    r_draws = _row(CF, "cf_debt_draws")
    r_repay = _row(CF, "cf_debt_repay")
    r_div = _row(CF, "cf_dividends")
    draws = _get(g, CF, r_draws) if r_draws else 0
    repay = _get(g, CF, r_repay) if r_repay else 0
    dividends = _get(g, CF, r_div) if r_div else 0
    fin_cf = draws - repay - dividends  # Template: =Draws - Repay - Div
    
    net_change = ops_cf + inv_cf + fin_cf
    
    # Beginning Cash is a FORMULA in the template — DON'T write to it
    # Instead, read it from the grid (set via cross-period linkage or prior period)
    r_begin = _row(CF, "cf_begin_cash")
    r_end = _row(CF, "cf_end_cash")
    begin_cash = _get(prev, CF, r_end, default=_get(prev, BS, _row(BS, "bs_cash"))) if r_end else 0
    end_cash = begin_cash + net_change
    
    # ── 5. Balance Sheet (simulate formulas for convergence check) ──
    # The solver doesn't WRITE to formula cells — it just checks convergence
    r_cash = _row(BS, "bs_cash")
    # Cash on BS should equal ending cash from CF
    # But Cash is an INPUT on BS — this is where we can write!
    if r_cash and _is_input(BS, r_cash):
        _set(g, BS, r_cash, end_cash)
    
    # Compute total assets / liabilities for convergence monitoring
    # ... (similar row_map lookups for each BS item)
    
    # ── 6. Derive new repayment from available cash ──
    cash_before_repay = end_cash + senior_repay + mezz_repay
    new_sen = min(sen_begin + sen_draw, max(0.0, cash_before_repay))
    remaining = max(0.0, cash_before_repay - new_sen)
    new_mezz = min(mezz_begin + mezz_draw, max(0.0, remaining))
    
    return g, new_sen, new_mezz
```

### 2.4 Should Simulation Logic Vary Per Template Type?

**Yes, but minimally.** Analysis of the three template types from `generate_templates.py` [Source 8]:

| Aspect | LBO | 3-Statement | DCF |
|---|---|---|---|
| Circular reference? | Yes: Interest ↔ Debt ↔ CF ↔ NI | Partial: if interest is formula | No |
| Debt Schedule sheet? | Yes (2 tranches) | No (single "Debt" on BS) | No |
| Working capital | Single input cell | Single input cell | N/A (separate FCF sheet) |
| Returns sheet? | Yes (IRR/MOIC) | No | No (has DCF Valuation) |
| Solver needed? | Full fixed-point | Optional (simple) | None |

**Recommendation**: Three simulation strategies:

```python
SIMULATION_STRATEGIES = {
    "LBO": simulate_period_lbo,      # Full IS→DS→CF→BS with Banach iteration
    "3-statement": simulate_period_3s, # Simplified: no debt tranches, optional interest
    "DCF": None,                       # No circular references, skip solver entirely
}
```

For `"DCF"`, the post-processor should simply pass through — the DCF has no circular references because WACC and terminal value are independent of the debt structure [Source 8].

---

## 3. Validation Builder Refactor

### 3.1 Complete Hardcoded Reference Audit

The `_add_validation_sheet()` function in `main.py` [Source 3] contains **38 hardcoded row references** across 7 sections. Here is the complete mapping:

**Section 1: Balance Sheet Identity**
| Formula Reference | Semantic Meaning | Hardcoded Row | Actual LBO Row |
|---|---|---|---|
| `'Balance Sheet'!{c}20` | Total Assets | 20 | **10** |
| `'Balance Sheet'!{c}36` | Total Liabilities | 36 | **17** |
| `'Balance Sheet'!{c}42` | Total Equity | 42 | **20** |

**Section 2: Margin Analysis**
| Formula Reference | Semantic Meaning | Hardcoded Row | Actual LBO Row |
|---|---|---|---|
| `'Income Statement'!{c}4` | Revenue | 4 | **2** |
| `'Income Statement'!{c}6` | Gross Profit | 6 | **4** |
| `'Income Statement'!{c}14` | EBITDA | 14 | **6** |
| `'Income Statement'!{c}29` | Net Income | 29 | **12** |
| `'Income Statement'!{c}7` | Gross Margin (!) | 7 | **N/A** (no margin row) |

**Section 3: Revenue Growth**
- Uses `'Income Statement'!{c}4` (should be row 2)
- **Bug**: `len(rows)` Python variable embedded in formula string → produces `#NAME?` error [Source 3]
- **Bug**: No IFERROR wrapper for FY2020 → `#ERROR!` div-by-zero [Source 3]

**Section 4: Cash Flow Reconciliation**
- **References `'Cash Flow Statement'` — sheet doesn't exist!** [Source 3]
- Template uses `'Cash Flow'` [Source 8]
- `has_cf = 'Cash Flow Statement' in sheet_names` → **always `False`** → entire section silently skipped

**Section 5: Debt Schedule**
| Formula Reference | Semantic Meaning | Hardcoded Row | Actual LBO Row |
|---|---|---|---|
| `'Debt Schedule'!{c}5` | Senior Begin Balance | 5 | **3** |
| `'Debt Schedule'!{c}6` | Drawdowns | 6 | **4** |
| `'Debt Schedule'!{c}7` | Repayments | 7 | **5** |
| `'Debt Schedule'!{c}9` | Ending Balance | 9 | **6** |

**Bug in rollforward check formula**: `End - (Begin + Draw + Repay)` should be `End - (Begin + Draw - Repay)` since repayments reduce the balance. The formula uses `+` for all three which is algebraically wrong [Source 3].

**Section 6: Cross-Sheet Linkage**
| Formula Reference | Semantic Meaning | Hardcoded Row | Actual Row |
|---|---|---|---|
| `'Income Statement'!{c}17` | D&A | 17 | **7** |
| `'Cash Flow Statement'!{c}6` | D&A Add-back | 6 | **3** (and wrong sheet name) |
| `'Income Statement'!{c}23` | Total Interest | 23 | **9** |
| `'Debt Schedule'!{c}27` | DS Total Interest | 27 | **16** |

**Section 7: Statistical Distribution**
- References `'Income Statement'!{cols[0]}4:{cols[-1]}4` for Revenue (should be row 2)
- References `'Income Statement'!{cols[0]}7:{cols[-1]}7` for Gross Margin — **row 7 is D&A, not a margin row** [Source 8]

### 3.2 Refactored Validation Builder

```python
def _add_validation_sheet(sheets_svc, spreadsheet_id: str, wb, parsed_template: dict = None):
    """Add validation sheet with template-driven row references."""
    
    # Build row map from parser data
    if parsed_template:
        rm = build_row_map(parsed_template)
    else:
        # Fallback: try to infer from workbook
        rm = _infer_row_map_from_wb(wb)
    
    sheet_names = rm["sheet_names"]
    row_map = rm["row_map"]
    template_type = rm["template_type"]
    
    # Helper: get actual sheet name and row for a canonical key
    def _ref(sheet_key, canonical, col):
        """Build a cell reference like 'Income Statement'!B2"""
        sname = sheet_names.get(sheet_key)
        row = row_map.get((sname, canonical)) if sname else None
        if sname and row:
            return f"'{sname}'!{col}{row}"
        return None

    # ... detect periods (same as before) ...
    
    # Build sections using row_map lookups
    rows = []
    
    # ── Section 1: Balance Sheet Identity (UNIVERSAL) ──
    if "bs" in sheet_names:
        bs = sheet_names["bs"]
        r_ta = row_map.get((bs, "bs_total_assets"))
        r_tl = row_map.get((bs, "bs_total_liab"))
        r_te = row_map.get((bs, "bs_total_equity"))
        
        if all([r_ta, r_tl, r_te]):
            rows.append({"values": _header("1. BALANCE SHEET IDENTITY")})
            rows.append({"values": _formula_row("Total Assets",
                [f"='{bs}'!{c}{r_ta}" for c in cols])})
            rows.append({"values": _formula_row("Total Liabilities",
                [f"='{bs}'!{c}{r_tl}" for c in cols])})
            rows.append({"values": _formula_row("Total Equity",
                [f"='{bs}'!{c}{r_te}" for c in cols])})
            rows.append({"values": _formula_row("Δ (A - L - E)",
                [f"='{bs}'!{c}{r_ta}-('{bs}'!{c}{r_tl}+'{bs}'!{c}{r_te})" for c in cols])})
            rows.append({"values": _status_row("✓ Status",
                [f'=IF(ABS(\'{bs}\'!{c}{r_ta}-(\'{bs}\'!{c}{r_tl}+\'{bs}\'!{c}{r_te}))<1,"PASS","FAIL")' for c in cols])})
    
    # ── Section 3: Revenue Growth (UNIVERSAL, with edge case fix) ──
    if "is" in sheet_names:
        is_name = sheet_names["is"]
        r_rev = row_map.get((is_name, "is_revenue"))
        if r_rev and len(cols) > 1:
            # FIXED: IFERROR wrapper for base year, skip first period
            growth_formulas = [""]  # blank for first period (no prior year)
            for i in range(1, len(cols)):
                growth_formulas.append(
                    f"=IFERROR('{is_name}'!{cols[i]}{r_rev}/'{is_name}'!{cols[i-1]}{r_rev}-1,\"N/A\")"
                )
            rows.append({"values": _formula_row("YoY Growth %", growth_formulas)})
    
    # ── Section 5: Debt Rollforward (LBO ONLY) ──
    if template_type == "LBO" and "ds" in sheet_names:
        ds = sheet_names["ds"]
        r_sb = row_map.get((ds, "ds_senior_begin"))
        r_sd = row_map.get((ds, "ds_senior_draw"))
        r_sr = row_map.get((ds, "ds_senior_repay"))
        r_se = row_map.get((ds, "ds_senior_end"))
        
        if all([r_sb, r_sd, r_sr, r_se]):
            rows.append({"values": _header("5. DEBT SCHEDULE — SENIOR")})
            rows.append({"values": _formula_row("Beginning Balance",
                [f"='{ds}'!{c}{r_sb}" for c in cols])})
            rows.append({"values": _formula_row("+ Drawdowns",
                [f"='{ds}'!{c}{r_sd}" for c in cols])})
            rows.append({"values": _formula_row("- Repayments",
                [f"='{ds}'!{c}{r_sr}" for c in cols])})
            rows.append({"values": _formula_row("= Ending Balance",
                [f"='{ds}'!{c}{r_se}" for c in cols])})
            # FIXED: Correct rollforward formula (Begin + Draw - Repay = End)
            rows.append({"values": _formula_row("Δ Rollforward",
                [f"='{ds}'!{c}{r_se}-('{ds}'!{c}{r_sb}+'{ds}'!{c}{r_sd}-'{ds}'!{c}{r_sr})" for c in cols])})
            rows.append({"values": _status_row("✓ Status",
                [f'=IF(ABS(\'{ds}\'!{c}{r_se}-(\'{ds}\'!{c}{r_sb}+\'{ds}\'!{c}{r_sd}-\'{ds}\'!{c}{r_sr}))<1,"PASS","FAIL")' for c in cols])})
```

### 3.3 Validation Rule Registry

```python
# File: safe-harbor/backend/agents/validation_rules.py

VALIDATION_REGISTRY = {
    "universal": [
        "bs_identity",      # Assets = Liabilities + Equity
        "margin_analysis",   # Gross/EBITDA/Net margins in range
        "revenue_growth",    # YoY growth with base-year handling
    ],
    "LBO": [
        "debt_rollforward_senior",  # Begin + Draw - Repay = End (Senior)
        "debt_rollforward_mezz",    # Begin + Draw - Repay = End (Mezz)
        "cf_reconciliation",        # End Cash = Begin + Net Change
        "cross_sheet_da",           # IS D&A = CF D&A add-back
        "cross_sheet_interest",     # IS Interest = DS Total Interest
        "cross_sheet_ni",           # IS Net Income = CF Net Income
        "irr_moic_check",           # IRR/MOIC reasonable ranges
    ],
    "DCF": [
        "ufcf_reconciliation",      # EBIT(1-t) + D&A - CapEx - ΔNWC = UFCF
        "terminal_value_check",     # TV = FCF*(1+g)/(WACC-g)
        "ev_bridge",                # EV = PV(FCFs) + PV(TV)
    ],
    "3-statement": [
        "cf_reconciliation",
        "cross_sheet_da",
        "cross_sheet_ni",
    ],
}

def get_validation_rules(template_type: str) -> list[str]:
    """Return the list of validation rule IDs for a given template type."""
    rules = list(VALIDATION_REGISTRY["universal"])
    rules.extend(VALIDATION_REGISTRY.get(template_type, []))
    return rules
```

---

## 4. Interest Calculation Alignment

### 4.1 Template Uses Beginning Balance × Rate

From `generate_templates.py` [Source 8], the LBO Debt Schedule interest formula is:

```python
elif item == "Interest Expense":
    cell.value = f"={col_letter}{i-5}*{col_letter}{i-1}"
    # For Senior: Interest Expense at row 8 → =B3*B7 (Begin Balance × Rate)
    # For Mezz:   Interest Expense at row 15 → =B10*B14 (Begin Balance × Rate)
```

The formula `=B3*B7` means **Beginning Balance × Interest Rate**. This is a **beginning-of-period convention** — common in leveraged finance because it avoids the circular reference that average balance creates.

### 4.2 Solver Uses Average Balance × Rate (WRONG)

From `post_processor.py` [Source 1]:

```python
sen_avg = (sen_begin + sen_end) / 2.0
_set(g, DS, 12, sen_avg)          # Average balance row (doesn't exist in template!)
sen_interest = sen_avg * sen_rate  # WRONG: should be sen_begin * sen_rate
```

This creates a **systematic error**: the solver computes a different interest figure than the template formula will produce. Since interest flows into Net Income → Cash Flow → debt repayment capacity, this error propagates through the entire circular reference chain.

### 4.3 Recommendation: Match the Template

**The solver should use beginning balance × rate.** This has three advantages:
1. **Matches the template** — the Python simulation produces the exact same result as the Excel/Sheets formula
2. **Eliminates the interest circularity** — interest depends only on beginning balance (known) and rate (input), not on ending balance (which depends on interest)
3. **Simplifies the Banach iteration** — fewer circular dependencies means faster convergence

The refactored solver code (shown in Section 2.3 above) already implements this fix:

```python
sen_interest = sen_begin * sen_rate  # BEGIN × RATE, matching template
```

### 4.4 Should the Solver Auto-Detect the Formula Pattern?

**No — this is over-engineering for the demo.** The three templates all use beginning-balance interest. If a custom template uses average-balance, the solver can be extended later. For now, standardize on beginning-balance to match the built-in templates.

---

## 5. Writer Formula-Skip Problem

### 5.1 The Problem

The writer [Source 9] explicitly skips any cell whose existing value starts with `=`:

```python
existing_val = cell.value
if isinstance(existing_val, str) and existing_val.startswith("="):
    continue  # SKIP — formula cell preserved
```

This is **correct behavior** — formula cells should never be overwritten because they contain the inter-sheet references that make the model work. The problem is that the solver tries to write to cells that are formulas in the template.

### 5.2 Which Cells the Solver Tries to Write to (But Can't)

| Cell | Solver Action | Template Cell Type | Writer Behavior |
|---|---|---|---|
| Retained Earnings (BS row 19) | `_set(g, BS, 40, retained)` | **FORMULA**: `=prev_RE + NI` | **SKIPPED** |
| Beginning Cash (CF row 13) | `_set(g, CF, 31, prev_end_cash)` | **FORMULA**: `=prev_EndCash` | **SKIPPED** |
| Ending Balance (DS rows 6, 13) | `_set(g, DS, 9, sen_end)` | **FORMULA**: `=Begin+Draw-Repay` | **SKIPPED** |
| All IS computed rows | `_set(g, IS, ...)` for 10+ rows | **FORMULA** | **SKIPPED** |
| All CF computed rows | `_set(g, CF, ...)` for 8+ rows | **FORMULA** | **SKIPPED** |

### 5.3 The Minimal Set of Input Cells the Solver Needs to Modify

For the LBO template, the solver's circular reference resolution only needs to adjust these **input cells**:

| Cell | Sheet | Row | Why |
|---|---|---|---|
| **Senior Repayments** | Debt Schedule | 5 | Determined by cash available after convergence |
| **Mezz Repayments** | Debt Schedule | 12 | Same |
| **Debt Repayments** | Cash Flow | 9 | Must match DS senior + mezz repayments |
| **Debt Drawdowns** | Cash Flow | 8 | Must match DS draws |
| **Cash** | Balance Sheet | 2 | Must equal CF Ending Cash (for t=0 plug) |
| **D&A** | Income Statement | 7 | Sign correction (positive → negative if needed) |
| **Tax** | Income Statement | 11 | Ensure consistency with computed EBT |

**Retained Earnings and Beginning Cash are both formulas** — the solver should NOT try to write to them. Instead, the solver's role is to ensure that the **input cells** it CAN write to will cause the formulas to converge to correct values.

### 5.4 How the Solver Can Detect Formula Cells

The parser already provides this information. The `build_row_map()` function populates `formula_rows`:

```python
def _is_writable(rm, sheet_name, row):
    """Check if a cell can be written to (is an input, not a formula)."""
    return (sheet_name, row) in rm["input_rows"]
```

The refactored `post_process()` should use this check before every write-back:

```python
# Phase 3: Write back ONLY writable input cells
for t in range(6):
    g = period_grids[t]
    col = PERIOD_TO_COL[t]
    
    # Senior Repayments
    r_sr = rm["row_map"].get((DS, "ds_senior_repay"))
    if r_sr and _is_writable(rm, DS, r_sr):
        idx = cell_index.get((DS, r_sr, t))
        if idx is not None:
            output[idx]["value"] = round(abs(_get(g, DS, r_sr)), 2)
    
    # DON'T write to Retained Earnings — it's a formula!
    # DON'T write to Beginning Cash — it's a formula!
```

---

## 6. Concrete Implementation Plan

### Priority 1: Sheet Name Fix (5 minutes, immediate impact)

**File**: `safe-harbor/backend/agents/post_processor.py` line 10 [Source 1]
**Change**: `CF = "Cash Flow Statement"` → `CF = "Cash Flow"`
**Also**: `safe-harbor/backend/main.py` — `has_cf = 'Cash Flow Statement' in sheet_names` → `has_cf = 'Cash Flow' in sheet_names` or better: `has_cf = any('cash flow' in s.lower() for s in sheet_names)` [Source 3]

### Priority 2: Create `row_map.py` Module (new file)

**File**: `safe-harbor/backend/agents/row_map.py`
**Contents**: The `build_row_map()` function, `CANONICAL_ALIASES` dictionary, `_normalize_header()`, `_resolve_canonical()`, and `_detect_template_type()` as designed in Section 1 above.

```python
# Function signatures:
def build_row_map(parsed_template: dict) -> dict: ...
def _normalize_header(raw_header: str) -> str: ...
def _resolve_canonical(normalized_header: str) -> Optional[str]: ...
def _detect_template_type(sheet_names: dict) -> str: ...
```

### Priority 3: Refactor `post_processor.py` (major fix)

**File**: `safe-harbor/backend/agents/post_processor.py` [Source 1]

**Changes**:

1. **Import row_map**: `from backend.agents.row_map import build_row_map`

2. **Use `parsed_template` parameter** (currently ignored):
```python
def post_process(cells, parsed_template=None):
    if parsed_template is None:
        return cells  # Can't fix what we can't map
    
    rm = build_row_map(parsed_template)
    template_type = rm["template_type"]
    
    if template_type == "DCF":
        return cells  # No circular references
    # ... proceed with template-driven solver
```

3. **Replace all hardcoded sheet names** with `rm["sheet_names"]["is"]`, etc.

4. **Replace all hardcoded row numbers** with `rm["row_map"][(sheet, canonical)]` lookups.

5. **Fix interest calculation**: `sen_begin * sen_rate` instead of `(sen_begin + sen_end) / 2 * sen_rate`.

6. **Remove writes to formula cells**: Check `(sheet, row) in rm["input_rows"]` before every `_set()` in the write-back phase.

7. **Simplify working capital**: The template has a single "Changes in Working Capital" input cell, not 5 separate items. The solver should read this single value instead of computing 5 BS deltas.

8. **Add `simulate_period_lbo()` and `simulate_period_3s()`** strategy functions using row_map lookups (code in Section 2.3).

### Priority 4: Refactor `_add_validation_sheet()` in `main.py`

**File**: `safe-harbor/backend/main.py` [Source 3]

**Changes**:

1. **Pass `parsed_template` to the function** — modify the call site:
```python
if add_validation:
    _add_validation_sheet(sheets_svc, spreadsheet_id, wb, parsed_template=parsed_data)
```

This requires threading `parsed_template` through the call chain. In `orchestrator.py` [Source 11], the parsed data is available as `parsed` — it needs to be stored in `JobState` or passed to the writer.

2. **Add `parsed_template` parameter and build row_map**:
```python
def _add_validation_sheet(sheets_svc, spreadsheet_id, wb, parsed_template=None):
    from backend.agents.row_map import build_row_map
    rm = build_row_map(parsed_template) if parsed_template else None
    # ... use rm for all row references
```

3. **Fix sheet name detection** — use case-insensitive matching:
```python
sheet_names_lower = {s.lower(): s for s in [ws.title for ws in wb.worksheets]}
has_cf = any('cash flow' in s for s in sheet_names_lower)
cf_name = next((v for k, v in sheet_names_lower.items() if 'cash flow' in k), None)
```

4. **Fix Revenue Growth div-by-zero** — wrap in `IFERROR`:
```python
# Before (broken):
f"='Income Statement'!{cols[i]}4/'Income Statement'!{cols[i-1]}4-1"

# After (fixed):
r_rev = rm["row_map"].get((is_name, "is_revenue"))
f"=IFERROR('{is_name}'!{cols[i]}{r_rev}/'{is_name}'!{cols[i-1]}{r_rev}-1,\"N/A\")"
```

5. **Fix Avg Growth #NAME? error** — the current code embeds Python's `len(rows)` into the formula string [Source 3]:
```python
# Before (broken — produces #NAME?):
f"=AVERAGE({cols[1]}{'len(rows)'}:{cols[-1]}{'len(rows)'})"

# After (fixed — use the actual row number where growth values are written):
growth_row = current_row_in_validation_sheet  # track this as we build
f"=IFERROR(AVERAGE({cols[1]}{growth_row}:{cols[-1]}{growth_row}),\"N/A\")"
```

6. **Fix Debt Rollforward formula sign** — repayments should be subtracted:
```python
# Before (wrong): End - (Begin + Draw + Repay)
# After (correct): End - (Begin + Draw - Repay)
f"='{ds}'!{c}{r_se}-('{ds}'!{c}{r_sb}+'{ds}'!{c}{r_sd}-'{ds}'!{c}{r_sr})"
```

7. **Fix Statistical Distribution section** — references row 7 for "Gross Margin" which is actually D&A:
```python
# Before: margin_range = f"'Income Statement'!{cols[0]}7:{cols[-1]}7"
# After: compute margin inline
r_gp = rm["row_map"].get((is_name, "is_gross_profit"))
r_rev = rm["row_map"].get((is_name, "is_revenue"))
# Use formula: =GP/Rev for each period instead of referencing a non-existent margin row
```

8. **Apply template-type gating** for conditional sections:
```python
template_type = rm["template_type"]
if template_type == "LBO":
    _add_debt_rollforward_section(rows, rm, cols)
    _add_returns_section(rows, rm, cols)
elif template_type == "DCF":
    _add_dcf_valuation_section(rows, rm, cols)
# Universal sections always included
```

### Priority 5: Thread `parsed_template` to the Writer/Google Sheets Stage

**File**: `safe-harbor/backend/orchestrator.py` [Source 11]

Currently, the orchestrator stores `parsed` locally and passes it to `post_process()` but not to the Google Sheets creation. The fix:

```python
# In orchestrator._execute(), store parsed_template on the job:
self.jobs[job_id].parsed_template = parsed  # Add field to JobState

# In main.py, when creating Google Sheet:
_create_sheet_from_xlsx(xlsx_path, title, sa_path, 
                        add_validation=True, 
                        parsed_template=job.parsed_template)
```

**File**: `safe-harbor/backend/models/schemas.py` [Source 13] — add to `JobState`:
```python
class JobState(BaseModel):
    # ... existing fields ...
    parsed_template: Optional[dict] = None  # ADD THIS
```

### Priority 6: Edge Case Handling

**Missing rows**: If `row_map.get(...)` returns `None`, the validation builder should skip that check entirely rather than producing a broken formula. Each section should be gated:

```python
if all([r_ta, r_tl, r_te]):
    # Build BS Identity section
else:
    # Skip with a note: "Balance Sheet Identity: SKIPPED (missing rows)"
```

**Templates with extra sections**: The canonical alias dictionary is permissive — unknown headers are simply not mapped and don't cause errors. The solver skips any canonical key not found in the row_map.

**Partial templates**: If a user uploads an IS-only template, `sheet_names` will only contain `"is"`. The template type detection returns `"unknown"`, the solver is skipped, and only universal validation rules that apply to available sheets are generated.

---

## Summary of All Required Changes

| Priority | File | Change | Impact |
|---|---|---|---|
| **P1** | `post_processor.py` line 10 | Fix CF sheet name | Unblocks all CF processing |
| **P1** | `main.py` ~line 130 | Fix CF sheet name check | Unblocks CF validation section |
| **P2** | `agents/row_map.py` (NEW) | Create row map builder | Foundation for all other fixes |
| **P3** | `post_processor.py` | Full refactor with row_map | Fixes solver convergence |
| **P3** | `post_processor.py` | Fix interest: begin×rate | Matches template formulas |
| **P3** | `post_processor.py` | Remove formula cell writes | Fixes silent discard by writer |
| **P4** | `main.py` `_add_validation_sheet` | Use row_map for all refs | Fixes all validation formulas |
| **P4** | `main.py` | IFERROR on growth formulas | Fixes #ERROR! on FY2020 |
| **P4** | `main.py` | Fix `len(rows)` bug | Fixes #NAME? on Avg Growth |
| **P4** | `main.py` | Fix rollforward sign | Fixes debt validation math |
| **P5** | `orchestrator.py` + `schemas.py` | Thread parsed_template | Enables validation builder |
| **P6** | `main.py` | Template-type gating | Correct rules per model type |

**Estimated total effort**: 4–6 focused hours for all changes. The row_map module is ~150 lines of new code; the post_processor refactor is ~200 lines of modified code; the validation builder refactor is ~100 lines of modified code. No new dependencies, no architectural rewrites, no virtual environments needed.

---

## Sources & Citations

### Source 1

- **Tool:** read_source_content
- **Source ID:** 1
- **Summary:** {
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/agents/post_processor.py",
  "content": "\"\"\"\nLBO Circular Reference Solver (Fixed-Point Iteration)\nBased on Gemini Deep Research + Claude Red-Team implementation.\n\nTakes flat cell list, modifies ONLY input cells:\n- Retained Earnings (BS row 40) \u2014 all periods\n- Beginning Cash (CF row 31) \u2014 t>0\n- Scheduled Repayments (DS rows 7, 18) \u2014 t>0 (positive, template subtracts)\n\nUses Banach fixed-point iteration
- **Arguments:** {
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/agents/post_processor.py"
}

### Source 2

- **Tool:** read_source_content
- **Source ID:** 2
- **Summary:** {
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/excel_io/parser.py",
  "content": "import openpyxl\nimport re\n\nclass InvalidTemplateError(Exception): pass\nclass TemplateNotEmptyError(Exception): pass\n\ndef parse_template(file_path: str) -> dict:\n    try:\n        wb = openpyxl.load_workbook(file_path, data_only=False)\n    except Exception as e:\n        raise InvalidTemplateError(f\"Corrupt or unsupported Excel file: {e}\")\n\n    result = {\n        \"file_name\": fil
- **Arguments:** {
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/excel_io/parser.py"
}

### Source 3

- **Tool:** read_source_content
- **Source ID:** 3
- **Summary:** {
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/main.py",
  "content": "import os\nimport uuid\nimport json\nimport asyncio\nimport logging\nfrom fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException\nfrom fastapi.middleware.cors import CORSMiddleware\nfrom fastapi.responses import FileResponse\nfrom backend.config import get_settings\nfrom backend.orchestrator import PipelineOrchestrator\nfrom backend.models.schemas import JobState\nfrom ba
- **Arguments:** {
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/main.py"
}

### Source 4

- **Tool:** code_grep
- **Source ID:** 4
- **Summary:** {
  "success": true,
  "matches": {},
  "pattern": "Section [78]|RETURNS|_add_validation_sheet|SUMMARY DASHBOARD|has_ra|add_validation",
  "path_filter": "safe-harbor/backend/main.py",
  "total_matches": 0,
  "files_searched": 0,
  "files_with_matches": 0,
  "truncated": false,
  "options": {
    "case_sensitive": false,
    "lines_before": 5,
    "lines_after": 5,
    "output_mode": "content",
    "whole_word": false,
    "fixed_string": false,
    "highlight": false,
    "include_line_numbers"
- **Arguments:** {
  "repository_id": "Kaide-LABS/tracelight-safe-harbor",
  "pattern": "Section [78]|RETURNS|_add_validation_sheet|SUMMARY DASHBOARD|has_ra|add_validation",
  "path": "safe-harbor/backend/main.py",
  "context_lines": 5
}

### Source 5

- **Tool:** code_grep
- **Source ID:** 5
- **Summary:** {
  "success": true,
  "matches": {
    "Kaide-LABS/tracelight-safe-harbor/CONTEXT.md": [
      {
        "path": "Kaide-LABS/tracelight-safe-harbor/CONTEXT.md",
        "line": "The Chief Executive Officer, Peter Fuller, operates with a strategic pragmatism forged during his tenure as an Engagement Manager at McKinsey & Company and QuantumBlack.7 His professional trajectory reflects a rigorous focus on digital transformation, operational value creation, and verifiable return on investment.7 Fro
- **Arguments:** {
  "repository_id": "Kaide-LABS/tracelight-safe-harbor",
  "pattern": "RETURNS|SUMMARY DASHBOARD|has_ra|Section 8",
  "context_lines": 5
}

### Source 6

- **Tool:** code_grep
- **Source ID:** 6
- **Summary:** {
  "success": true,
  "matches": {
    "Kaide-LABS/tracelight-safe-harbor/CONTEXT.md": [
      {
        "path": "Kaide-LABS/tracelight-safe-harbor/CONTEXT.md",
        "line": "## **Executive Summary**",
        "context": "# **Strategic Architectural Blueprint for Tracelight: Multi-Agent Sidecar Orchestration and Enterprise Acceleration**\n\n## **Executive Summary**\n\nThe deployment of artificial intelligence within the high-stakes domain of complex financial modeling necessitates a fundamen
- **Arguments:** {
  "repository_id": "Kaide-LABS/tracelight-safe-harbor",
  "pattern": "has_ra|RETURNS ANALYSIS|Section 8|SUMMARY|_add_validation",
  "context_lines": 3,
  "max_total_matches": 30
}

### Source 7

- **Tool:** get_github_tree
- **Source ID:** 7
- **Summary:** {
  "tree": "\ud83d\udcc4 .env.example\n\ud83d\udcc1 .github\n  \ud83d\udcc1 workflows\n    \ud83d\udcc4 ci.yml\n    \ud83d\udcc4 deploy.yml\n\ud83d\udcc4 .gitignore\n\ud83d\udcc4 3_Statement_Model.xlsx\n\ud83d\udcc4 ADJACENT_IDEAS.md\n\ud83d\udcc4 Balancing Financial Model Circular References copy.md\n\ud83d\udcc4 CONTEXT.md\n\ud83d\udcc4 DCF_Model.xlsx\n\ud83d\udcc4 FOUNDERS_BRIEF.md\n\ud83d\udcc4 LBO_Model.xlsx\n\ud83d\udcc4 PHASE_1_SPEC.md\n\ud83d\udcc4 PHASE_2_SPEC.md\n\ud83d\udcc4 PHASE_3_
- **Arguments:** {
  "project_id": "e83393b7-1ee7-4b81-b0a0-fffc1b7afa1b"
}

### Source 8

- **Tool:** read_source_content
- **Source ID:** 8
- **Summary:** {
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/scripts/generate_templates.py",
  "content": "import openpyxl\nfrom openpyxl.styles import Font, PatternFill, numbers\nimport os\n\ndef create_lbo():\n    wb = openpyxl.Workbook()\n    \n    # 1. Income Statement\n    ws_is = wb.active\n    ws_is.title = \"Income Statement\"\n    headers = [\"Line Item\", \"FY2020\", \"FY2021\", \"FY2022\", \"FY2023\", \"FY2024\", \"FY2025\"]\n    ws_is.append(headers)\n    for cell in ws_is[1]:\n     
- **Arguments:** {
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/scripts/generate_templates.py"
}

### Source 9

- **Tool:** read_source_content
- **Source ID:** 9
- **Summary:** {
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/excel_io/writer.py",
  "content": "import openpyxl\nfrom backend.models.schemas import SyntheticPayload\n\ndef write_synthetic_data(template_path: str, payload: SyntheticPayload, output_path: str) -> str:\n    wb = openpyxl.load_workbook(template_path, data_only=False)\n    \n    for cell_value in payload.cells:\n        if cell_value.sheet_name in wb.sheetnames:\n            ws = wb[cell_value.sheet_name]\n            cell = w
- **Arguments:** {
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/excel_io/writer.py"
}

### Source 10

- **Tool:** think
- **Source ID:** 10
- **Summary:** Reflection recorded. Continue with next action.
- **Arguments:** {
  "reflection": "## Key Findings So Far\n\n### 1. Template Row Layout (from generate_templates.py)\n\n**LBO Income Statement (actual):**\n- Row 2: Revenue (INPUT), Row 3: COGS (INPUT), Row 4: Gross Profit (FORMULA)\n- Row 5: SG&A (INPUT), Row 6: EBITDA (FORMULA), Row 7: D&A (INPUT)\n- Row 8: EBIT (FORMULA), Row 9: Interest Expense (FORMULA from DS!16)\n- Row 10: EBT (FORMULA), Row 11: Tax (INPUT), Row 12: Net Income (FORMULA)\n\n**LBO Balance Sheet (actual):**\n- Row 2: Cash (INPUT), Row 3: AR (INPUT), Row 4: Inventory (INPUT), Row 5: Other Curr (INPUT)\n- Row 6: Total Curr Assets (FORMULA), Row 7: PP&E Net (INPUT)\n- Row 8: Goodwill (INPUT), Row 9: Other Non-Curr (INPUT), Row 10: Total Assets (FORMULA)\n- Row 11: AP (INPUT), Row 12: Accrued (INPUT), Row 13: Curr Debt (INPUT)\n- Row 14: Total Curr Liab (FORMULA), Row 15: Senior Debt (INPUT), Row 16: Mezz Debt (INPUT)\n- Row 17: Total Liabilities (FORMULA), Row 18: Common Equity (INPUT)\n- Row 19: Retained Earnings (FORMULA!), Row 20: Total Equity (FORMULA)\n- Row 21: Total L&E (FORMULA)\n\n**Cash Flow (sheet named 'Cash Flow' NOT 'Cash Flow Statement'):**\n- Row 2: NI (FORMULA), Row 3: D&A (FORMULA), Row 4: WC Changes (INPUT - single line!)\n- Row 5: Operating CF (FORMULA), Row 6: CapEx (INPUT), Row 7: Investing CF (FORMULA)\n- Row 8: Debt Drawdowns (INPUT), Row 9: Debt Repayments (INPUT), Row 10: Dividends (INPUT)\n- Row 11: Financing CF (FORMULA), Row 12: Net Change (FORMULA)\n- Row 13: Beginning Cash (FORMULA!), Row 14: Ending Cash (FORMULA)\n\n**Debt Schedule:**\n- Row 2: Senior Debt (section header), Row 3: Begin Bal, Row 4: Drawdowns, Row 5: Repayments\n- Row 6: Ending Bal (FORMULA), Row 7: Interest Rate, Row 8: Interest Expense (FORMULA: =B3*B7, BEGIN×RATE)\n- Row 9: Mezzanine Debt (section header), Row 10: Begin Bal, Row 11: Drawdowns, Row 12: Repayments\n- Row 13: Ending Bal (FORMULA), Row 14: Interest Rate, Row 15: Interest Expense (FORMULA: =B10*B14, BEGIN×RATE)\n- Row 16: Total Interest (FORMULA), Row 17: Total Ending Debt (FORMULA)\n\n### 2. Critical Mismatches Confirmed\n- **Sheet name**: Solver uses 'Cash Flow Statement', template uses 'Cash Flow'\n- **Interest method**: Solver uses AVERAGE balance × rate, template uses BEGIN balance × rate\n- **Retained Earnings is a FORMULA**: Solver tries to write to it, writer SKIPS it\n- **Beginning Cash is a FORMULA**: Same problem\n- **Every single row number is wrong** in both post_processor.py and _add_validation_sheet\n- **Template is much simpler**: No R&D, Other OpEx, PP&E Gross/Accum Depr, Intangibles, Deferred items, AOCI\n- **Working capital is a single input cell**, not 5 separate items\n\n### 3. Writer Formula-Skip\nConfirmed: writer.py checks `existing_val.startswith('=')` and skips. So post-processor adjustments to formula cells are silently discarded.\n\n### Gaps Remaining\n- Need the truncated part of main.py (validation sections 7-8, summary dashboard)\n- Need to understand the 3-Statement and DCF template layouts for generalization\n- Need to design the row_map builder and normalization strategy\n\n### Confidence: HIGH on diagnosis, MEDIUM on implementation plan (need more detail)\n\n### Next Actions:\n1. Read the remaining part of main.py (sections 7-8)\n2. Read the orchestrator.py to understand how post_processor is called\n3. Design the row_map builder and implementation plan"
}

### Source 11

- **Tool:** read_source_content
- **Source ID:** 11
- **Summary:** {
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/orchestrator.py",
  "content": "import asyncio\nimport uuid\nimport time\nimport logging\nfrom typing import Callable, Awaitable\nfrom datetime import datetime\n\nfrom backend.config import Settings\nfrom backend.models.schemas import JobState, WSEvent, AuditLogEntry, TemplateSchema, SyntheticPayload\nfrom backend.excel_io.parser import parse_template\nfrom backend.excel_io.writer import write_synthetic_data\nfrom backend.agent
- **Arguments:** {
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/orchestrator.py"
}

### Source 12

- **Tool:** read_source_content
- **Source ID:** 12
- **Summary:** {
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/agents/validator.py",
  "content": "from datetime import datetime\nimport copy\nfrom backend.models.schemas import TemplateSchema, SyntheticPayload, ValidationResult, ValidationRuleResult, PlugAdjustment\n\n\nclass DeterministicValidator:\n    def __init__(self, schema: TemplateSchema):\n        self.schema = schema\n        self.adjustments = []\n        self.needs_regeneration = []\n\n    def validate(self, payload: Synthetic
- **Arguments:** {
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/agents/validator.py"
}

### Source 13

- **Tool:** read_source_content
- **Source ID:** 13
- **Summary:** {
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/models/schemas.py",
  "content": "from typing import Literal, Optional, List\nfrom pydantic import BaseModel, Field\n\nclass ColumnConstraints(BaseModel):\n    min_value: Optional[float] = None\n    max_value: Optional[float] = None\n    growth_rate_range: Optional[List[float]] = None  # [min, max] e.g. [-0.1, 0.3]\n    must_be_positive: bool = False\n    must_be_negative: bool = False\n    sum_equals: Optional[str] = None\n\nc
- **Arguments:** {
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/models/schemas.py"
}

### Source 14

- **Tool:** code_grep
- **Source ID:** 14
- **Summary:** {
  "success": true,
  "matches": {},
  "pattern": "Section 7|Section 8|Returns Analysis|SUMMARY DASHBOARD|def _add_validation|has_ra|has_is|has_bs|has_cf|has_ds",
  "path_filter": "safe-harbor/backend",
  "total_matches": 0,
  "files_searched": 0,
  "files_with_matches": 0,
  "truncated": false,
  "options": {
    "case_sensitive": false,
    "lines_before": 4,
    "lines_after": 4,
    "output_mode": "content",
    "whole_word": false,
    "fixed_string": false,
    "highlight": false,
    "in
- **Arguments:** {
  "repository_id": "Kaide-LABS/tracelight-safe-harbor",
  "pattern": "Section 7|Section 8|Returns Analysis|SUMMARY DASHBOARD|def _add_validation|has_ra|has_is|has_bs|has_cf|has_ds",
  "path": "safe-harbor/backend",
  "context_lines": 4,
  "max_total_matches": 50
}

### Source 15

- **Tool:** query
- **Source ID:** 15
- **Summary:** {
  "content": "Query='_add_validation_sheet Returns Analysis summary dashboard section 8 validation formulas'. Repo results=5 (projects=1). Doc results=0 (sources=0).",
  "sources": [
    {
      "content": "Kaide-LABS/tracelight-safe-harbor/safe-harbor/backend/agents/validator.py\nCalls: PlugAdjustment, ValidationRuleResult, _get_val, abs, append\nControl flow: 12 branches, 8 loops, complexity 27\n\ndef _rule_balance_sheet_identity(self, payload: SyntheticPayload) -> list[ValidationRuleResult]
- **Arguments:** {
  "query": "_add_validation_sheet Returns Analysis summary dashboard section 8 validation formulas",
  "repositories": [
    "Kaide-LABS/tracelight-safe-harbor"
  ]
}

### Source 16

- **Tool:** read_source_content
- **Source ID:** 16
- **Summary:** {
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/scripts/verify_templates.py",
  "content": "\"\"\"Verify generated templates are structurally correct.\"\"\"\nimport openpyxl\nimport sys\n\ndef verify_lbo():\n    wb = openpyxl.load_workbook(\"../templates/lbo_template.xlsx\", data_only=False)\n    assert len(wb.sheetnames) == 5, f\"Expected 5 sheets, got {len(wb.sheetnames)}\"\n    assert \"Income Statement\" in wb.sheetnames\n    assert \"Debt Schedule\" in wb.sheetnames\n    assert
- **Arguments:** {
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/scripts/verify_templates.py"
}

### Source 17

- **Tool:** read_source_content
- **Source ID:** 17
- **Summary:** {
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/agents/synthetic_gen.py",
  "content": "import time\nimport json\nimport asyncio\nimport functools\nimport logging\nfrom google import genai\nfrom google.genai import types\nfrom backend.models.schemas import TemplateSchema, SyntheticPayload, GenerationMetadata, TokenUsage, CellValue\nfrom backend.config import Settings\n\nlogger = logging.getLogger(__name__)\n\n# Smaller chunks = LLM never skips. 25 cells \u00d7 ~5 tokens each
- **Arguments:** {
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/agents/synthetic_gen.py"
}

### Source 18

- **Tool:** code_grep
- **Source ID:** 18
- **Summary:** {
  "success": true,
  "matches": {},
  "pattern": "def create_dcf|DCF Valuation|Free Cash Flow|WACC|Terminal",
  "path_filter": "safe-harbor/scripts/generate_templates.py",
  "total_matches": 0,
  "files_searched": 0,
  "files_with_matches": 0,
  "truncated": false,
  "options": {
    "case_sensitive": false,
    "lines_before": 6,
    "lines_after": 6,
    "output_mode": "content",
    "whole_word": false,
    "fixed_string": false,
    "highlight": false,
    "include_line_numbers": true,
   
- **Arguments:** {
  "repository_id": "Kaide-LABS/tracelight-safe-harbor",
  "pattern": "def create_dcf|DCF Valuation|Free Cash Flow|WACC|Terminal",
  "path": "safe-harbor/scripts/generate_templates.py",
  "context_lines": 6,
  "max_total_matches": 30
}

### Source 19

- **Tool:** think
- **Source ID:** 19
- **Summary:** Reflection recorded. Continue with next action.
- **Arguments:** {
  "reflection": "## Final Synthesis Before Report\n\n### Complete Data Flow (confirmed through source code):\n1. **Parser** → produces `{sheet_name, ref, column_header (section-qualified), period, formula}` with separate `input_cells` and `formula_cells` lists\n2. **Synthetic Gen** → only touches `input_cells` from parser, preserves `cell_ref` exactly, generates values via LLM in chunks of 25\n3. **Post-Processor** → receives flat cells + parsed_template (BUT IGNORES parsed_template!), builds grids keyed by `(sheet_name, row_number)`, simulates using HARDCODED row numbers that don't match any template\n4. **Validator** → uses fuzzy keyword matching on headers (template-agnostic, good design)\n5. **Writer** → skips formula cells, writes only to input cells\n6. **Google Sheets + Validation Tab** → builds formulas with HARDCODED row references that don't match template\n\n### Critical Bugs Confirmed:\n\n**Bug 1: Sheet Name Mismatch**\n- post_processor.py: `CF = \"Cash Flow Statement\"`\n- Actual template: `\"Cash Flow\"`\n- Validation builder: `has_cf = 'Cash Flow Statement' in sheet_names` → always False!\n- Result: ALL cash flow processing is silently skipped\n\n**Bug 2: Every Row Number Wrong** (post_processor + validation builder)\n- IS Revenue: solver uses row 4, actual is row 2\n- BS Cash: solver uses row 5, actual is row 2 \n- CF Net Income: solver uses row 5, actual is row 2\n- DS Senior Begin: solver uses row 5, actual is row 3\n- ...and dozens more (see complete mapping)\n\n**Bug 3: Interest Calculation Method Mismatch**\n- Solver: `(begin + end) / 2 × rate` (average balance)\n- Template: `begin × rate` (beginning balance)\n- This creates a systematic error in interest → NI → CF → Debt circularity\n\n**Bug 4: Formula Cell Overwrite Attempt**\n- Solver tries to write: Retained Earnings (BS row 19 - FORMULA), Beginning Cash (CF row 13 - FORMULA)\n- Writer silently skips these because they start with `=`\n- Result: solver's circular reference resolution is completely discarded\n\n**Bug 5: Validation Div-by-Zero**\n- Revenue Growth for FY2020 tries `FY2020/FY2019-1` but FY2019 doesn't exist → #ERROR!\n\n**Bug 6: Avg Growth #NAME? Error**\n- Uses `len(rows)` (Python variable) in formula string, creating malformed range reference\n\n**Bug 7: Working Capital Granularity Mismatch**\n- Solver simulates 5 separate WC items (AR, Inv, AP, Accrued, DefRev)\n- Template has single \"Changes in Working Capital\" input cell\n\n**Bug 8: parsed_template Parameter Ignored**\n- `post_process(cells, parsed_template=None)` receives parsed_template but NEVER uses it\n- This is the key architectural gap — all the row mapping data is available but unused\n\n### Design Decisions for Row Map Builder:\n\n1. **Normalization Strategy**: Use a canonical alias dictionary mapping qualified headers to canonical keys. Example:\n   - `\"Revenue\"` → `\"revenue\"`\n   - `\"SENIOR SECURED DEBT > Beginning Balance\"` → `\"senior_begin_bal\"` (but actual template uses just \"Beginning Balance\" under \"Senior Debt\" section)\n   - Need to handle: section prefix + item name → canonical key\n\n2. **Template Type Detection**: Check sheet names:\n   - Has \"Debt Schedule\" + \"Returns Analysis\" → LBO\n   - Has \"Revenue Build\" + \"DCF Valuation\" → DCF\n   - Has IS + BS + CF only → 3-Statement\n\n3. **Formula vs Input Detection**: Parser already separates these into `input_cells` and `formula_cells` lists\n\n4. **Solver Strategy Per Template**:\n   - LBO: Full IS→DS→CF→BS circular reference solver\n   - DCF: No debt circularity, simpler (UFCF → Terminal Value → WACC)\n   - 3-Statement: Simplified debt handling\n\n### Confidence Level: HIGH — Ready to produce comprehensive report"
}

---

## Tool Calls

### 1. read_source_content

- **Timestamp:** 2026-04-10T06:18:55.571721+00:00
- **Arguments:**
```json
{
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/agents/post_processor.py"
}
```

### 2. read_source_content

- **Timestamp:** 2026-04-10T06:19:02.304318+00:00
- **Arguments:**
```json
{
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/excel_io/parser.py"
}
```

### 3. read_source_content

- **Timestamp:** 2026-04-10T06:19:09.331998+00:00
- **Arguments:**
```json
{
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/main.py"
}
```

### 4. code_grep

- **Timestamp:** 2026-04-10T06:19:18.148122+00:00
- **Arguments:**
```json
{
  "repository_id": "Kaide-LABS/tracelight-safe-harbor",
  "pattern": "Section [78]|RETURNS|_add_validation_sheet|SUMMARY DASHBOARD|has_ra|add_validation",
  "path": "safe-harbor/backend/main.py",
  "context_lines": 5
}
```

### 5. code_grep

- **Timestamp:** 2026-04-10T06:19:22.606511+00:00
- **Arguments:**
```json
{
  "repository_id": "Kaide-LABS/tracelight-safe-harbor",
  "pattern": "RETURNS|SUMMARY DASHBOARD|has_ra|Section 8",
  "context_lines": 5
}
```

### 6. code_grep

- **Timestamp:** 2026-04-10T06:19:32.976319+00:00
- **Arguments:**
```json
{
  "repository_id": "Kaide-LABS/tracelight-safe-harbor",
  "pattern": "has_ra|RETURNS ANALYSIS|Section 8|SUMMARY|_add_validation",
  "context_lines": 3,
  "max_total_matches": 30
}
```

### 7. get_github_tree

- **Timestamp:** 2026-04-10T06:19:40.816883+00:00
- **Arguments:**
```json
{
  "project_id": "e83393b7-1ee7-4b81-b0a0-fffc1b7afa1b"
}
```

### 8. read_source_content

- **Timestamp:** 2026-04-10T06:19:48.698209+00:00
- **Arguments:**
```json
{
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/scripts/generate_templates.py"
}
```

### 9. read_source_content

- **Timestamp:** 2026-04-10T06:20:37.965097+00:00
- **Arguments:**
```json
{
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/excel_io/writer.py"
}
```

### 10. think

- **Timestamp:** 2026-04-10T06:21:03.646986+00:00
- **Arguments:**
```json
{
  "reflection": "## Key Findings So Far\n\n### 1. Template Row Layout (from generate_templates.py)\n\n**LBO Income Statement (actual):**\n- Row 2: Revenue (INPUT), Row 3: COGS (INPUT), Row 4: Gross Profit (FORMULA)\n- Row 5: SG&A (INPUT), Row 6: EBITDA (FORMULA), Row 7: D&A (INPUT)\n- Row 8: EBIT (FORMULA), Row 9: Interest Expense (FORMULA from DS!16)\n- Row 10: EBT (FORMULA), Row 11: Tax (INPUT), Row 12: Net Income (FORMULA)\n\n**LBO Balance Sheet (actual):**\n- Row 2: Cash (INPUT), Row 3: AR (INPUT), Row 4: Inventory (INPUT), Row 5: Other Curr (INPUT)\n- Row 6: Total Curr Assets (FORMULA), Row 7: PP&E Net (INPUT)\n- Row 8: Goodwill (INPUT), Row 9: Other Non-Curr (INPUT), Row 10: Total Assets (FORMULA)\n- Row 11: AP (INPUT), Row 12: Accrued (INPUT), Row 13: Curr Debt (INPUT)\n- Row 14: Total Curr Liab (FORMULA), Row 15: Senior Debt (INPUT), Row 16: Mezz Debt (INPUT)\n- Row 17: Total Liabilities (FORMULA), Row 18: Common Equity (INPUT)\n- Row 19: Retained Earnings (FORMULA!), Row 20: Total Equity (FORMULA)\n- Row 21: Total L&E (FORMULA)\n\n**Cash Flow (sheet named 'Cash Flow' NOT 'Cash Flow Statement'):**\n- Row 2: NI (FORMULA), Row 3: D&A (FORMULA), Row 4: WC Changes (INPUT - single line!)\n- Row 5: Operating CF (FORMULA), Row 6: CapEx (INPUT), Row 7: Investing CF (FORMULA)\n- Row 8: Debt Drawdowns (INPUT), Row 9: Debt Repayments (INPUT), Row 10: Dividends (INPUT)\n- Row 11: Financing CF (FORMULA), Row 12: Net Change (FORMULA)\n- Row 13: Beginning Cash (FORMULA!), Row 14: Ending Cash (FORMULA)\n\n**Debt Schedule:**\n- Row 2: Senior Debt (section header), Row 3: Begin Bal, Row 4: Drawdowns, Row 5: Repayments\n- Row 6: Ending Bal (FORMULA), Row 7: Interest Rate, Row 8: Interest Expense (FORMULA: =B3*B7, BEGIN×RATE)\n- Row 9: Mezzanine Debt (section header), Row 10: Begin Bal, Row 11: Drawdowns, Row 12: Repayments\n- Row 13: Ending Bal (FORMULA), Row 14: Interest Rate, Row 15: Interest Expense (FORMULA: =B10*B14, BEGIN×RATE)\n- Row 16: Total Interest (FORMULA), Row 17: Total Ending Debt (FORMULA)\n\n### 2. Critical Mismatches Confirmed\n- **Sheet name**: Solver uses 'Cash Flow Statement', template uses 'Cash Flow'\n- **Interest method**: Solver uses AVERAGE balance × rate, template uses BEGIN balance × rate\n- **Retained Earnings is a FORMULA**: Solver tries to write to it, writer SKIPS it\n- **Beginning Cash is a FORMULA**: Same problem\n- **Every single row number is wrong** in both post_processor.py and _add_validation_sheet\n- **Template is much simpler**: No R&D, Other OpEx, PP&E Gross/Accum Depr, Intangibles, Deferred items, AOCI\n- **Working capital is a single input cell**, not 5 separate items\n\n### 3. Writer Formula-Skip\nConfirmed: writer.py checks `existing_val.startswith('=')` and skips. So post-processor adjustments to formula cells are silently discarded.\n\n### Gaps Remaining\n- Need the truncated part of main.py (validation sections 7-8, summary dashboard)\n- Need to understand the 3-Statement and DCF template layouts for generalization\n- Need to design the row_map builder and normalization strategy\n\n### Confidence: HIGH on diagnosis, MEDIUM on implementation plan (need more detail)\n\n### Next Actions:\n1. Read the remaining part of main.py (sections 7-8)\n2. Read the orchestrator.py to understand how post_processor is called\n3. Design the row_map builder and implementation plan"
}
```

### 11. read_source_content

- **Timestamp:** 2026-04-10T06:21:11.069883+00:00
- **Arguments:**
```json
{
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/orchestrator.py"
}
```

### 12. read_source_content

- **Timestamp:** 2026-04-10T06:21:20.612974+00:00
- **Arguments:**
```json
{
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/agents/validator.py"
}
```

### 13. read_source_content

- **Timestamp:** 2026-04-10T06:21:34.118998+00:00
- **Arguments:**
```json
{
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/models/schemas.py"
}
```

### 14. code_grep

- **Timestamp:** 2026-04-10T06:21:47.897198+00:00
- **Arguments:**
```json
{
  "repository_id": "Kaide-LABS/tracelight-safe-harbor",
  "pattern": "Section 7|Section 8|Returns Analysis|SUMMARY DASHBOARD|def _add_validation|has_ra|has_is|has_bs|has_cf|has_ds",
  "path": "safe-harbor/backend",
  "context_lines": 4,
  "max_total_matches": 50
}
```

### 15. query

- **Timestamp:** 2026-04-10T06:21:56.509488+00:00
- **Arguments:**
```json
{
  "query": "_add_validation_sheet Returns Analysis summary dashboard section 8 validation formulas",
  "repositories": [
    "Kaide-LABS/tracelight-safe-harbor"
  ]
}
```

### 16. read_source_content

- **Timestamp:** 2026-04-10T06:22:10.726063+00:00
- **Arguments:**
```json
{
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/scripts/verify_templates.py"
}
```

### 17. read_source_content

- **Timestamp:** 2026-04-10T06:22:20.598641+00:00
- **Arguments:**
```json
{
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/agents/synthetic_gen.py"
}
```

### 18. code_grep

- **Timestamp:** 2026-04-10T06:22:30.119244+00:00
- **Arguments:**
```json
{
  "repository_id": "Kaide-LABS/tracelight-safe-harbor",
  "pattern": "def create_dcf|DCF Valuation|Free Cash Flow|WACC|Terminal",
  "path": "safe-harbor/scripts/generate_templates.py",
  "context_lines": 6,
  "max_total_matches": 30
}
```

### 19. think

- **Timestamp:** 2026-04-10T06:23:07.059847+00:00
- **Arguments:**
```json
{
  "reflection": "## Final Synthesis Before Report\n\n### Complete Data Flow (confirmed through source code):\n1. **Parser** → produces `{sheet_name, ref, column_header (section-qualified), period, formula}` with separate `input_cells` and `formula_cells` lists\n2. **Synthetic Gen** → only touches `input_cells` from parser, preserves `cell_ref` exactly, generates values via LLM in chunks of 25\n3. **Post-Processor** → receives flat cells + parsed_template (BUT IGNORES parsed_template!), builds grids keyed by `(sheet_name, row_number)`, simulates using HARDCODED row numbers that don't match any template\n4. **Validator** → uses fuzzy keyword matching on headers (template-agnostic, good design)\n5. **Writer** → skips formula cells, writes only to input cells\n6. **Google Sheets + Validation Tab** → builds formulas with HARDCODED row references that don't match template\n\n### Critical Bugs Confirmed:\n\n**Bug 1: Sheet Name Mismatch**\n- post_processor.py: `CF = \"Cash Flow Statement\"`\n- Actual template: `\"Cash Flow\"`\n- Validation builder: `has_cf = 'Cash Flow Statement' in sheet_names` → always False!\n- Result: ALL cash flow processing is silently skipped\n\n**Bug 2: Every Row Number Wrong** (post_processor + validation builder)\n- IS Revenue: solver uses row 4, actual is row 2\n- BS Cash: solver uses row 5, actual is row 2 \n- CF Net Income: solver uses row 5, actual is row 2\n- DS Senior Begin: solver uses row 5, actual is row 3\n- ...and dozens more (see complete mapping)\n\n**Bug 3: Interest Calculation Method Mismatch**\n- Solver: `(begin + end) / 2 × rate` (average balance)\n- Template: `begin × rate` (beginning balance)\n- This creates a systematic error in interest → NI → CF → Debt circularity\n\n**Bug 4: Formula Cell Overwrite Attempt**\n- Solver tries to write: Retained Earnings (BS row 19 - FORMULA), Beginning Cash (CF row 13 - FORMULA)\n- Writer silently skips these because they start with `=`\n- Result: solver's circular reference resolution is completely discarded\n\n**Bug 5: Validation Div-by-Zero**\n- Revenue Growth for FY2020 tries `FY2020/FY2019-1` but FY2019 doesn't exist → #ERROR!\n\n**Bug 6: Avg Growth #NAME? Error**\n- Uses `len(rows)` (Python variable) in formula string, creating malformed range reference\n\n**Bug 7: Working Capital Granularity Mismatch**\n- Solver simulates 5 separate WC items (AR, Inv, AP, Accrued, DefRev)\n- Template has single \"Changes in Working Capital\" input cell\n\n**Bug 8: parsed_template Parameter Ignored**\n- `post_process(cells, parsed_template=None)` receives parsed_template but NEVER uses it\n- This is the key architectural gap — all the row mapping data is available but unused\n\n### Design Decisions for Row Map Builder:\n\n1. **Normalization Strategy**: Use a canonical alias dictionary mapping qualified headers to canonical keys. Example:\n   - `\"Revenue\"` → `\"revenue\"`\n   - `\"SENIOR SECURED DEBT > Beginning Balance\"` → `\"senior_begin_bal\"` (but actual template uses just \"Beginning Balance\" under \"Senior Debt\" section)\n   - Need to handle: section prefix + item name → canonical key\n\n2. **Template Type Detection**: Check sheet names:\n   - Has \"Debt Schedule\" + \"Returns Analysis\" → LBO\n   - Has \"Revenue Build\" + \"DCF Valuation\" → DCF\n   - Has IS + BS + CF only → 3-Statement\n\n3. **Formula vs Input Detection**: Parser already separates these into `input_cells` and `formula_cells` lists\n\n4. **Solver Strategy Per Template**:\n   - LBO: Full IS→DS→CF→BS circular reference solver\n   - DCF: No debt circularity, simpler (UFCF → Terminal Value → WACC)\n   - 3-Statement: Simplified debt handling\n\n### Confidence Level: HIGH — Ready to produce comprehensive report"
}
```

---

## Research Notes

1. [Source 1] read_source_content({"source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/agents/post_processor.py"}): {
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/agents/post_processor.py",
  "content": "\"\"\"\nLBO Circular Reference Solver (Fixed-Point Iteration)\nBased on Gemini Deep Research + Claude Red-Team implementation.\n\nTakes flat cell list, modifies ONLY input cells:\n- Retained Earnings (BS row 40) \u2014 all periods\n- Beginning Cash (CF row 31) \u2014 t>0\n- Scheduled Repayments (DS rows 7, 18) \u2014 t>0 (positive, template subtracts)\n\nUses Banach fixed-point iteration to resolve the Interest \u2192 NI \u2192 CF \u2192 Repayment circularity.\n\"\"\"\nimport copy\n\n# \u2500\u2500 Column / Period mapping \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\nCOL_TO_PERIOD = {\"B\": 0, \"C\": 1, \"D\": 2, \"E\": 3, \"F\": 4, \"G\": 5}\nPERIOD_TO_COL = {v: k for k, v in COL_TO_PERIOD.items()}\n\n# \u2500\u2500 Sheet names (must match actual template) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\nIS = \"Income Statement\"\nDS = \"Debt Schedule\"\nCF = \"Cash Flow Statement\"\nBS = \"Balance Sheet\"\n\n\ndef _key(sheet, row):\n    return (sheet, row)\n\ndef _get(grid, sheet, row, default=0.0):\n    v = grid.get(_key(sheet, row), default)\n    try:\n        return float(v)\n    except (TypeError, ValueError):\n        return default\n\ndef _set(grid, sheet, row, val):\n    grid[_key(sheet, row)] = val\n\n\ndef simulate_period(grid, prev, senior_repay, mezz_repay, default_tax_rate=0.25):\n    \"\"\"Simulate full IS \u2192 DS \u2192 CF \u2192 BS chain for one period. Returns (grid, new_sen_repay, new_mezz_repay).\"\"\"\n    g = grid\n\n    # \u2500\u2500 0. Cross-period linkages \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n    prev_end_cash = _get(prev, CF, 32, default=_get(prev, BS, 5))\n    _set(g, CF, 31, prev_end_cash)\n\n    prev_sen_end = _get(prev, DS, 9, default=_get(prev, DS, 5))\n    _set(g, DS, 5, prev_sen_end)\n\n    prev_mezz_end = _get(prev, DS, 20, default=_get(prev, DS, 16))\n    _set(g, DS, 16, prev_mezz_end)\n\n    # \u2500\u2500 1. Plug repayment guesses (positive \u2014 template subtracts) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n    _set(g, DS, 7, senior_repay)\n    _set(g, DS, 18, mezz_repay)\n\n    # \u2500\u2500 2. Debt Schedule \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n    sen_begin = _get(g, DS, 5)\n    sen_draw = _get(g, DS, 6)\n    sen_end = sen_begin + sen_draw - senior_repay\n    _set(g, DS, 9, sen_end)\n\n    sen_rate = _get(g, DS, 11)\n    sen_avg = (sen_begin + sen_end) / 2.0\n    _set(g, DS, 12, sen_avg)\n    sen_interest = sen_avg * sen_rate\n    _set(g, DS, 13, sen_interest)\n\n    mezz_begin = _get(g, DS, 16)\n    mezz_draw = _get(g, DS, 17)\n    mezz_end = mezz_begin + mezz_draw - mezz_repay\n    _set(g, DS, 20, mezz_end)\n\n    mezz_rate = _get(g, DS, 22)\n    mezz_avg = (mezz_begin + mezz_end) / 2.0\n    _set(g, DS, 23, mezz_avg)\n    mezz_interest = mezz_avg * mezz_rate\n    _set(g, DS, 24, mezz_interest)\n\n    # \u2500\u2500 3. Income Statement \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n    revenue = _get(g, IS, 4)\n    cogs = _get(g, IS, 5)\n    gross = revenue - cogs\n    _set(g, IS, 6, gross)\n\n    sga = _get(g, IS, 9)\n    rnd = _get(g, IS, 10)\n    other_opex = _get(g, IS, 11)\n    total_opex = sga + rnd + other_opex\n    _set(g, IS, 12, total_opex)\n\n    ebitda = gross - total_opex\n    _set(g, IS, 14, ebitda)\n\n    da = _get(g, IS, 17)  # negative on IS\n    ebit = ebitda + da  # da is negative, so this subtracts\n    _set(g, IS, 18, ebit)\n\n    _set(g, IS, 21, sen_interest)\n    _set(g, IS, 22, mezz_interest)\n    total_interest = sen_interest + mezz_interest\n    _set(g, IS, 23, total_interest)\n\n    ebt = ebit - total_interest\n    _set(g, IS, 25, ebt)\n\n    tax_rate = _get(g, IS, 26, default_tax_rate)\n    tax_expense = max(0.0, ebt * tax_rate)\n    _set(g, IS, 27, tax_expense)\n\n    net_income = ebt - tax_expense\n    _set(g, IS, 29, net_income)\n\n    # \u2500\u2500 4. Cash Flow \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n    _set(g, CF, 5, net_income)\n    da_addback = abs(da)\n    _set(g, CF, 6, da_addback)\n\n    # Working capital changes (computed from BS deltas)\n    chg_ar = -(_get(g, BS, 6) - _get(prev, BS, 6))\n    chg_inv = -(_get(g, BS, 7) - _get(prev, BS, 7))\n    chg_ap = _get(g, BS, 23) - _get(prev, BS, 23)\n    chg_accrued = _get(g, BS, 24) - _get(prev, BS, 24)\n    chg_defrev = _get(g, BS, 25) - _get(prev, BS, 25)\n    _set(g, CF, 9, chg_ar)\n    _set(g, CF, 10, chg_inv)\n    _set(g, CF, 11, chg_ap)\n    _set(g, CF, 12, chg_accrued)\n    _set(g, CF, 13, chg_defrev)\n\n    net_wc = chg_ar + chg_inv + chg_ap + chg_accrued + chg_defrev\n    _set(g, CF, 14, net_wc)\n\n    net_cash_ops = net_income + da_addback + net_wc\n    _set(g, CF, 16, net_cash_ops)\n\n    capex = _get(g, CF, 19)\n    acquisitions = _get(g, CF, 20)\n    other_inv = _get(g, CF, 21)\n    net_cash_inv = capex + acquisitions + other_inv\n    _set(g, CF, 22, net_cash_inv)\n\n    debt_draws = sen_draw + mezz_draw\n    _set(g, CF, 25, debt_draws)\n    debt_repay_cf = -(senior_repay + mezz_repay)  # negative on CF\n    _set(g, CF, 26, debt_repay_cf)\n    dividends = _get(g, CF, 27)\n    net_cash_fin = debt_draws + debt_repay_cf - dividends\n    _set(g, CF, 28, net_cash_fin)\n\n    net_change = net_cash_ops + net_cash_inv + net_cash_fin\n    _set(g, CF, 30, net_change)\n\n    beg_cash = _get(g, CF, 31)\n    end_cash = beg_cash + net_change\n    _set(g, CF, 32, end_cash)\n\n    # \u2500\u2500 5. Balance Sheet \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n    _set(g, BS, 5, end_cash)\n\n    curr_assets = end_cash + _get(g, BS, 6) + _get(g, BS, 7) + _get(g, BS, 8)\n    _set(g, BS, 9, curr_assets)\n\n    ppe_net = _get(g, BS, 11) - abs(_get(g, BS, 12))\n    _set(g, BS, 13, ppe_net)\n\n    non_curr = ppe_net + _get(g, BS, 14) + _get(g, BS, 15) + _get(g, BS, 16) + _get(g, BS, 17)\n    _set(g, BS, 18, non_curr)\n\n    total_assets = curr_assets + non_curr\n    _set(g, BS, 20, total_assets)\n\n    curr_liab = _get(g, BS, 23) + _get(g, BS, 24) + _get(g, BS, 25) + _get(g, BS, 26)\n    _set(g, BS, 27, curr_liab)\n\n    _set(g, BS, 29, sen_end)\n    _set(g, BS, 30, mezz_end)\n    total_lt_debt = sen_end + mezz_end\n    _set(g, BS, 31, total_lt_debt)\n\n    non_curr_liab = total_lt_debt + _get(g, BS, 32) + _get(g, BS, 33)\n    _set(g, BS, 34, non_curr_liab)\n\n    total_liab = curr_liab + non_curr_liab\n    _set(g, BS, 36, total_liab)\n\n    # RE rollforward\n    prev_re = _get(prev, BS, 40)\n    retained = prev_re + net_income - dividends\n    _set(g, BS, 40, retained)\n\n    total_equity = _get(g, BS, 39) + retained + _get(g, BS, 41)\n    _set(g, BS, 42, total_equity)\n    _set(g, BS, 44, total_liab + total_equity)\n    _set(g, BS, 45, total_assets - (total_liab + total_equity))\n\n    # \u2500\u2500 6. Derive new repayment from cash available \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n    cash_before_repay = end_cash + senior_repay + mezz_repay\n    new_sen = min(sen_begin + sen_draw, max(0.0, cash_before_repay))\n    remaining = max(0.0, cash_before_repay - new_sen)\n    new_mezz = min(mezz_begin + mezz_draw, max(0.0, remaining))\n\n    return g, new_sen, new_mezz\n\n\ndef post_process(cells, parsed_template=None):\n    \"\"\"\n    Main entry point. Fixed-point iteration solver for LBO circular references.\n    Only modifies: RetainedEarnings, BeginningCash(t>0), Repayments(t>0).\n    \"\"\"\n    # Parse flat cells into per-period grids\n    period_grids = {t: {} for t in range(6)}\n    cell_index = {}  # (sheet, row, period_idx) \u2192 index in cells list\n\n    for i, c in enumerate(cells):\n        ref = c.get(\"cell_ref\", \"\")\n        if not ref or len(ref) < 2:\n            continue\n        col_letter = ref[0].upper()\n        if col_letter not in COL_TO_PERIOD:\n            continue\n        try:\n            row_num = int(ref[1:])\n        except ValueError:\n            continue\n        t = COL_TO_PERIOD[col_letter]\n        sheet = c.get(\"sheet_name\", \"\")\n        val = c.get(\"value\", 0)\n        try:\n            val = float(val)\n        except (TypeError, ValueError):\n            val = 0.0\n\n        period_grids[t][(sheet, row_num)] = val\n        cell_index[(sheet, row_num, t)] = i\n\n    # \u2500\u2500 Phase 1: Balance historical period (t=0) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n    g0 = period_grids[0]\n\n    # Fix D&A sign: must be negative on IS\n    da0 = _get(g0, IS, 17)\n    if da0 > 0:\n        _set(g0, IS, 17, -da0)\n\n    # Fix repayment sign: must be positive for template formula\n    for repay_row in [7, 18]:\n        r = _get(g0, DS, repay_row)\n        if r < 0:\n            _set(g0, DS, repay_row, abs(r))\n\n    # Compute t=0 DS ending balances\n    sen_end0 = _get(g0, DS, 5) + _get(g0, DS, 6) - _get(g0, DS, 7)\n    mezz_end0 = _get(g0, DS, 16) + _get(g0, DS, 17) - _get(g0, DS, 18)\n    _set(g0, DS, 9, sen_end0)\n    _set(g0, DS, 20, mezz_end0)\n\n    # Compute t=0 BS totals for RE plug\n    cash0 = _get(g0, BS, 5)\n    curr_a0 = cash0 + _get(g0, BS, 6) + _get(g0, BS, 7) + _get(g0, BS, 8)\n    ppe_net0 = _get(g0, BS, 11) - abs(_get(g0, BS, 12))\n    non_curr_a0 = ppe_net0 + _get(g0, BS, 14) + _get(g0, BS, 15) + _get(g0, BS, 16) + _get(g0, BS, 17)\n    total_a0 = curr_a0 + non_curr_a0\n\n    curr_l0 = _get(g0, BS, 23) + _get(g0, BS, 24) + _get(g0, BS, 25) + _get(g0, BS, 26)\n    non_curr_l0 = sen_end0 + mezz_end0 + _get(g0, BS, 32) + _get(g0, BS, 33)\n    total_l0 = curr_l0 + non_curr_l0\n\n    known_eq0 = _get(g0, BS, 39) + _get(g0, BS, 41)\n    re0 = total_a0 - total_l0 - known_eq0\n    _set(g0, BS, 40, re0)\n\n    # Set t=0 EndCash for CF linkage\n    _set(g0, CF, 32, cash0)\n    _set(g0, CF, 31, cash0)\n\n    # \u2500\u2500 Phase 2: Fixed-point iteration for t=1..5 \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n    for t in range(1, 6):\n        prev = period_grids[t - 1]\n        sen_guess = 0.0\n        mezz_guess = 0.0\n\n        # Fix D&A sign for this period\n        da_t = _get(period_grids[t], IS, 17)\n        if da_t > 0:\n            _set(period_grids[t], IS, 17, -da_t)\n\n        for iteration in range(100):\n            g = copy.copy(period_grids[t])\n            g, new_sen, new_mezz = simulate_period(g, prev, sen_guess, mezz_guess)\n\n            if abs(new_sen - sen_guess) <= 1e-4 and abs(new_mezz - mezz_guess) <= 1e-4:\n                period_grids[t] = g\n                break\n\n            sen_guess = new_sen\n            mezz_guess = new_mezz\n\n    # \u2500\u2500 Phase 3: Write back ONLY determined input cells \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n    output = copy.deepcopy(cells)\n\n    for t in range(6):\n        g = period_grids[t]\n\n        # Fix D&A sign in output (must be negative on IS)\n        idx = cell_index.get((IS, 17, t))\n        if idx is not None:\n            output[idx][\"value\"] = -abs(_get(g, IS, 17))\n\n        # Fix repayment signs in output (must be positive)\n        for repay_row in [7, 18]:\n            idx = cell_index.get((DS, repay_row, t))\n            if idx is not None:\n                output[idx][\"value\"] = abs(_get(g, DS, repay_row))\n\n        # Retained Earnings \u2014 all periods\n        idx = cell_index.get((BS, 40, t))\n        if idx is not None:\n            output[idx][\"value\"] = round(_get(g, BS, 40), 2)\n\n        if t > 0:\n            # Beginning Cash\n            idx = cell_index.get((CF, 31, t))\n            if idx is not None:\n                output[idx][\"value\"] = round(_get(g, CF, 31), 2)\n\n            # Senior Repay (positive)\n            idx = cell_index.get((DS, 7, t))\n            if idx is not None:\n                output[idx][\"value\"] = round(abs(_get(g, DS, 7)), 2)\n\n            # Mezz Repay (positive)\n            idx = cell_index.get((DS, 18, t))\n            if idx is not None:\n                output[idx][\"value\"] = round(abs(_get(g, DS, 18)), 2)\n\n    return output\n",
  "language": "python",
  "truncated": false,
  "original_size": 11149
}

2. [Source 2] read_source_content({"source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/excel_io/parser.py"}): {
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/excel_io/parser.py",
  "content": "import openpyxl\nimport re\n\nclass InvalidTemplateError(Exception): pass\nclass TemplateNotEmptyError(Exception): pass\n\ndef parse_template(file_path: str) -> dict:\n    try:\n        wb = openpyxl.load_workbook(file_path, data_only=False)\n    except Exception as e:\n        raise InvalidTemplateError(f\"Corrupt or unsupported Excel file: {e}\")\n\n    result = {\n        \"file_name\": file_path.split(\"/\")[-1],\n        \"sheets\": [],\n        \"named_ranges\": [],\n        \"inter_sheet_refs\": [],\n        \"total_input_cells\": 0\n    }\n\n    year_pattern = re.compile(r\"(FY|CY)?\\d{4}[EA]?\")\n    inter_sheet_pattern = re.compile(r\"'?([^'!]+)'?!([A-Z]+\\d+)\")\n\n    # Known financial acronyms that are ALL CAPS but are real data rows\n    financial_acronyms = {\n        'EBITDA', 'EBIT', 'EBT', 'EPS', 'ROE', 'ROA', 'ROIC', 'WACC',\n        'IRR', 'MOIC', 'NPV', 'FCF', 'UFCF', 'LFCF', 'DSCR', 'SGA',\n        'COGS', 'CAPEX', 'NWC', 'PP&E', 'PPE', 'D&A',\n    }\n    # Section header keywords\n    section_keywords = {\n        'activities', 'assumptions', 'summary', 'schedule', 'guide',\n        'instructions', 'legend', 'disclaimer', 'notes',\n    }\n    # Single-word ALL CAPS section headers\n    section_singles = {\n        'ASSETS', 'LIABILITIES', 'EQUITY',\n    }\n    skip_exact = {\n        'formatting guide', 'blue text', 'black text', 'green text',\n        'notes', 'instructions', 'legend', 'source', 'disclaimer',\n        'input', 'link to another sheet', 'formula',\n    }\n    skip_contains = ['color code', 'formatting', 'legend', 'instruction']\n\n    def _is_section_header(name):\n        \"\"\"Detect section headers like OPERATING ACTIVITIES, TOTAL DEBT SUMMARY, etc.\"\"\"\n        stripped = name.strip()\n        # Skip known non-data rows\n        if stripped.lower() in skip_exact:\n            return True\n        if any(kw in stripped.lower() for kw in skip_contains):\n            return True\n        # Preserve known financial acronyms\n        if stripped.upper() in financial_acronyms:\n            return False\n        # Known single-word section headers\n        if stripped in section_singles:\n            return True\n        # ALL CAPS with 2+ words and contains a section keyword\n        if stripped == stripped.upper() and len(stripped) > 5 and ' ' in stripped:\n            lower = stripped.lower()\n            if any(kw in lower for kw in section_keywords):\n                return True\n            # Generic ALL CAPS multi-word headers (like \"SENIOR SECURED DEBT\", \"ASSETS\")\n            return True\n        return False\n\n    total_input = 0\n    total_cells_checked = 0\n    populated_input = 0\n\n    for ws in wb.worksheets:\n        sheet_data = {\n            \"name\": ws.title,\n            \"headers\": [],\n            \"input_cells\": [],\n            \"formula_cells\": [],\n            \"temporal_headers\": []\n        }\n\n        period_headers = []\n        header_row = 1\n        for col in range(2, ws.max_column + 1):\n            val = ws.cell(row=1, column=col).value\n            if val and year_pattern.search(str(val)):\n                period_headers.append({\"col\": col, \"val\": str(val).strip()})\n                if str(val).strip() not in sheet_data[\"temporal_headers\"]:\n                    sheet_data[\"temporal_headers\"].append(str(val).strip())\n        # If no periods found in row 1, try row 2\n        if not period_headers:\n            header_row = 2\n            for col in range(2, ws.max_column + 1):\n                val = ws.cell(row=2, column=col).value\n                if val and year_pattern.search(str(val)):\n                    period_headers.append({\"col\": col, \"val\": str(val).strip()})\n                    if str(val).strip() not in sheet_data[\"temporal_headers\"]:\n                        sheet_data[\"temporal_headers\"].append(str(val).strip())\n\n        # If no period headers found, treat columns B+ as single-value inputs\n        if not period_headers:\n            for row in range(2, ws.max_row + 1):\n                line_item_val = ws.cell(row=row, column=1).value\n                if not line_item_val:\n                    continue\n                header_name = str(line_item_val).strip()\n                is_section = _is_section_header(header_name)\n                sheet_data[\"headers\"].append({\"row\": row, \"header\": header_name, \"is_section\": is_section})\n                if is_section:\n                    continue\n                # Scan columns B onwards for input/formula cells\n                for col in range(2, min(ws.max_column + 1, 8)):  # cap at col G\n                    cell = ws.cell(row=row, column=col)\n                    val = cell.value\n                    coord = cell.coordinate\n                    total_cells_checked += 1\n                    if val is None or str(val).strip() == \"\":\n                        sheet_data[\"input_cells\"].append({\"ref\": coord, \"column_header\": header_name, \"period\": \"Value\"})\n                        total_input += 1\n                    elif isinstance(val, str) and val.startswith(\"=\"):\n                        sheet_data[\"formula_cells\"].append({\"ref\": coord, \"formula\": val, \"column_header\": header_name})\n                        matches = inter_sheet_pattern.findall(val)\n                        for match in matches:\n                            target_sheet, target_cell = match\n                            if target_sheet != ws.title:\n                                result[\"inter_sheet_refs\"].append({\n                                    \"source_sheet\": ws.title, \"source_cell\": coord,\n                                    \"target_sheet\": target_sheet, \"target_cell\": target_cell\n                                })\n                    else:\n                        populated_input += 1\n                        sheet_data[\"input_cells\"].append({\"ref\": coord, \"column_header\": header_name, \"period\": \"Value\"})\n                        total_input += 1\n            result[\"sheets\"].append(sheet_data)\n            continue\n\n        data_start_row = header_row + 1\n        current_section = \"\"  # Track which section we're in for disambiguation\n        for row in range(data_start_row, ws.max_row + 1):\n            line_item_val = ws.cell(row=row, column=1).value\n            if not line_item_val:\n                continue\n\n            header_name = str(line_item_val).strip()\n            is_section = _is_section_header(header_name)\n            sheet_data[\"headers\"].append({\"row\": row, \"header\": header_name, \"is_section\": is_section})\n\n            # Track section context, skip section headers as data rows\n            if is_section:\n                current_section = header_name\n                continue\n\n            # Build disambiguated header: \"SENIOR SECURED DEBT > Beginning Balance\"\n            if current_section:\n                qualified_header = f\"{current_section} > {header_name}\"\n            else:\n                qualified_header = header_name\n\n            for p in period_headers:\n                cell = ws.cell(row=row, column=p[\"col\"])\n                val = cell.value\n                coord = cell.coordinate\n\n                total_cells_checked += 1\n                if val is None or str(val).strip() == \"\":\n                    sheet_data[\"input_cells\"].append({\"ref\": coord, \"column_header\": qualified_header, \"period\": p[\"val\"]})\n                    total_input += 1\n                elif isinstance(val, str) and val.startswith(\"=\"):\n                    sheet_data[\"formula_cells\"].append({\"ref\": coord, \"formula\": val, \"column_header\": header_name})\n\n                    matches = inter_sheet_pattern.findall(val)\n                    for match in matches:\n                        target_sheet, target_cell = match\n                        if target_sheet != ws.title:\n                            result[\"inter_sheet_refs\"].append({\n                                \"source_sheet\": ws.title,\n                                \"source_cell\": coord,\n                                \"target_sheet\": target_sheet,\n                                \"target_cell\": target_cell\n                            })\n                else:\n                    populated_input += 1\n                    sheet_data[\"input_cells\"].append({\"ref\": coord, \"column_header\": qualified_header, \"period\": p[\"val\"]})\n                    total_input += 1\n\n        result[\"sheets\"].append(sheet_data)\n\n    if total_input > 0 and (populated_input / total_input) > 0.15:\n        raise TemplateNotEmptyError(\"File contains too much data in input cells. Upload an empty template.\")\n\n    result[\"total_input_cells\"] = total_input\n\n    # openpyxl 3.1+ uses DefinedNameDict which is directly iterable\n    try:\n        for name in wb.defined_names.values():\n            result[\"named_ranges\"].append({\n                \"name\": name.name,\n                \"cell_range\": name.attr_text\n            })\n    except Exception:\n        pass  # No named ranges or incompatible API \u2014 not critical\n\n    return result\n",
  "language": "python",
  "truncated": false,
  "original_size": 8845
}

3. [Source 3] read_source_content({"source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/main.py"}): {
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/main.py",
  "content": "import os\nimport uuid\nimport json\nimport asyncio\nimport logging\nfrom fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException\nfrom fastapi.middleware.cors import CORSMiddleware\nfrom fastapi.responses import FileResponse\nfrom backend.config import get_settings\nfrom backend.orchestrator import PipelineOrchestrator\nfrom backend.models.schemas import JobState\nfrom backend.middleware.logging_middleware import StructuredLoggingMiddleware\nfrom backend.health import router as health_router\n\nfrom fastapi.staticfiles import StaticFiles\n\nlogging.basicConfig(level=logging.INFO, format='%(message)s')\nlogger = logging.getLogger(__name__)\n\napp = FastAPI()\napp.include_router(health_router)\napp.add_middleware(StructuredLoggingMiddleware)\n\napp.mount(\"/templates\", StaticFiles(directory=\"templates\"), name=\"templates\")\nsettings = get_settings()\n\nallowed_origins = [\n    \"http://localhost:5173\",\n    \"http://localhost:5174\",\n    \"http://localhost:5175\",\n    os.getenv(\"FRONTEND_ORIGIN\", \"\"),\n]\nallowed_origins = [o for o in allowed_origins if o]\n\napp.add_middleware(\n    CORSMiddleware,\n    allow_origins=allowed_origins,\n    allow_credentials=True,\n    allow_methods=[\"*\"],\n    allow_headers=[\"*\"],\n)\n\norchestrator = PipelineOrchestrator(settings)\n\n\ndef _get_google_creds(sa_path: str):\n    \"\"\"Load OAuth user credentials (preferred) or fall back to service account.\"\"\"\n    import os\n    token_path = os.path.join(os.path.dirname(sa_path), 'oauth_token.json')\n    if os.path.exists(token_path):\n        from google.oauth2.credentials import Credentials\n        creds = Credentials.from_authorized_user_file(token_path)\n        if creds and creds.expired and creds.refresh_token:\n            from google.auth.transport.requests import Request\n            creds.refresh(Request())\n            # Save refreshed token\n            import json\n            with open(token_path, 'w') as f:\n                json.dump({\n                    'token': creds.token,\n                    'refresh_token': creds.refresh_token,\n                    'token_uri': creds.token_uri,\n                    'client_id': creds.client_id,\n                    'client_secret': creds.client_secret,\n                    'scopes': list(creds.scopes or []),\n                }, f)\n        return creds\n    else:\n        from google.oauth2 import service_account\n        SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']\n        return service_account.Credentials.from_service_account_file(sa_path, scopes=SCOPES)\n\n\ndef _create_sheet_from_xlsx(xlsx_path: str, title: str, sa_path: str, add_validation: bool = False) -> dict:\n    \"\"\"Read xlsx with openpyxl, create Google Sheet via Sheets API, write all data.\"\"\"\n    import openpyxl\n    from googleapiclient.discovery import build\n\n    creds = _get_google_creds(sa_path)\n    sheets_svc = build('sheets', 'v4', credentials=creds)\n    drive_svc = build('drive', 'v3', credentials=creds)\n\n    # Read xlsx\n    wb = openpyxl.load_workbook(xlsx_path, data_only=False)\n\n    # Create spreadsheet with correct sheet names\n    sheet_props = [{\"properties\": {\"title\": ws.title}} for ws in wb.worksheets]\n    body = {\"properties\": {\"title\": title}, \"sheets\": sheet_props}\n    spreadsheet = sheets_svc.spreadsheets().create(body=body, fields='spreadsheetId').execute()\n    spreadsheet_id = spreadsheet['spreadsheetId']\n\n    # Write data sheet by sheet\n    data = []\n    for ws in wb.worksheets:\n        rows = []\n        for row in ws.iter_rows(min_row=1, max_row=ws.max_row, max_col=ws.max_column):\n            row_data = []\n            for cell in row:\n                val = cell.value\n                if val is None:\n                    row_data.append({\"userEnteredValue\": {\"stringValue\": \"\"}})\n                elif isinstance(val, str) and val.startswith(\"=\"):\n                    row_data.append({\"userEnteredValue\": {\"formulaValue\": val}})\n                elif isinstance(val, bool):\n                    row_data.append({\"userEnteredValue\": {\"boolValue\": val}})\n                elif isinstance(val, (int, float)):\n                    row_data.append({\"userEnteredValue\": {\"numberValue\": val}})\n                else:\n                    row_data.append({\"userEnteredValue\": {\"stringValue\": str(val)}})\n            rows.append({\"values\": row_data})\n\n        # Find the sheet ID\n        sheet_meta = sheets_svc.spreadsheets().get(\n            spreadsheetId=spreadsheet_id, fields='sheets.properties'\n        ).execute()\n        sheet_id = None\n        for s in sheet_meta['sheets']:\n            if s['properties']['title'] == ws.title:\n                sheet_id = s['properties']['sheetId']\n                break\n\n        if sheet_id is not None:\n            data.append({\n                \"updateCells\": {\n                    \"rows\": rows,\n                    \"fields\": \"userEnteredValue\",\n                    \"start\": {\"sheetId\": sheet_id, \"rowIndex\": 0, \"columnIndex\": 0},\n                }\n            })\n\n    if data:\n        sheets_svc.spreadsheets().batchUpdate(\n            spreadsheetId=spreadsheet_id,\n            body={\"requests\": data},\n        ).execute()\n\n    # Add Validation sheet with live formulas (only for generated output, not templates)\n    if add_validation:\n        _add_validation_sheet(sheets_svc, spreadsheet_id, wb)\n\n    # Make publicly viewable\n    drive_svc.permissions().create(\n        fileId=spreadsheet_id,\n        body={'type': 'anyone', 'role': 'reader'},\n    ).execute()\n\n    embed_url = f\"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit?embedded=true&rm=minimal\"\n    view_url = f\"https://docs.google.com/spreadsheets/d/{spreadsheet_id}\"\n\n    return {\"embed_url\": embed_url, \"view_url\": view_url, \"sheet_id\": spreadsheet_id}\n\n\ndef _add_validation_sheet(sheets_svc, spreadsheet_id: str, wb):\n    \"\"\"Add a 'Validation' sheet with live formulas proving data integrity.\"\"\"\n    import re\n\n    # Check which sheets exist\n    sheet_names = [ws.title for ws in wb.worksheets]\n    has_is = 'Income Statement' in sheet_names\n    has_bs = 'Balance Sheet' in sheet_names\n    has_cf = 'Cash Flow Statement' in sheet_names\n    has_ds = 'Debt Schedule' in sheet_names\n    has_ra = 'Returns Analysis' in sheet_names\n\n    # Detect periods from row 2 of Income Statement (or row 1)\n    periods = []\n    if has_is:\n        ws = wb['Income Statement']\n        for col in range(2, ws.max_column + 1):\n            for r in [2, 1]:\n                val = ws.cell(row=r, column=col).value\n                if val and re.search(r'(FY|CY)?\\d{4}', str(val)):\n                    periods.append({\"col_letter\": chr(64 + col), \"label\": str(val).strip()})\n                    break\n    if not periods:\n        return  # Can't build validation without periods\n\n    cols = [p[\"col_letter\"] for p in periods]\n\n    # Add the validation sheet\n    sheets_svc.spreadsheets().batchUpdate(\n        spreadsheetId=spreadsheet_id,\n        body={\"requests\": [{\"addSheet\": {\"properties\": {\"title\": \"\u2713 Validation\"}}}]},\n    ).execute()\n\n    # Build validation rows\n    rows = []\n\n    def _header(text):\n        return [{\"userEnteredValue\": {\"stringValue\": text}, \"userEnteredFormat\": {\"textFormat\": {\"bold\": True, \"fontSize\": 11}}}]\n\n    def _label(text):\n        return [{\"userEnteredValue\": {\"stringValue\": text}}]\n\n    def _formula_row(label, formulas):\n        \"\"\"Row with label in A, formulas in B onwards.\"\"\"\n        r = [{\"userEnteredValue\": {\"stringValue\": label}}]\n        for f in formulas:\n            r.append({\"userEnteredValue\": {\"formulaValue\": f}})\n        return r\n\n    def _status_row(label, check_formulas):\n        \"\"\"Row with label in A, PASS/FAIL checks in B onwards.\"\"\"\n        r = [{\"userEnteredValue\": {\"stringValue\": label}}]\n        for f in check_formulas:\n            r.append({\"userEnteredValue\": {\"formulaValue\": f}})\n        return r\n\n    # Title\n    rows.append({\"values\": _header(\"SAFE-HARBOR VALIDATION REPORT\")})\n    rows.append({\"values\": _label(\"All checks are live Google Sheets formulas \u2014 click any cell to verify.\")})\n    rows.append({\"values\": []})  # blank\n\n    # Period headers row\n    period_row = [{\"userEnteredValue\": {\"stringValue\": \"\"}}]\n    for p in periods:\n        period_row.append({\"userEnteredValue\": {\"stringValue\": p[\"label\"]}, \"userEnteredFormat\": {\"textFormat\": {\"bold\": True}}})\n    rows.append({\"values\": period_row})\n\n    # \u2500\u2500 Section 1: Balance Sheet Identity \u2500\u2500\n    rows.append({\"values\": []})\n    rows.append({\"values\": _header(\"1. BALANCE SHEET IDENTITY (Assets = Liabilities + Equity)\")})\n    if has_bs:\n        rows.append({\"values\": _formula_row(\"Total Assets\", [f\"='Balance Sheet'!{c}20\" for c in cols])})\n        rows.append({\"values\": _formula_row(\"Total Liabilities\", [f\"='Balance Sheet'!{c}36\" for c in cols])})\n        rows.append({\"values\": _formula_row(\"Total Equity\", [f\"='Balance Sheet'!{c}42\" for c in cols])})\n        rows.append({\"values\": _formula_row(\"\u0394 (Assets - L - E)\", [f\"='Balance Sheet'!{c}20-('Balance Sheet'!{c}36+'Balance Sheet'!{c}42)\" for c in cols])})\n        rows.append({\"values\": _status_row(\"\u2713 Status\", [f'=IF(ABS(\\'Balance Sheet\\'!{c}20-(\\'Balance Sheet\\'!{c}36+\\'Balance Sheet\\'!{c}42))<1,\"PASS\",\"FAIL\")' for c in cols])})\n\n    # \u2500\u2500 Section 2: Gross Margin \u2500\u2500\n    rows.append({\"values\": []})\n    rows.append({\"values\": _header(\"2. MARGIN ANALYSIS\")})\n    if has_is:\n        rows.append({\"values\": _formula_row(\"Revenue\", [f\"='Income Statement'!{c}4\" for c in cols])})\n        rows.append({\"values\": _formula_row(\"Gross Profit\", [f\"='Income Statement'!{c}6\" for c in cols])})\n        rows.append({\"values\": _formula_row(\"Gross Margin %\", [f\"='Income Statement'!{c}6/'Income Statement'!{c}4\" for c in cols])})\n        rows.append({\"values\": _formula_row(\"EBITDA\", [f\"='Income Statement'!{c}14\" for c in cols])})\n        rows.append({\"values\": _formula_row(\"EBITDA Margin %\", [f\"='Income Statement'!{c}14/'Income Statement'!{c}4\" for c in cols])})\n        rows.append({\"values\": _formula_row(\"Net Income\", [f\"='Income Statement'!{c}29\" for c in cols])})\n        rows.append({\"values\": _formula_row(\"Net Margin %\", [f\"='Income Statement'!{c}29/'Income Statement'!{c}4\" for c in cols])})\n        rows.append({\"values\": _status_row(\"\u2713 Margins in range\", [f'=IF(AND(\\'Income Statement\\'!{c}6/\\'Income Statement\\'!{c}4>0,\\'Income Statement\\'!{c}6/\\'Income Statement\\'!{c}4<1),\"PASS\",\"FAIL\")' for c in cols])})\n\n    # \u2500\u2500 Section 3: Revenue Growth \u2500\u2500\n    rows.append({\"values\": []})\n    rows.append({\"values\": _header(\"3. REVENUE GROWTH RATE\")})\n    if has_is and len(cols) > 1:\n        growth_formulas = [\"\"] + [f\"='Income Statement'!{cols[i]}4/'Income Statement'!{cols[i-1]}4-1\" for i in range(1, len(cols))]\n        rows.append({\"values\": _formula_row(\"YoY Growth %\", growth_formulas)})\n        rows.append({\"values\": _formula_row(\"Avg Growth\", [\"\", f\"=AVERAGE({cols[1]}{'len(rows)'}:{cols[-1]}{'len(rows)'})\" if len(cols) > 2 else \"\"])})\n\n    # \u2500\u2500 Section 4: Cash Flow Reconciliation \u2500\u2500\n    rows.append({\"values\": []})\n    rows.append({\"values\": _header(\"4. CASH FLOW RECONCILIATION\")})\n    if has_cf:\n        rows.append({\"values\": _formula_row(\"Beginning Cash\", [f\"='Cash Flow Statement'!{c}31\" for c in cols])})\n        rows.append({\"values\": _formula_row(\"Net Change in Cash\", [f\"='Cash Flow Statement'!{c}30\" for c in cols])})\n        rows.append({\"values\": _formula_row(\"Ending Cash\", [f\"='Cash Flow Statement'!{c}32\" for c in cols])})\n        rows.append({\"values\": _formula_row(\"\u0394 (End - Begin - Net)\", [f\"='Cash Flow Statement'!{c}32-'Cash Flow Statement'!{c}31-'Cash Flow Statement'!{c}30\" for c in cols])})\n        rows.append({\"values\": _status_row(\"\u2713 Status\", [f'=IF(ABS(\\'Cash Flow Statement\\'!{c}32-\\'Cash Flow Statement\\'!{c}31-\\'Cash Flow Statement\\'!{c}30)<1,\"PASS\",\"FAIL\")' for c in cols])})\n\n    # \u2500\u2500 Section 5: Debt Schedule Rollforward \u2500\u2500\n    rows.append({\"values\": []})\n    rows.append({\"values\": _header(\"5. DEBT SCHEDULE \u2014 SENIOR SECURED\")})\n    if has_ds:\n        rows.append({\"values\": _formula_row(\"Beginning Balance\", [f\"='Debt Schedule'!{c}5\" for c in cols])})\n        rows.append({\"values\": _formula_row(\"+ Drawdowns\", [f\"='Debt Schedule'!{c}6\" for c in cols])})\n        rows.append({\"values\": _formula_row(\"- Repayments\", [f\"='Debt Schedule'!{c}7\" for c in cols])})\n        rows.append({\"values\": _formula_row(\"= Ending Balance\", [f\"='Debt Schedule'!{c}9\" for c in cols])})\n        rows.append({\"values\": _formula_row(\"\u0394 (End - Begin - Draw + Repay)\", [f\"='Debt Schedule'!{c}9-('Debt Schedule'!{c}5+'Debt Schedule'!{c}6+'Debt Schedule'!{c}7)\" for c in cols])})\n        rows.append({\"values\": _status_row(\"\u2713 Status\", [f'=IF(ABS(\\'Debt Schedule\\'!{c}9-(\\'Debt Schedule\\'!{c}5+\\'Debt Schedule\\'!{c}6+\\'Debt Schedule\\'!{c}7))<1,\"PASS\",\"FAIL\")' for c in cols])})\n\n    # \u2500\u2500 Section 6: Cross-Sheet Linkage \u2500\u2500\n    rows.append({\"values\": []})\n    rows.append({\"values\": _header(\"6. CROSS-SHEET LINKAGE\")})\n    if has_is and has_cf:\n        rows.append({\"values\": _formula_row(\"IS: D&A\", [f\"='Income Statement'!{c}17\" for c in cols])})\n        rows.append({\"values\": _formula_row(\"CF: D&A Add-back\", [f\"='Cash Flow Statement'!{c}6\" for c in cols])})\n        rows.append({\"values\": _formula_row(\"\u0394 (IS D&A - CF D&A)\", [f\"=ABS('Income Statement'!{c}17)-ABS('Cash Flow Statement'!{c}6)\" for c in cols])})\n        rows.append({\"values\": _status_row(\"\u2713 D&A Linkage\", [f'=IF(ABS(ABS(\\'Income Statement\\'!{c}17)-ABS(\\'Cash Flow Statement\\'!{c}6))<1,\"PASS\",\"FAIL\")' for c in cols])})\n    if has_is and has_ds:\n        rows.append({\"values\": _formula_row(\"IS: Total Interest\", [f\"='Income Statement'!{c}23\" for c in cols])})\n        rows.append({\"values\": _formula_row(\"DS: Total Interest\", [f\"='Debt Schedule'!{c}27\" for c in cols])})\n        rows.append({\"values\": _status_row(\"\u2713 Interest Linkage\", [f'=IF(ABS(ABS(\\'Income Statement\\'!{c}23)-ABS(\\'Debt Schedule\\'!{c}27))<1,\"PASS\",\"FAIL\")' for c in cols])})\n\n    # \u2500\u2500 Section 7: Statistical Summary \u2500\u2500\n    rows.append({\"values\": []})\n    rows.append({\"values\": _header(\"7. STATISTICAL DISTRIBUTION\")})\n    if has_is:\n        rev_range = f\"'Income Statement'!{cols[0]}4:{cols[-1]}4\"\n        margin_range = f\"'Income Statement'!{cols[0]}7:{cols[-1]}7\"\n        rows.append({\"values\": [\n            {\"userEnteredValue\": {\"stringValue\": \"Revenue\"}},\n            {\"userEnteredValue\": {\"stringValue\": \"Mean\"}},\n            {\"userEnteredValue\": {\"formulaValue\": f\"=AVERAGE({rev_range})\"}},\n            {\"userEnteredValue\": {\"stringValue\": \"Std Dev\"}},\n            {\"userEnteredValue\": {\"formulaValue\": f\"=STDEV({rev_range})\"}},\n            {\"userEnteredValue\": {\"stringValue\": \"CV\"}},\n            {\"userEnteredValue\": {\"formulaValue\": f\"=STDEV({rev_range})/AVERAGE({rev_range})\"}},\n        ]})\n        rows.append({\"values\": [\n            {\"userEnteredValue\": {\"stringValue\": \"Gross Margin\"}},\n            {\"userEnteredValue\": {\"stringValue\": \"Mean\"}},\n            {\"userEnteredValue\": {\"formulaValue\": f\"=AVERAGE({margin_range})\"}},\n            {\"userEnteredValue\": {\"st\n\n... [File truncated: 9340 chars omitted]",
  "language": "python",
  "truncated": true,
  "original_size": 24340
}

4. [Source 4] code_grep({"repository_id": "Kaide-LABS/tracelight-safe-harbor", "pattern": "Section [78]|RETURNS|_add_validation_sheet|SUMMARY DASHBOARD|has_ra|add_validation", "path": "safe-harbor/backend/main.py", "context_lines": 5}): {
  "success": true,
  "matches": {},
  "pattern": "Section [78]|RETURNS|_add_validation_sheet|SUMMARY DASHBOARD|has_ra|add_validation",
  "path_filter": "safe-harbor/backend/main.py",
  "total_matches": 0,
  "files_searched": 0,
  "files_with_matches": 0,
  "truncated": false,
  "options": {
    "case_sensitive": false,
    "lines_before": 5,
    "lines_after": 5,
    "output_mode": "content",
    "whole_word": false,
    "fixed_string": false,
    "highlight": false,
    "include_line_numbers": true,
    "group_by_file": true
  }
}

5. [Source 5] code_grep({"repository_id": "Kaide-LABS/tracelight-safe-harbor", "pattern": "RETURNS|SUMMARY DASHBOARD|has_ra|Section 8", "context_lines": 5}): {
  "success": true,
  "matches": {
    "Kaide-LABS/tracelight-safe-harbor/CONTEXT.md": [
      {
        "path": "Kaide-LABS/tracelight-safe-harbor/CONTEXT.md",
        "line": "The Chief Executive Officer, Peter Fuller, operates with a strategic pragmatism forged during his tenure as an Engagement Manager at McKinsey & Company and QuantumBlack.7 His professional trajectory reflects a rigorous focus on digital transformation, operational value creation, and verifiable return on investment.7 From an operational standpoint, his recent communications indicate a strategic preoccupation with the friction inherent in enterprise sales cycles.7 However, he views this friction through a highly pragmatic lens. The evidence suggests that he believes slow internal approval processes and rigorous security requirements should not be bypassed via insecure shortcuts; rather, they serve as a useful filter for enterprise software viability, ensuring that organizations only adopt tools of genuine consequence.7 A critical operational bottleneck identified in his professional network is the inability of enterprise clients to efficiently test software due to strict information security restrictions on live, sensitive data. To navigate these approval processes without violating compliance protocols, the creation of robust testing environments utilizing non-sensitive, structurally accurate test data is deemed essential.7 Consequently, any architectural proposal must be positioned as a tangible mechanism to shorten the enterprise sales cycle and directly address these security blockers, focusing on macroeconomic impact, verifiable returns, and strategic enablement.9  ",
        "context": "To accelerate enterprise adoption without compromising the integrity of Tracelight\u2019s core proprietary engine, this analysis outlines a strategic mandate for adjacent, multi-agent artificial intelligence workflows. Through a rigorous psychological and operational deconstruction of the founding team, three distinct architectural \"sidecar\" blueprints have been engineered. These workflows\u2014spanning pre-core synthetic data ingestion, post-core artifact synthesis, and parallel security compliance\u2014adhere to the highest standards of technical pragmatism, deterministic fallback logic, and visual proof. By integrating these systems, the enterprise sales cycle can be significantly compressed, directly neutralizing Tracelight's current operational bottlenecks regarding information security approvals and downstream artifact generation.\n\n## **Intelligence Synthesis: Psychological and Architectural Teardown of the Founding Matrix**\n\nThe Tracelight founding team represents a rare convergence of elite strategic consulting, high-frequency quantitative engineering, and hyper-growth product scaling. Engaging this specific matrix of leadership requires discarding conventional marketing rhetoric in favor of high-leverage architectural reasoning. The psychological and technical profiles of the founders dictate the precise communication strategy and architectural design parameters for all proposed solutions.  \nThe Chief Executive Officer, Peter Fuller, operates with a strategic pragmatism forged during his tenure as an Engagement Manager at McKinsey & Company and QuantumBlack.7 His professional trajectory reflects a rigorous focus on digital transformation, operational value creation, and verifiable return on investment.7 From an operational standpoint, his recent communications indicate a strategic preoccupation with the friction inherent in enterprise sales cycles.7 However, he views this friction through a highly pragmatic lens. The evidence suggests that he believes slow internal approval processes and rigorous security requirements should not be bypassed via insecure shortcuts; rather, they serve as a useful filter for enterprise software viability, ensuring that organizations only adopt tools of genuine consequence.7 A critical operational bottleneck identified in his professional network is the inability of enterprise clients to efficiently test software due to strict information security restrictions on live, sensitive data. To navigate these approval processes without violating compliance protocols, the creation of robust testing environments utilizing non-sensitive, structurally accurate test data is deemed essential.7 Consequently, any architectural proposal must be positioned as a tangible mechanism to shorten the enterprise sales cycle and directly address these security blockers, focusing on macroeconomic impact, verifiable returns, and strategic enablement.9  \nThe Chief Technology Officer, Aleksander Misztal, brings an uncompromising engineering pedigree to the organization, heavily influenced by his tenure as a Software Engineer at Jane Street and his foundational work in Zero-Knowledge cryptography at Nethermind.7 Jane Street is globally recognized for its utilization of functional programming, specifically OCaml, memory-safe stack allocations, and the design of deterministic, high-performance systems operating in highly complex, low-latency financial environments.10 Furthermore, an operational background in Zero-Knowledge cryptography implies a deep-seated architectural preference for systems built on mathematical proofs, privacy preservation, and formal verification.7 The technical philosophy driving this architecture centers on human-machine augmentation through precision tooling. The platform is described as an artificial intelligence engine for complex financial modeling, focusing on building coding agents that fit precisely into professional analyst workflows.7 Because spreadsheets are fundamentally deterministic environments, applying stochastic language models to this domain requires translating spreadsheet logic into parsable, rule-based structures, effectively treating the workbook as a Directed Acyclic Graph.3 Architectural proposals must therefore employ high-leverage terminology, speaking in terms of deterministic fallbacks, topological sorting, strict data boundaries, and verifiable execution.7 Any proposed workflow must demonstrate how it mitigates language model hallucination through hardcoded, rule-based mathematical validations.  \nThe Chief Product Officer, Janek Zimoch, combines the mathematical rigor of a former Standard Chartered Bank Quantitative Researcher with the hyper-growth product engineering experience of scaling an autonomous outbound enterprise.7 Holding a Master of Philosophy in Machine Learning from the University of Cambridge, a deep theoretical understanding of neural networks and large language models informs the product vision.7 Previous experience includes building the personalization module for an autonomous, multi-agent outbound pipeline at a rapidly scaling startup, demonstrating the capability to deploy language models for dynamic, real-world execution at scale.7 The prevailing product philosophy revolves around creating frictionless, high-aesthetic user experiences. The interface is designed so that users do not have to worry about prompt engineering, pushing the complexity to the backend to achieve a seamless user experience.7 The transformation of raw mathematical logic into beautiful, shareable webpages is highly valued, ensuring that the final output is not just mathematically sound, but highly consumable by executive stakeholders.7 Workflows pitched to this profile must highlight multi-agent orchestration, dynamic context injection, and native user interfaces, proving how the proposed architectures eliminate user friction and output flawlessly formatted, client-ready artifacts.  \nThe table below synthesizes the founding team's psychographics and maps them to the required architectural pitch parameters.\n\n| Executive Profile | Pedigree & Background | Core Architectural Values | Pitch Mapping & Triggers |",
        "line_number": 11,
        "context_start_line": 6
      },
      {
        "path": "Kaide-LABS/tracelight-safe-harbor/CONTEXT.md",
        "line": "While the platform excels at making analysts highly efficient at building complex logic inside the spreadsheet 5, the quantitative model is rarely the final deliverable in institutional finance. In private equity and asset management, the model serves as the foundation for the Investment Committee Memo. This narrative document, typically fifteen to thirty pages in length, details the investment thesis, comprehensive market sizing, financial returns, and associated risks.21 Under current operational paradigms, analysts must manually transcribe final calculated arrays from the spreadsheet into Microsoft Word. This manual transcription is highly prone to human error, formatting fatigue, and version control issues, causing significant downstream friction.21  ",
        "context": "| Synthetic Generation Agent | Tabular GAN / Diffusion Model | Generate statistically realistic, covariance-aware financial time-series data.17 | Bounded numerical generation limited by historical industry standard deviations. |\n| Deterministic Validation Agent | Python (Pandas/NumPy) | Enforce double-entry accounting rules and inter-statement referential integrity.15 | Hardcoded algebraic assertions (Assets \\= Liabilities \\+ Equity); forced plug-account adjustments. |\n\n## **Post-Core Architecture: The QuantumBlack-Grade Investment Committee Memo Synthesizer**\n\nWhile the platform excels at making analysts highly efficient at building complex logic inside the spreadsheet 5, the quantitative model is rarely the final deliverable in institutional finance. In private equity and asset management, the model serves as the foundation for the Investment Committee Memo. This narrative document, typically fifteen to thirty pages in length, details the investment thesis, comprehensive market sizing, financial returns, and associated risks.21 Under current operational paradigms, analysts must manually transcribe final calculated arrays from the spreadsheet into Microsoft Word. This manual transcription is highly prone to human error, formatting fatigue, and version control issues, causing significant downstream friction.21  \nThe solution is a post-core orchestration engine designed to monitor the finalized state of the mathematical graph. Upon user command, this engine extracts the deterministic outputs and autonomously authors a perfectly formatted, McKinsey-grade Investment Committee Memo, dynamically grounded by real-time external market intelligence. This architecture functions purely downstream, leveraging the completed quantitative work to automate the qualitative presentation.  \nThe technical architecture for this synthesizer utilizes a Next.js user interface embedded seamlessly as a sidebar or modal within the existing Excel Add-in. The backend operates on a Python FastAPI orchestration layer that coordinates a highly specialized multi-agent engine. The first component is the State Observer Agent, a Python-based monitor that interfaces with the finalized Directed Acyclic Graph. When the user flags the financial model as complete, this agent extracts the key output nodes\u2014such as the calculated Exit Internal Rate of Return, the Multiple on Invested Capital, Enterprise Value, and base versus downside case EBITDA figures\u2014without disturbing the internal dependency logic or altering the workbook.  \nOperating in parallel is the Oracle Research Agent, leveraging Gemini 1.5 Pro via Google Vertex AI. This model is specifically selected for its massive context window and robust real-time grounding capabilities. It extracts the target company name and industry sector from the model and executes a live web search for recent macroeconomic headwinds, competitor valuation multiples, and emerging regulatory risks. This ensures that the qualitative sections of the memo are highly relevant and grounded in current reality. The Synthesis and Authoring Agent, powered by Claude 3.5 Sonnet, receives both the deterministic financial outputs and the grounded market research. It drafts the distinct sections of the Investment Committee Memo\u2014including the Executive Summary, Market Analysis, Financial Projections, and Risks and Mitigants\u2014meticulously matching the strict, narrative-driven, structured tone characteristic of top-tier strategy consultancies.21 Finally, a Formatting Engine utilizing LaTeX and Pandoc bypasses the formatting errors commonly associated with language models by compiling the structured JSON output directly into a perfectly styled, firm-branded PDF or DOCX file.  \nThe execution flow is initiated when an analyst completes an analysis, such as an annual recurring revenue snowball or a discounted cash flow valuation, and triggers the generation sequence.24 Parallel execution commences immediately: the Observer Agent extracts the hard financial metrics, while the Research Agent queries live macroeconomic data. Claude 3.5 Sonnet then synthesizes this data into a narrative draft, utilizing strict JSON schemas to ensure no required section of the institutional memo is omitted.22 To guarantee system resilience and immunity against hallucination, a deterministic string-matching script compares every financial number generated in the text narrative against the raw payload extracted directly from the mathematical graph. If a hallucinated discrepancy is detected\u2014for instance, if the generated text states a return of 25.4 percent while the deterministic graph calculated 24.5 percent\u2014the system forcefully overwrites the text with the exact source-of-truth value. A beautifully formatted document is then generated and presented for download.  \nThis workflow provides a profound user experience enhancement. A synthesis dashboard slides into view, presenting a split-screen interface. On the left, the user views the finalized Excel model; on the right, the Investment Committee Memo is drafted in real-time. Dynamic badges display the system's underlying processes, indicating that market risks are being grounded via live search, followed by a notification that financial metrics are being verified against the model state. The analyst watches hours of narrative drafting compress into under a minute. This aligns perfectly with the product philosophy of turning spreadsheets into beautiful, shareable artifacts, eliminating the friction between the quantitative model and the qualitative presentation without requiring complex prompt engineering from the user.7 Furthermore, this expands the total addressable market of the platform. It evolves the offering from a faster modeling tool into a comprehensive automation engine for the entire due diligence and deal execution lifecycle, delivering the macroeconomic impact demanded by enterprise leadership.  ",
        "line_number": 45,
        "context_start_line": 40
      },
      {
        "path": "Kaide-LABS/tracelight-safe-harbor/CONTEXT.md",
        "line": "| Deal Structure & Returns | State Observer Agent (Python) | Deterministic extraction of IRR, MOIC, and debt tranches from the LBO waterfall.22 |",
        "context": "| :---- | :---- | :---- |\n| Executive Summary | Synthesis Agent (Claude 3.5) | Aggregates outputs from all other agents into a concise narrative thesis.22 |\n| Market Analysis | Oracle Research Agent (Gemini) | Live web search for TAM, sector headwinds, and competitor multiples. |\n| Financial Projections | State Observer Agent (Python) | Direct, deterministic extraction from the finalized Tracelight DAG nodes. |\n| Risks & Mitigants | Synthesis \\+ Oracle Agents | Cross-references live regulatory news with calculated downside financial scenarios. |\n| Deal Structure & Returns | State Observer Agent (Python) | Deterministic extraction of IRR, MOIC, and debt tranches from the LBO waterfall.22 |\n\n## **Parallel Architecture: The Shield-Wall Autonomous InfoSec Responder**\n\nEnterprise software organizations face a paralyzing administrative bottleneck during the procurement phase: the vendor security questionnaire, which frequently encompasses hundreds of highly technical infrastructure and policy inquiries. While automated compliance platforms currently exist in the market, this sector was recently shaken by severe cross-tenant data exposure scandals. Specific incidents involved product code changes that inadvertently exposed sensitive customer data\u2014such as employee roles and multi-factor authentication configurations\u2014across different tenant boundaries.25 For a highly technical founding team with backgrounds in proprietary trading and zero-knowledge cryptography, exposing proprietary infrastructure telemetry to vulnerable third-party compliance platforms presents an unacceptable systemic risk.7 Nevertheless, manually answering these extensive questionnaires severely elongates enterprise sales cycles, directly impacting revenue velocity.7  \nThe architectural solution is an air-gapped, fully internal, multi-agent system designated as the Shield-Wall. Deployed directly and exclusively within the organization's own Virtual Private Cloud, this system autonomously answers complex information security questionnaires by querying live infrastructure logs, code repositories, and internal security policies. This entirely bypasses the need for vulnerable third-party compliance software, ensuring that telemetry never leaves the organization's controlled perimeter.26  ",
        "line_number": 59,
        "context_start_line": 54
      }
    ],
    "Kaide-LABS/tracelight-safe-harbor/PHASE_1_SPEC.md": [
      {
        "path": "Kaide-LABS/tracelight-safe-harbor/PHASE_1_SPEC.md",
        "line": "- If Gemini returns malformed JSON: retry up to 2 times.",
        "context": "   ```\n4. Parse `response.text` \u2192 strip any markdown fences \u2192 `json.loads()` \u2192 validate with `TemplateSchema.model_validate()`.\n5. Populate the `cell_references` and `periods` fields on each `ColumnSchema` from the original `parsed_template` data (Gemini classifies the types; the cell refs come from the parser).\n\n**Fallback:**\n- If Gemini returns malformed JSON: retry up to 2 times.\n- If still failing after 2 retries: fall back to GPT-4o via OpenAI with the same prompt.\n  ```python\n  client = OpenAI(api_key=settings.openai_api_key)\n  completion = client.chat.completions.parse(\n      model=settings.gpt4o_model,",
        "line_number": 453,
        "context_start_line": 448
      },
      {
        "path": "Kaide-LABS/tracelight-safe-harbor/PHASE_1_SPEC.md",
        "line": "Returns a new `SyntheticPayload` with the adjusted cell values. The original payload is not mutated.",
        "context": "Ending Debt = Beginning Debt + Drawdowns - Repayments\n```\n- On failure: adjust Repayments to force the identity.\n\n#### Method: `_apply_plug_adjustments(payload, adjustments) -> SyntheticPayload`\nReturns a new `SyntheticPayload` with the adjusted cell values. The original payload is not mutated.\n\n#### Method: `_build_retry_instructions(results) -> str | None`\nIf any rule has `needs_regeneration` items, builds a human-readable string describing what to fix. Returns `None` if no retry needed.\n\n---",
        "line_number": 619,
        "context_start_line": 614
      },
      {
        "path": "Kaide-LABS/tracelight-safe-harbor/PHASE_1_SPEC.md",
        "line": "If any rule has `needs_regeneration` items, builds a human-readable string describing what to fix. Returns `None` if no retry needed.",
        "context": "\n#### Method: `_apply_plug_adjustments(payload, adjustments) -> SyntheticPayload`\nReturns a new `SyntheticPayload` with the adjusted cell values. The original payload is not mutated.\n\n#### Method: `_build_retry_instructions(results) -> str | None`\nIf any rule has `needs_regeneration` items, builds a human-readable string describing what to fix. Returns `None` if no retry needed.\n\n---\n\n## 9. ORCHESTRATOR \u2014 `backend/orchestrator.py`\n",
        "line_number": 622,
        "context_start_line": 617
      },
      {
        "path": "Kaide-LABS/tracelight-safe-harbor/PHASE_1_SPEC.md",
        "line": "  - Backend returns `TemplateNotEmptyError` \u2192 \"This file contains data in input cells. Please upload an empty template.\"",
        "context": "- Three sample template buttons below the drop zone: \"LBO Template\", \"DCF Template\", \"3-Statement Template\" \u2014 clicking these sends a pre-built template from `/templates/`.\n- On drop/select: `POST /api/upload` with the file as `FormData`. On success, call `onJobCreated(response.job_id)`.\n- Error states:\n  - File too large \u2192 red text.\n  - Wrong format \u2192 red text.\n  - Backend returns `TemplateNotEmptyError` \u2192 \"This file contains data in input cells. Please upload an empty template.\"\n\n### 11.3 `src/components/SchemaTerminal.jsx`\n\n**Props:** `events: WSEvent[]` (filtered to `phase === \"parse\" || phase === \"schema_extract\"`)\n",
        "line_number": 821,
        "context_start_line": 816
      },
      {
        "path": "Kaide-LABS/tracelight-safe-harbor/PHASE_1_SPEC.md",
        "line": "Sheets: Income Statement, Balance Sheet, Cash Flow Statement, Debt Schedule, Returns Analysis.",
        "context": "## 12. SAMPLE TEMPLATES\n\nThree pre-built `.xlsx` files must be created in the `templates/` directory. These are for prospects who don't have their own template handy.\n\n### `lbo_template.xlsx`\nSheets: Income Statement, Balance Sheet, Cash Flow Statement, Debt Schedule, Returns Analysis.\n- Income Statement columns: Revenue, COGS, Gross Profit (formula), SG&A, EBITDA (formula), D&A, EBIT (formula), Interest Expense (formula from Debt Schedule), EBT (formula), Tax, Net Income (formula). Periods: FY2020-FY2030.\n- Balance Sheet: Cash, Accounts Receivable, Inventory, Other Current Assets, Total Current Assets (formula), PP&E Net, Goodwill, Other Non-Current Assets, Total Assets (formula), Accounts Payable, Accrued Expenses, Current Portion of Debt, Total Current Liabilities (formula), Senior Debt, Mezzanine Debt, Total Liabilities (formula), Common Equity, Retained Earnings, Total Equity (formula), Total Liabilities & Equity (formula). Periods: FY2020-FY2030.\n- Cash Flow: Net Income, D&A, Changes in Working Capital, Operating CF (formula), CapEx, Investing CF (formula), Debt Drawdowns, Debt Repayments, Dividends, Financing CF (formula), Net Change in Cash (formula), Beginning Cash, Ending Cash (formula). Periods: FY2020-FY2030.\n- Debt Schedule: For each tranche (Senior, Mezzanine): Beginning Balance, Drawdowns, Repayments, Ending Balance (formula), Interest Rate, Interest Expense (formula). Periods: FY2020-FY2030.\n- Returns: Entry EV, Exit EV (formula from Exit Multiple x EBITDA), Net Debt at Exit, Exit Equity (formula), Equity Invested, MOIC (formula), IRR (formula). Single-period summary.",
        "line_number": 938,
        "context_start_line": 933
      },
      {
        "path": "Kaide-LABS/tracelight-safe-harbor/PHASE_1_SPEC.md",
        "line": "- Returns: Entry EV, Exit EV (formula from Exit Multiple x EBITDA), Net Debt at Exit, Exit Equity (formula), Equity Invested, MOIC (formula), IRR (formula). Single-period summary.",
        "context": "Sheets: Income Statement, Balance Sheet, Cash Flow Statement, Debt Schedule, Returns Analysis.\n- Income Statement columns: Revenue, COGS, Gross Profit (formula), SG&A, EBITDA (formula), D&A, EBIT (formula), Interest Expense (formula from Debt Schedule), EBT (formula), Tax, Net Income (formula). Periods: FY2020-FY2030.\n- Balance Sheet: Cash, Accounts Receivable, Inventory, Other Current Assets, Total Current Assets (formula), PP&E Net, Goodwill, Other Non-Current Assets, Total Assets (formula), Accounts Payable, Accrued Expenses, Current Portion of Debt, Total Current Liabilities (formula), Senior Debt, Mezzanine Debt, Total Liabilities (formula), Common Equity, Retained Earnings, Total Equity (formula), Total Liabilities & Equity (formula). Periods: FY2020-FY2030.\n- Cash Flow: Net Income, D&A, Changes in Working Capital, Operating CF (formula), CapEx, Investing CF (formula), Debt Drawdowns, Debt Repayments, Dividends, Financing CF (formula), Net Change in Cash (formula), Beginning Cash, Ending Cash (formula). Periods: FY2020-FY2030.\n- Debt Schedule: For each tranche (Senior, Mezzanine): Beginning Balance, Drawdowns, Repayments, Ending Balance (formula), Interest Rate, Interest Expense (formula). Periods: FY2020-FY2030.\n- Returns: Entry EV, Exit EV (formula from Exit Multiple x EBITDA), Net Debt at Exit, Exit Equity (formula), Equity Invested, MOIC (formula), IRR (formula). Single-period summary.\n\nAll input cells empty. All formula cells contain correct Excel formulas with inter-sheet references.\n\n### `dcf_template.xlsx`\nSheets: Revenue Build, Income Statement, Free Cash Flow, DCF Valuation.",
        "line_number": 943,
        "context_start_line": 938
      },
      {
        "path": "Kaide-LABS/tracelight-safe-harbor/PHASE_1_SPEC.md",
        "line": "- No debt schedule or returns analysis.",
        "context": "- DCF sheet: WACC, Terminal Growth Rate, Terminal Value (formula), PV of FCFs (formula), Enterprise Value (formula).\n\n### `three_statement_template.xlsx`\nSheets: Income Statement, Balance Sheet, Cash Flow Statement.\n- Standard 3-statement model with full inter-statement linkages.\n- No debt schedule or returns analysis.\n\n---\n\n## 13. TESTS \u2014 Required Coverage\n",
        "line_number": 955,
        "context_start_line": 950
      },
      {
        "path": "Kaide-LABS/tracelight-safe-harbor/PHASE_1_SPEC.md",
        "line": "- Test: margin violation (negative gross margin) returns `needs_regeneration` for COGS.",
        "context": "\n### `tests/test_validator.py`\n- Test: balanced BS passes `_rule_balance_sheet_identity`.\n- Test: unbalanced BS triggers plug adjustment to Cash, result status is `PASSED_WITH_PLUGS`.\n- Test: broken CF reconciliation triggers adjustment.\n- Test: margin violation (negative gross margin) returns `needs_regeneration` for COGS.\n- Test: depreciation exceeding CapEx + PP&E triggers cap.\n- Test: debt schedule mismatch triggers repayment adjustment.\n\n### `tests/test_schema_extractor.py`\n- Test: mock Gemini response \u2192 verify `TemplateSchema` output parses correctly.",
        "line_number": 970,
        "context_start_line": 965
      }
    ],
    "Kaide-LABS/tracelight-safe-harbor/PRD.md": [
      {
        "path": "Kaide-LABS/tracelight-safe-harbor/PRD.md",
        "line": "  - Implement retry signal (returns which line items need regeneration)",
        "context": "STEP 3 \u2014 Deterministic Validation Agent (Hour 6-12)\n- Build validator.py as a pure Python class:\n  - Method: validate(payload: SyntheticPayload) \u2192 ValidationResult\n  - Implement all 6 hardcoded rules (see architecture above)\n  - Implement plug-account adjustment logic\n  - Implement retry signal (returns which line items need regeneration)\n- TEST: Feed it deliberately broken data (BS doesn't balance,\n  negative margins, depreciation > CapEx). Verify it catches every\n  violation and produces correct plug adjustments.\n- This is the trust anchor. It must be bulletproof before proceeding.\n",
        "line_number": 593,
        "context_start_line": 588
      },
      {
        "path": "Kaide-LABS/tracelight-safe-harbor/PRD.md",
        "line": "- Fallback: If Gemini fails or returns malformed JSON, retry 2x.",
        "context": "    following Excel template structure, classify each column by its\n    financial data type, identify temporal ranges, detect inter-sheet\n    dependencies, and classify the model type. Output strict JSON\n    conforming to the TemplateSchema.\"\n  - Parse response into TemplateSchema Pydantic model\n- Fallback: If Gemini fails or returns malformed JSON, retry 2x.\n  If still failing, fall back to GPT-4o for schema extraction.\n- TEST: Run against LBO, DCF, and 3-Statement templates. Verify\n  correct classification of every column.\n\nSTEP 5 \u2014 Synthetic Generation Agent (Hour 18-26)",
        "line_number": 609,
        "context_start_line": 604
      },
      {
        "path": "Kaide-LABS/tracelight-safe-harbor/PRD.md",
        "line": "  - POST /api/upload \u2014 receives .xlsx, returns job_id",
        "context": "  - Executes pipeline: Parse \u2192 Schema Extract \u2192 Generate \u2192 Validate \u2192 Write\n  - WebSocket connection to frontend for real-time progress updates\n  - Sends structured events: {\"phase\": \"schema\", \"detail\": \"Mapping Income Statement...\"}\n  - Error handling: timeout after 60 seconds, graceful degradation\n- Build main.py:\n  - POST /api/upload \u2014 receives .xlsx, returns job_id\n  - WS /ws/{job_id} \u2014 streams progress events to frontend\n  - GET /api/download/{job_id} \u2014 returns populated .xlsx\n\nSTEP 7 \u2014 Frontend (Hour 32-48)\n- Build React components in order:",
        "line_number": 635,
        "context_start_line": 630
      },
      {
        "path": "Kaide-LABS/tracelight-safe-harbor/PRD.md",
        "line": "  - GET /api/download/{job_id} \u2014 returns populated .xlsx",
        "context": "  - Sends structured events: {\"phase\": \"schema\", \"detail\": \"Mapping Income Statement...\"}\n  - Error handling: timeout after 60 seconds, graceful degradation\n- Build main.py:\n  - POST /api/upload \u2014 receives .xlsx, returns job_id\n  - WS /ws/{job_id} \u2014 streams progress events to frontend\n  - GET /api/download/{job_id} \u2014 returns populated .xlsx\n\nSTEP 7 \u2014 Frontend (Hour 32-48)\n- Build React components in order:\n  1. UploadZone.jsx \u2014 drag-and-drop with sample template buttons\n  2. SchemaTerminal.jsx \u2014 terminal-style feed consuming WS events",
        "line_number": 637,
        "context_start_line": 632
      }
    ]
  },
  "pattern": "RETURNS|SUMMARY DASHBOARD|has_ra|Section 8",
  "path_filter": "/",
  "total_matches": 15,
  "files_searched": 3,
  "files_with_matches": 3,
  "truncated": false,
  "options": {
    "case_sensitive": false,
    "lines_before": 5,
    "lines_after": 5,
    "output_mode": "content",
    "whole_word": false,
    "fixed_string": false,
    "highlight": false,
    "include_line_numbers": true,
    "group_by_file": true
  }
}

6. [Source 6] code_grep({"repository_id": "Kaide-LABS/tracelight-safe-harbor", "pattern": "has_ra|RETURNS ANALYSIS|Section 8|SUMMARY|_add_validation", "context_lines": 3, "max_total_matches": 30}): {
  "success": true,
  "matches": {
    "Kaide-LABS/tracelight-safe-harbor/CONTEXT.md": [
      {
        "path": "Kaide-LABS/tracelight-safe-harbor/CONTEXT.md",
        "line": "## **Executive Summary**",
        "context": "# **Strategic Architectural Blueprint for Tracelight: Multi-Agent Sidecar Orchestration and Enterprise Acceleration**\n\n## **Executive Summary**\n\nThe deployment of artificial intelligence within the high-stakes domain of complex financial modeling necessitates a fundamental paradigm shift away from stochastic generation and towards deterministic orchestration. Tracelight has successfully pioneered this transition by treating spreadsheet logic as a Directed Acyclic Graph (DAG), enabling large language models to reason over topological dependencies rather than flat text arrays.1 Backed by a recent $3.6 million seed round led by Chalfen Ventures, and already deployed within elite management consultancies and private equity funds managing billions in assets, Tracelight is strategically positioned to capture the enterprise financial modeling market.4  \nTo accelerate enterprise adoption without compromising the integrity of Tracelight\u2019s core proprietary engine, this analysis outlines a strategic mandate for adjacent, multi-agent artificial intelligence workflows. Through a rigorous psychological and operational deconstruction of the founding team, three distinct architectural \"sidecar\" blueprints have been engineered. These workflows\u2014spanning pre-core synthetic data ingestion, post-core artifact synthesis, and parallel security compliance\u2014adhere to the highest standards of technical pragmatism, deterministic fallback logic, and visual proof. By integrating these systems, the enterprise sales cycle can be significantly compressed, directly neutralizing Tracelight's current operational bottlenecks regarding information security approvals and downstream artifact generation.",
        "line_number": 3,
        "context_start_line": 1
      },
      {
        "path": "Kaide-LABS/tracelight-safe-harbor/CONTEXT.md",
        "line": "Operating in parallel is the Oracle Research Agent, leveraging Gemini 1.5 Pro via Google Vertex AI. This model is specifically selected for its massive context window and robust real-time grounding capabilities. It extracts the target company name and industry sector from the model and executes a live web search for recent macroeconomic headwinds, competitor valuation multiples, and emerging regulatory risks. This ensures that the qualitative sections of the memo are highly relevant and grounded in current reality. The Synthesis and Authoring Agent, powered by Claude 3.5 Sonnet, receives both the deterministic financial outputs and the grounded market research. It drafts the distinct sections of the Investment Committee Memo\u2014including the Executive Summary, Market Analysis, Financial Projections, and Risks and Mitigants\u2014meticulously matching the strict, narrative-driven, structured tone characteristic of top-tier strategy consultancies.21 Finally, a Formatting Engine utilizing LaTeX and Pandoc bypasses the formatting errors commonly associated with language models by compiling the structured JSON output directly into a perfectly styled, firm-branded PDF or DOCX file.  ",
        "context": "While the platform excels at making analysts highly efficient at building complex logic inside the spreadsheet 5, the quantitative model is rarely the final deliverable in institutional finance. In private equity and asset management, the model serves as the foundation for the Investment Committee Memo. This narrative document, typically fifteen to thirty pages in length, details the investment thesis, comprehensive market sizing, financial returns, and associated risks.21 Under current operational paradigms, analysts must manually transcribe final calculated arrays from the spreadsheet into Microsoft Word. This manual transcription is highly prone to human error, formatting fatigue, and version control issues, causing significant downstream friction.21  \nThe solution is a post-core orchestration engine designed to monitor the finalized state of the mathematical graph. Upon user command, this engine extracts the deterministic outputs and autonomously authors a perfectly formatted, McKinsey-grade Investment Committee Memo, dynamically grounded by real-time external market intelligence. This architecture functions purely downstream, leveraging the completed quantitative work to automate the qualitative presentation.  \nThe technical architecture for this synthesizer utilizes a Next.js user interface embedded seamlessly as a sidebar or modal within the existing Excel Add-in. The backend operates on a Python FastAPI orchestration layer that coordinates a highly specialized multi-agent engine. The first component is the State Observer Agent, a Python-based monitor that interfaces with the finalized Directed Acyclic Graph. When the user flags the financial model as complete, this agent extracts the key output nodes\u2014such as the calculated Exit Internal Rate of Return, the Multiple on Invested Capital, Enterprise Value, and base versus downside case EBITDA figures\u2014without disturbing the internal dependency logic or altering the workbook.  \nOperating in parallel is the Oracle Research Agent, leveraging Gemini 1.5 Pro via Google Vertex AI. This model is specifically selected for its massive context window and robust real-time grounding capabilities. It extracts the target company name and industry sector from the model and executes a live web search for recent macroeconomic headwinds, competitor valuation multiples, and emerging regulatory risks. This ensures that the qualitative sections of the memo are highly relevant and grounded in current reality. The Synthesis and Authoring Agent, powered by Claude 3.5 Sonnet, receives both the deterministic financial outputs and the grounded market research. It drafts the distinct sections of the Investment Committee Memo\u2014including the Executive Summary, Market Analysis, Financial Projections, and Risks and Mitigants\u2014meticulously matching the strict, narrative-driven, structured tone characteristic of top-tier strategy consultancies.21 Finally, a Formatting Engine utilizing LaTeX and Pandoc bypasses the formatting errors commonly associated with language models by compiling the structured JSON output directly into a perfectly styled, firm-branded PDF or DOCX file.  \nThe execution flow is initiated when an analyst completes an analysis, such as an annual recurring revenue snowball or a discounted cash flow valuation, and triggers the generation sequence.24 Parallel execution commences immediately: the Observer Agent extracts the hard financial metrics, while the Research Agent queries live macroeconomic data. Claude 3.5 Sonnet then synthesizes this data into a narrative draft, utilizing strict JSON schemas to ensure no required section of the institutional memo is omitted.22 To guarantee system resilience and immunity against hallucination, a deterministic string-matching script compares every financial number generated in the text narrative against the raw payload extracted directly from the mathematical graph. If a hallucinated discrepancy is detected\u2014for instance, if the generated text states a return of 25.4 percent while the deterministic graph calculated 24.5 percent\u2014the system forcefully overwrites the text with the exact source-of-truth value. A beautifully formatted document is then generated and presented for download.  \nThis workflow provides a profound user experience enhancement. A synthesis dashboard slides into view, presenting a split-screen interface. On the left, the user views the finalized Excel model; on the right, the Investment Committee Memo is drafted in real-time. Dynamic badges display the system's underlying processes, indicating that market risks are being grounded via live search, followed by a notification that financial metrics are being verified against the model state. The analyst watches hours of narrative drafting compress into under a minute. This aligns perfectly with the product philosophy of turning spreadsheets into beautiful, shareable artifacts, eliminating the friction between the quantitative model and the qualitative presentation without requiring complex prompt engineering from the user.7 Furthermore, this expands the total addressable market of the platform. It evolves the offering from a faster modeling tool into a comprehensive automation engine for the entire due diligence and deal execution lifecycle, delivering the macroeconomic impact demanded by enterprise leadership.  \nThe following table details the standard sections of a Private Equity Investment Committee Memo and the corresponding agent responsible for its automated synthesis.",
        "line_number": 48,
        "context_start_line": 45
      },
      {
        "path": "Kaide-LABS/tracelight-safe-harbor/CONTEXT.md",
        "line": "| Executive Summary | Synthesis Agent (Claude 3.5) | Aggregates outputs from all other agents into a concise narrative thesis.22 |",
        "context": "\n| IC Memo Section | Responsible Agent | Data Source & Grounding Mechanism |\n| :---- | :---- | :---- |\n| Executive Summary | Synthesis Agent (Claude 3.5) | Aggregates outputs from all other agents into a concise narrative thesis.22 |\n| Market Analysis | Oracle Research Agent (Gemini) | Live web search for TAM, sector headwinds, and competitor multiples. |\n| Financial Projections | State Observer Agent (Python) | Direct, deterministic extraction from the finalized Tracelight DAG nodes. |\n| Risks & Mitigants | Synthesis \\+ Oracle Agents | Cross-references live regulatory news with calculated downside financial scenarios. |",
        "line_number": 55,
        "context_start_line": 52
      }
    ],
    "Kaide-LABS/tracelight-safe-harbor/PHASE_1_SPEC.md": [
      {
        "path": "Kaide-LABS/tracelight-safe-harbor/PHASE_1_SPEC.md",
        "line": "   - Send final `WSEvent` with `event_type=\"complete\"` including full validation summary and audit log in `data`.",
        "context": "\n6. **Complete**\n   - `self._update_status(job_id, \"complete\")`\n   - Send final `WSEvent` with `event_type=\"complete\"` including full validation summary and audit log in `data`.\n\n**Timeout:** Wrap the entire pipeline in `asyncio.wait_for(..., timeout=settings.generation_timeout_s)`. On timeout, set status to \"error\" and send error event.\n",
        "line_number": 703,
        "context_start_line": 700
      },
      {
        "path": "Kaide-LABS/tracelight-safe-harbor/PHASE_1_SPEC.md",
        "line": "Sheets: Income Statement, Balance Sheet, Cash Flow Statement, Debt Schedule, Returns Analysis.",
        "context": "Three pre-built `.xlsx` files must be created in the `templates/` directory. These are for prospects who don't have their own template handy.\n\n### `lbo_template.xlsx`\nSheets: Income Statement, Balance Sheet, Cash Flow Statement, Debt Schedule, Returns Analysis.\n- Income Statement columns: Revenue, COGS, Gross Profit (formula), SG&A, EBITDA (formula), D&A, EBIT (formula), Interest Expense (formula from Debt Schedule), EBT (formula), Tax, Net Income (formula). Periods: FY2020-FY2030.\n- Balance Sheet: Cash, Accounts Receivable, Inventory, Other Current Assets, Total Current Assets (formula), PP&E Net, Goodwill, Other Non-Current Assets, Total Assets (formula), Accounts Payable, Accrued Expenses, Current Portion of Debt, Total Current Liabilities (formula), Senior Debt, Mezzanine Debt, Total Liabilities (formula), Common Equity, Retained Earnings, Total Equity (formula), Total Liabilities & Equity (formula). Periods: FY2020-FY2030.\n- Cash Flow: Net Income, D&A, Changes in Working Capital, Operating CF (formula), CapEx, Investing CF (formula), Debt Drawdowns, Debt Repayments, Dividends, Financing CF (formula), Net Change in Cash (formula), Beginning Cash, Ending Cash (formula). Periods: FY2020-FY2030.",
        "line_number": 938,
        "context_start_line": 935
      },
      {
        "path": "Kaide-LABS/tracelight-safe-harbor/PHASE_1_SPEC.md",
        "line": "- Returns: Entry EV, Exit EV (formula from Exit Multiple x EBITDA), Net Debt at Exit, Exit Equity (formula), Equity Invested, MOIC (formula), IRR (formula). Single-period summary.",
        "context": "- Balance Sheet: Cash, Accounts Receivable, Inventory, Other Current Assets, Total Current Assets (formula), PP&E Net, Goodwill, Other Non-Current Assets, Total Assets (formula), Accounts Payable, Accrued Expenses, Current Portion of Debt, Total Current Liabilities (formula), Senior Debt, Mezzanine Debt, Total Liabilities (formula), Common Equity, Retained Earnings, Total Equity (formula), Total Liabilities & Equity (formula). Periods: FY2020-FY2030.\n- Cash Flow: Net Income, D&A, Changes in Working Capital, Operating CF (formula), CapEx, Investing CF (formula), Debt Drawdowns, Debt Repayments, Dividends, Financing CF (formula), Net Change in Cash (formula), Beginning Cash, Ending Cash (formula). Periods: FY2020-FY2030.\n- Debt Schedule: For each tranche (Senior, Mezzanine): Beginning Balance, Drawdowns, Repayments, Ending Balance (formula), Interest Rate, Interest Expense (formula). Periods: FY2020-FY2030.\n- Returns: Entry EV, Exit EV (formula from Exit Multiple x EBITDA), Net Debt at Exit, Exit Equity (formula), Equity Invested, MOIC (formula), IRR (formula). Single-period summary.\n\nAll input cells empty. All formula cells contain correct Excel formulas with inter-sheet references.\n",
        "line_number": 943,
        "context_start_line": 940
      },
      {
        "path": "Kaide-LABS/tracelight-safe-harbor/PHASE_1_SPEC.md",
        "line": "- No debt schedule or returns analysis.",
        "context": "### `three_statement_template.xlsx`\nSheets: Income Statement, Balance Sheet, Cash Flow Statement.\n- Standard 3-statement model with full inter-statement linkages.\n- No debt schedule or returns analysis.\n\n---\n",
        "line_number": 955,
        "context_start_line": 952
      }
    ],
    "Kaide-LABS/tracelight-safe-harbor/PRD.md": [
      {
        "path": "Kaide-LABS/tracelight-safe-harbor/PRD.md",
        "line": "### Agent Routing Summary Table",
        "context": "\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518\n```\n\n### Agent Routing Summary Table\n\n| Agent | Model | Provider | Why This Model |\n|-------|-------|----------|----------------|",
        "line_number": 397,
        "context_start_line": 394
      },
      {
        "path": "Kaide-LABS/tracelight-safe-harbor/PRD.md",
        "line": "  4. VerdictBadge.jsx \u2014 full-screen validation summary",
        "context": "  1. UploadZone.jsx \u2014 drag-and-drop with sample template buttons\n  2. SchemaTerminal.jsx \u2014 terminal-style feed consuming WS events\n  3. DataWaterfall.jsx \u2014 grid visualization with cell-by-cell animation\n  4. VerdictBadge.jsx \u2014 full-screen validation summary\n  5. AuditTrail.jsx \u2014 expandable JSON inspector for the CTO\n- useWebSocket.js hook manages the WS connection and event routing\n- Tailwind config matches Tracelight's dark UI aesthetic",
        "line_number": 644,
        "context_start_line": 641
      }
    ]
  },
  "pattern": "has_ra|RETURNS ANALYSIS|Section 8|SUMMARY|_add_validation",
  "path_filter": "/",
  "total_matches": 9,
  "files_searched": 3,
  "files_with_matches": 3,
  "truncated": false,
  "options": {
    "case_sensitive": false,
    "lines_before": 3,
    "lines_after": 3,
    "output_mode": "content",
    "whole_word": false,
    "fixed_string": false,
    "highlight": false,
    "include_line_numbers": true,
    "group_by_file": true
  }
}

7. [Source 7] get_github_tree({"project_id": "e83393b7-1ee7-4b81-b0a0-fffc1b7afa1b"}): {
  "tree": "\ud83d\udcc4 .env.example\n\ud83d\udcc1 .github\n  \ud83d\udcc1 workflows\n    \ud83d\udcc4 ci.yml\n    \ud83d\udcc4 deploy.yml\n\ud83d\udcc4 .gitignore\n\ud83d\udcc4 3_Statement_Model.xlsx\n\ud83d\udcc4 ADJACENT_IDEAS.md\n\ud83d\udcc4 Balancing Financial Model Circular References copy.md\n\ud83d\udcc4 CONTEXT.md\n\ud83d\udcc4 DCF_Model.xlsx\n\ud83d\udcc4 FOUNDERS_BRIEF.md\n\ud83d\udcc4 LBO_Model.xlsx\n\ud83d\udcc4 PHASE_1_SPEC.md\n\ud83d\udcc4 PHASE_2_SPEC.md\n\ud83d\udcc4 PHASE_3_SPEC.md\n\ud83d\udcc4 PHASE_4_SPEC.md\n\ud83d\udcc4 PHASE_5_SPEC.md\n\ud83d\udcc4 PRD.md\n\ud83d\udcc4 Tracelight_logo.png\n\ud83d\udcc4 Vendor_Security_Questionnaire.xlsx\n\ud83d\udcc1 demo\n  \ud83d\udcc4 cost_comparison.md\n  \ud83d\udcc4 deck_outline.md\n  \ud83d\udcc4 pitch_notes.md\n  \ud83d\udcc4 run_demo.sh\n  \ud83d\udcc4 scenarios.md\n  \ud83d\udcc4 technical_appendix.md\n\ud83d\udcc4 docker-compose.yml\n\ud83d\udcc1 infra\n  \ud83d\udcc4 cloudbuild-safe-harbor.yaml\n  \ud83d\udcc4 cloudbuild-shield-wall.yaml\n  \ud83d\udcc1 env\n    \ud83d\udcc4 production.env\n    \ud83d\udcc4 staging.env\n\ud83d\udcc1 launcher\n  \ud83d\udcc4 Dockerfile\n  \ud83d\udcc4 index.html\n  \ud83d\udcc4 package.json\n  \ud83d\udcc4 postcss.config.js\n  \ud83d\udcc1 public\n    \ud83d\udcc4 Tracelight_logo.png\n  \ud83d\udcc1 src\n    \ud83d\udcc4 App.jsx\n    \ud83d\udcc4 config.js\n    \ud83d\udcc4 index.css\n    \ud83d\udcc4 main.jsx\n  \ud83d\udcc4 tailwind.config.js\n  \ud83d\udcc4 vercel.json\n  \ud83d\udcc4 vite.config.js\n\ud83d\udcc1 safe-harbor\n  \ud83d\udcc4 Dockerfile\n  \ud83d\udcc1 backend\n    \ud83d\udcc4 __init__.py\n    \ud83d\udcc1 agents\n      \ud83d\udcc4 __init__.py\n      \ud83d\udcc4 post_processor.py\n      \ud83d\udcc4 schema_extractor.py\n      \ud83d\udcc4 synthetic_gen.py\n      \ud83d\udcc4 validator.py\n    \ud83d\udcc4 config.py\n    \ud83d\udcc1 excel_io\n      \ud83d\udcc4 __init__.py\n      \ud83d\udcc4 parser.py\n      \ud83d\udcc4 writer.py\n    \ud83d\udcc4 health.py\n    \ud83d\udcc4 main.py\n    \ud83d\udcc1 middleware\n      \ud83d\udcc4 __init__.py\n      \ud83d\udcc4 cost_tracker.py\n      \ud83d\udcc4 logging_middleware.py\n    \ud83d\udcc1 models\n      \ud83d\udcc4 __init__.py\n      \ud83d\udcc4 schemas.py\n    \ud83d\udcc4 orchestrator.py\n  \ud83d\udcc1 frontend\n    \ud83d\udcc4 Dockerfile\n    \ud83d\udcc4 index.html\n    \ud83d\udcc4 package.json\n    \ud83d\udcc4 postcss.config.js\n    \ud83d\udcc1 public\n      \ud83d\udcc4 Tracelight_logo.png\n    \ud83d\udcc1 src\n      \ud83d\udcc4 App.jsx\n      \ud83d\udcc1 components\n        \ud83d\udcc4 AuditTrail.jsx\n        \ud83d\udcc4 DataWaterfall.jsx\n        \ud83d\udcc4 ErrorBanner.jsx\n        \ud83d\udcc4 SchemaTerminal.jsx\n        \ud83d\udcc4 SpreadsheetViewer.jsx\n        \ud83d\udcc4 TemplatePreview.jsx\n        \ud83d\udcc4 UploadZone.jsx\n        \ud83d\udcc4 VerdictBadge.jsx\n      \ud83d\udcc4 config.js\n      \ud83d\udcc1 hooks\n        \ud83d\udcc4 useWebSocket.js\n      \ud83d\udcc4 index.css\n      \ud83d\udcc4 main.jsx\n    \ud83d\udcc4 tailwind.config.js\n    \ud83d\udcc4 vercel.json\n    \ud83d\udcc4 vite.config.js\n  \ud83d\udcc4 requirements.txt\n  \ud83d\udcc1 scripts\n    \ud83d\udcc4 generate_templates.py\n    \ud83d\udcc4 verify_templates.py\n  \ud83d\udcc1 templates\n    \ud83d\udcc4 3_Statement_Model.xlsx\n    \ud83d\udcc4 DCF_Model.xlsx\n    \ud83d\udcc4 LBO_Model.xlsx\n  \ud83d\udcc1 tests\n    \ud83d\udcc4 conftest.py\n    \ud83d\udcc4 test_cost_tracker.py\n    \ud83d\udcc4 test_health.py\n    \ud83d\udcc4 test_orchestrator_e2e.py\n    \ud83d\udcc4 test_parser.py\n    \ud83d\udcc4 test_schema_extractor.py\n    \ud83d\udcc4 test_synthetic_gen.py\n    \ud83d\udcc4 test_validator.py\n\ud83d\udcc1 shield-wall\n  \ud83d\udcc4 Dockerfile\n  \ud83d\udcc1 backend\n    \ud83d\udcc4 __init__.py\n    \ud83d\udcc1 agents\n      \ud83d\udcc4 __init__.py\n      \ud83d\udcc4 drift_detector.py\n      \ud83d\udcc4 policy_agent.py\n      \ud83d\udcc4 questionnaire_parser.py\n      \ud83d\udcc4 synthesis_agent.py\n      \ud83d\udcc4 telemetry_agent.py\n    \ud83d\udcc4 config.py\n    \ud83d\udcc4 health.py\n    \ud83d\udcc4 main.py\n    \ud83d\udcc1 middleware\n      \ud83d\udcc4 __init__.py\n      \ud83d\udcc4 cost_tracker.py\n      \ud83d\udcc4 logging_middleware.py\n    \ud83d\udcc1 models\n      \ud83d\udcc4 __init__.py\n      \ud83d\udcc4 schemas.py\n    \ud83d\udcc4 orchestrator.py\n    \ud83d\udcc1 parsers\n      \ud83d\udcc4 __init__.py\n      \ud83d\udcc4 excel_parser.py\n      \ud83d\udcc4 pdf_parser.py\n      \ud83d\udcc4 text_parser.py\n    \ud83d\udcc1 policy_store\n      \ud83d\udcc4 __init__.py\n      \ud83d\udcc4 indexer.py\n      \ud83d\udcc4 retriever.py\n    \ud83d\udcc1 telemetry\n      \ud83d\udcc4 __init__.py\n      \ud83d\udcc4 aws_adapter.py\n      \ud83d\udcc4 base.py\n      \ud83d\udcc4 mock_adapter.py\n  \ud83d\udcc1 data\n    \ud83d\udcc1 mock_infra\n      \ud83d\udcc4 cloudtrail_events.json\n      \ud83d\udcc4 iam_policies.json\n      \ud83d\udcc4 kms_keys.json\n      \ud83d\udcc4 rds_instances.json\n      \ud83d\udcc4 security_groups.json\n    \ud83d\udcc1 policies\n      \ud83d\udcc4 access_control.md\n      \ud83d\udcc4 business_continuity.md\n      \ud83d\udcc4 change_management.md\n      \ud83d\udcc4 compliance_policy.md\n      \ud83d\udcc4 data_classification.md\n      \ud83d\udcc4 encryption_policy.md\n      \ud83d\udcc4 incident_response.md\n      \ud83d\udcc4 logging_monitoring.md\n      \ud83d\udcc4 network_security.md\n      \ud83d\udcc4 physical_security.md\n      \ud83d\udcc4 soc2_type2_report.md\n      \ud83d\udcc4 vendor_management.md\n  \ud83d\udcc1 frontend\n    \ud83d\udcc4 Dockerfile\n    \ud83d\udcc4 index.html\n    \ud83d\udcc4 package.json\n    \ud83d\udcc4 postcss.config.js\n    \ud83d\udcc1 public\n      \ud83d\udcc4 Tracelight_logo.png\n    \ud83d\udcc1 src\n      \ud83d\udcc4 App.jsx\n      \ud83d\udcc1 components\n        \ud83d\udcc4 AnswerGrid.jsx\n        \ud83d\udcc4 DriftAlerts.jsx\n        \ud83d\udcc4 ErrorBanner.jsx\n        \ud83d\udcc4 ExportPanel.jsx\n        \ud83d\udcc4 ProcessingTerminal.jsx\n        \ud83d\udcc4 QuestionnaireUpload.jsx\n      \ud83d\udcc4 config.js\n      \ud83d\udcc1 hooks\n        \ud83d\udcc4 useWebSocket.js\n      \ud83d\udcc4 index.css\n      \ud83d\udcc4 main.jsx\n    \ud83d\udcc4 tailwind.config.js\n    \ud83d\udcc4 vercel.json\n    \ud83d\udcc4 vite.config.js\n  \ud83d\udcc4 requirements.txt\n  \ud83d\udcc1 scripts\n    \ud83d\udcc4 generate_fixtures.py\n  \ud83d\udcc1 tests\n    \ud83d\udcc4 conftest.py\n    \ud83d\udcc1 fixtures\n      \ud83d\udcc4 sample_questionnaire.xlsx\n    \ud83d\udcc4 test_drift_detector.py\n    \ud83d\udcc4 test_health.py\n    \ud83d\udcc4 test_orchestrator_e2e.py\n    \ud83d\udcc4 test_policy_agent.py\n    \ud83d\udcc4 test_questionnaire_parser.py\n    \ud83d\udcc4 test_synthesis_agent.py\n    \ud83d\udcc4 test_telemetry_agent.py",
  "stats": {
    "total_files": 171,
    "total_directories": 41,
    "total_items": 212,
    "file_extensions": {
      ".example": 1,
      ".yml": 3,
      "": 1,
      ".xlsx": 8,
      ".md": 27,
      ".png": 4,
      ".sh": 1,
      ".yaml": 2,
      ".env": 2,
      "no_extension": 5,
      ".html": 3,
      ".json": 11,
      ".js": 14,
      ".jsx": 20,
      ".css": 3,
      ".py": 64,
      ".txt": 2
    },
    "max_depth": 5
  },
  "branch": "main",
  "truncated": false,
  "hint": null
}

8. [Source 8] read_source_content({"source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/scripts/generate_templates.py"}): {
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/scripts/generate_templates.py",
  "content": "import openpyxl\nfrom openpyxl.styles import Font, PatternFill, numbers\nimport os\n\ndef create_lbo():\n    wb = openpyxl.Workbook()\n    \n    # 1. Income Statement\n    ws_is = wb.active\n    ws_is.title = \"Income Statement\"\n    headers = [\"Line Item\", \"FY2020\", \"FY2021\", \"FY2022\", \"FY2023\", \"FY2024\", \"FY2025\"]\n    ws_is.append(headers)\n    for cell in ws_is[1]:\n        cell.font = Font(bold=True)\n        \n    line_items = [\n        \"Revenue\", \"COGS\", \"Gross Profit\", \"SG&A\", \"EBITDA\", \"D&A\", \"EBIT\", \"Interest Expense\", \"EBT\", \"Tax\", \"Net Income\"\n    ]\n    \n    for i, item in enumerate(line_items, 2):\n        ws_is.cell(row=i, column=1, value=item)\n        for col in range(2, 8):\n            cell = ws_is.cell(row=i, column=col)\n            cell.number_format = '#,##0'\n            col_letter = openpyxl.utils.get_column_letter(col)\n            \n            if item == \"Gross Profit\":\n                cell.value = f\"={col_letter}2-{col_letter}3\"\n                cell.fill = PatternFill(\"solid\", fgColor=\"E0E0E0\")\n            elif item == \"EBITDA\":\n                cell.value = f\"={col_letter}4-{col_letter}5\"\n                cell.fill = PatternFill(\"solid\", fgColor=\"E0E0E0\")\n            elif item == \"EBIT\":\n                cell.value = f\"={col_letter}6-{col_letter}7\"\n                cell.fill = PatternFill(\"solid\", fgColor=\"E0E0E0\")\n            elif item == \"Interest Expense\":\n                cell.value = f\"='Debt Schedule'!{col_letter}16\"\n                cell.fill = PatternFill(\"solid\", fgColor=\"E0E0E0\")\n            elif item == \"EBT\":\n                cell.value = f\"={col_letter}8-{col_letter}9\"\n                cell.fill = PatternFill(\"solid\", fgColor=\"E0E0E0\")\n            elif item == \"Net Income\":\n                cell.value = f\"={col_letter}10-{col_letter}11\"\n                cell.fill = PatternFill(\"solid\", fgColor=\"E0E0E0\")\n\n    # 2. Balance Sheet\n    ws_bs = wb.create_sheet(\"Balance Sheet\")\n    ws_bs.append(headers)\n    for cell in ws_bs[1]: cell.font = Font(bold=True)\n    \n    bs_items = [\n        \"Cash\", \"Accounts Receivable\", \"Inventory\", \"Other Current Assets\", \"Total Current Assets\",\n        \"PP&E Net\", \"Goodwill\", \"Other Non-Current Assets\", \"Total Assets\",\n        \"Accounts Payable\", \"Accrued Expenses\", \"Current Portion of Debt\", \"Total Current Liabilities\",\n        \"Senior Debt\", \"Mezzanine Debt\", \"Total Liabilities\",\n        \"Common Equity\", \"Retained Earnings\", \"Total Equity\", \"Total Liabilities & Equity\"\n    ]\n    \n    for i, item in enumerate(bs_items, 2):\n        ws_bs.cell(row=i, column=1, value=item)\n        for col in range(2, 8):\n            cell = ws_bs.cell(row=i, column=col)\n            cell.number_format = '#,##0'\n            col_letter = openpyxl.utils.get_column_letter(col)\n            prev_col = openpyxl.utils.get_column_letter(col-1) if col > 2 else None\n            \n            if item == \"Total Current Assets\":\n                cell.value = f\"=SUM({col_letter}2:{col_letter}5)\"\n                cell.fill = PatternFill(\"solid\", fgColor=\"E0E0E0\")\n            elif item == \"Total Assets\":\n                cell.value = f\"={col_letter}6+{col_letter}7+{col_letter}8+{col_letter}9\"\n                cell.fill = PatternFill(\"solid\", fgColor=\"E0E0E0\")\n            elif item == \"Total Current Liabilities\":\n                cell.value = f\"=SUM({col_letter}11:{col_letter}13)\"\n                cell.fill = PatternFill(\"solid\", fgColor=\"E0E0E0\")\n            elif item == \"Total Liabilities\":\n                cell.value = f\"={col_letter}14+{col_letter}15+{col_letter}16\"\n                cell.fill = PatternFill(\"solid\", fgColor=\"E0E0E0\")\n            elif item == \"Retained Earnings\":\n                if prev_col:\n                    cell.value = f\"={prev_col}19+'Income Statement'!{col_letter}12\"\n                else:\n                    cell.value = f\"='Income Statement'!{col_letter}12\"\n                cell.fill = PatternFill(\"solid\", fgColor=\"E0E0E0\")\n            elif item == \"Total Equity\":\n                cell.value = f\"={col_letter}18+{col_letter}19\"\n                cell.fill = PatternFill(\"solid\", fgColor=\"E0E0E0\")\n            elif item == \"Total Liabilities & Equity\":\n                cell.value = f\"={col_letter}17+{col_letter}20\"\n                cell.fill = PatternFill(\"solid\", fgColor=\"E0E0E0\")\n                \n    # 3. Cash Flow Statement\n    ws_cf = wb.create_sheet(\"Cash Flow\")\n    ws_cf.append(headers)\n    for cell in ws_cf[1]: cell.font = Font(bold=True)\n    \n    cf_items = [\n        \"Net Income\", \"D&A\", \"Changes in Working Capital\", \"Operating CF\",\n        \"CapEx\", \"Investing CF\",\n        \"Debt Drawdowns\", \"Debt Repayments\", \"Dividends\", \"Financing CF\",\n        \"Net Change in Cash\", \"Beginning Cash\", \"Ending Cash\"\n    ]\n    \n    for i, item in enumerate(cf_items, 2):\n        ws_cf.cell(row=i, column=1, value=item)\n        for col in range(2, 8):\n            cell = ws_cf.cell(row=i, column=col)\n            cell.number_format = '#,##0'\n            col_letter = openpyxl.utils.get_column_letter(col)\n            prev_col = openpyxl.utils.get_column_letter(col-1) if col > 2 else None\n            \n            if item == \"Net Income\":\n                cell.value = f\"='Income Statement'!{col_letter}12\"\n                cell.fill = PatternFill(\"solid\", fgColor=\"E0E0E0\")\n            elif item == \"D&A\":\n                cell.value = f\"='Income Statement'!{col_letter}7\"\n                cell.fill = PatternFill(\"solid\", fgColor=\"E0E0E0\")\n            elif item == \"Operating CF\":\n                cell.value = f\"={col_letter}2+{col_letter}3+{col_letter}4\"\n                cell.fill = PatternFill(\"solid\", fgColor=\"E0E0E0\")\n            elif item == \"Investing CF\":\n                cell.value = f\"=-{col_letter}6\"\n                cell.fill = PatternFill(\"solid\", fgColor=\"E0E0E0\")\n            elif item == \"Financing CF\":\n                cell.value = f\"={col_letter}8-{col_letter}9-{col_letter}10\"\n                cell.fill = PatternFill(\"solid\", fgColor=\"E0E0E0\")\n            elif item == \"Net Change in Cash\":\n                cell.value = f\"={col_letter}5+{col_letter}7+{col_letter}11\"\n                cell.fill = PatternFill(\"solid\", fgColor=\"E0E0E0\")\n            elif item == \"Beginning Cash\":\n                if prev_col:\n                    cell.value = f\"={prev_col}14\"\n                else:\n                    cell.value = 0 # first period\n                cell.fill = PatternFill(\"solid\", fgColor=\"E0E0E0\")\n            elif item == \"Ending Cash\":\n                cell.value = f\"={col_letter}12+{col_letter}13\"\n                cell.fill = PatternFill(\"solid\", fgColor=\"E0E0E0\")\n\n    # 4. Debt Schedule\n    ws_ds = wb.create_sheet(\"Debt Schedule\")\n    ws_ds.append(headers)\n    for cell in ws_ds[1]: cell.font = Font(bold=True)\n    \n    ds_items = [\n        \"Senior Debt\", \"Beginning Balance\", \"Drawdowns\", \"Repayments\", \"Ending Balance\", \"Interest Rate\", \"Interest Expense\",\n        \"Mezzanine Debt\", \"Beginning Balance\", \"Drawdowns\", \"Repayments\", \"Ending Balance\", \"Interest Rate\", \"Interest Expense\",\n        \"Total Interest Expense\", \"Total Ending Debt\"\n    ]\n    \n    for i, item in enumerate(ds_items, 2):\n        ws_ds.cell(row=i, column=1, value=item)\n        if item in [\"Senior Debt\", \"Mezzanine Debt\"]:\n            ws_ds.cell(row=i, column=1).font = Font(bold=True)\n            continue\n            \n        for col in range(2, 8):\n            cell = ws_ds.cell(row=i, column=col)\n            col_letter = openpyxl.utils.get_column_letter(col)\n            prev_col = openpyxl.utils.get_column_letter(col-1) if col > 2 else None\n            \n            if item == \"Interest Rate\":\n                cell.number_format = '0.0%'\n            else:\n                cell.number_format = '#,##0'\n                \n            if item == \"Beginning Balance\":\n                if prev_col:\n                    cell.value = f\"={prev_col}{i+3}\"\n                    cell.fill = PatternFill(\"solid\", fgColor=\"E0E0E0\")\n            elif item == \"Ending Balance\":\n                cell.value = f\"={col_letter}{i-3}+{col_letter}{i-2}-{col_letter}{i-1}\"\n                cell.fill = PatternFill(\"solid\", fgColor=\"E0E0E0\")\n            elif item == \"Interest Expense\":\n                cell.value = f\"={col_letter}{i-5}*{col_letter}{i-1}\"\n                cell.fill = PatternFill(\"solid\", fgColor=\"E0E0E0\")\n            elif item == \"Total Interest Expense\":\n                cell.value = f\"={col_letter}8+{col_letter}15\"\n                cell.fill = PatternFill(\"solid\", fgColor=\"E0E0E0\")\n            elif item == \"Total Ending Debt\":\n                cell.value = f\"={col_letter}6+{col_letter}13\"\n                cell.fill = PatternFill(\"solid\", fgColor=\"E0E0E0\")\n\n    # 5. Returns Analysis\n    ws_ra = wb.create_sheet(\"Returns Analysis\")\n    ws_ra.append([\"Metric\", \"Value\"])\n    for cell in ws_ra[1]: cell.font = Font(bold=True)\n    \n    ra_items = [\n        (\"Entry EV\", \"\"),\n        (\"Exit Multiple\", \"\"),\n        (\"Exit EV\", \"='Income Statement'!G6*B3\"),\n        (\"Net Debt at Exit\", \"='Debt Schedule'!G17\"),\n        (\"Exit Equity\", \"=B4-B5\"),\n        (\"Equity Invested\", \"\"),\n        (\"MOIC\", \"=B6/B7\"),\n        (\"IRR\", \"\")\n    ]\n    \n    for i, (item, form) in enumerate(ra_items, 2):\n        ws_ra.cell(row=i, column=1, value=item)\n        cell = ws_ra.cell(row=i, column=2)\n        if form:\n            cell.value = form\n            cell.fill = PatternFill(\"solid\", fgColor=\"E0E0E0\")\n        \n        if item in [\"Exit Multiple\", \"MOIC\"]:\n            cell.number_format = '0.0x'\n        elif item == \"IRR\":\n            cell.number_format = '0.0%'\n        else:\n            cell.number_format = '#,##0'\n\n    os.makedirs(\"../templates\", exist_ok=True)\n    wb.save(\"../templates/lbo_template.xlsx\")\n\n\ndef create_three_statement():\n    \"\"\"3-Statement model: IS + BS + CF only. No debt schedule or returns.\"\"\"\n    wb = openpyxl.Workbook()\n    hdrs = [\"Line Item\", \"FY2020\", \"FY2021\", \"FY2022\", \"FY2023\", \"FY2024\", \"FY2025\"]\n    formula_fill = PatternFill(\"solid\", fgColor=\"E0E0E0\")\n\n    # Income Statement\n    ws = wb.active\n    ws.title = \"Income Statement\"\n    ws.append(hdrs)\n    for c in ws[1]: c.font = Font(bold=True)\n    items = [\"Revenue\", \"COGS\", \"Gross Profit\", \"SG&A\", \"EBITDA\", \"D&A\", \"EBIT\",\n             \"Interest Expense\", \"EBT\", \"Tax\", \"Net Income\"]\n    for i, item in enumerate(items, 2):\n        ws.cell(row=i, column=1, value=item)\n        for col in range(2, 8):\n            cell = ws.cell(row=i, column=col)\n            cell.number_format = '#,##0'\n            cl = openpyxl.utils.get_column_letter(col)\n            if item == \"Gross Profit\":\n                cell.value = f\"={cl}2-{cl}3\"; cell.fill = formula_fill\n            elif item == \"EBITDA\":\n                cell.value = f\"={cl}4-{cl}5\"; cell.fill = formula_fill\n            elif item == \"EBIT\":\n                cell.value = f\"={cl}6-{cl}7\"; cell.fill = formula_fill\n            elif item == \"EBT\":\n                cell.value = f\"={cl}8-{cl}9\"; cell.fill = formula_fill\n            elif item == \"Net Income\":\n                cell.value = f\"={cl}10-{cl}11\"; cell.fill = formula_fill\n\n    # Balance Sheet (simplified \u2014 no senior/mezz split)\n    ws_bs = wb.create_sheet(\"Balance Sheet\")\n    ws_bs.append(hdrs)\n    for c in ws_bs[1]: c.font = Font(bold=True)\n    bs = [\"Cash\", \"Accounts Receivable\", \"Inventory\", \"Total Current Assets\",\n          \"PP&E Net\", \"Total Assets\",\n          \"Accounts Payable\", \"Accrued Expenses\", \"Debt\", \"Total Liabilities\",\n          \"Common Equity\", \"Retained Earnings\", \"Total Equity\", \"Total Liabilities & Equity\"]\n    for i, item in enumerate(bs, 2):\n        ws_bs.cell(row=i, column=1, value=item)\n        for col in range(2, 8):\n            cell = ws_bs.cell(row=i, column=col)\n            cell.number_format = '#,##0'\n            cl = openpyxl.utils.get_column_letter(col)\n            pc = openpyxl.utils.get_column_letter(col-1) if col > 2 else None\n            if item == \"Total Current Assets\":\n                cell.value = f\"=SUM({cl}2:{cl}4)\"; cell.fill = formula_fill\n            elif item == \"Total Assets\":\n                cell.value = f\"={cl}5+{cl}6\"; cell.fill = formula_fill\n            elif item == \"Total Liabilities\":\n                cell.value = f\"=SUM({cl}8:{cl}10)\"; cell.fill = formula_fill\n            elif item == \"Retained Earnings\":\n                cell.value = (f\"={pc}13+'Income Statement'!{cl}12\" if pc\n                              else f\"='Income Statement'!{cl}12\")\n                cell.fill = formula_fill\n            elif item == \"Total Equity\":\n                cell.value = f\"={cl}12+{cl}13\"; cell.fill = formula_fill\n            elif item == \"Total Liabilities & Equity\":\n                cell.value = f\"={cl}11+{cl}14\"; cell.fill = formula_fill\n\n    # Cash Flow\n    ws_cf = wb.create_sheet(\"Cash Flow\")\n    ws_cf.append(hdrs)\n    for c in ws_cf[1]: c.font = Font(bold=True)\n    cf = [\"Net Income\", \"D&A\", \"Changes in Working Capital\", \"Operating CF\",\n          \"CapEx\", \"Investing CF\", \"Net Change in Cash\", \"Beginning Cash\", \"Ending Cash\"]\n    for i, item in enumerate(cf, 2):\n        ws_cf.cell(row=i, column=1, value=item)\n        for col in range(2, 8):\n            cell = ws_cf.cell(row=i, column=col)\n            cell.number_format = '#,##0'\n            cl = openpyxl.utils.get_column_letter(col)\n            pc = openpyxl.utils.get_column_letter(col-1) if col > 2 else None\n            if item == \"Net Income\":\n                cell.value = f\"='Income Statement'!{cl}12\"; cell.fill = formula_fill\n            elif item == \"D&A\":\n                cell.value = f\"='Income Statement'!{cl}7\"; cell.fill = formula_fill\n            elif item == \"Operating CF\":\n                cell.value = f\"={cl}2+{cl}3+{cl}4\"; cell.fill = formula_fill\n            elif item == \"Investing CF\":\n                cell.value = f\"=-{cl}6\"; cell.fill = formula_fill\n            elif item == \"Net Change in Cash\":\n                cell.value = f\"={cl}5+{cl}7\"; cell.fill = formula_fill\n            elif item == \"Beginning Cash\":\n                cell.value = f\"={pc}10\" if pc else 0; cell.fill = formula_fill\n            elif item == \"Ending Cash\":\n                cell.value = f\"={cl}8+{cl}9\"; cell.fill = formula_fill\n\n    wb.save(\"../templates/three_statement_template.xlsx\")\n\n\ndef create_dcf():\n    \"\"\"DCF model: Revenue Build + IS + FCF + DCF Valuation.\"\"\"\n    wb = openpyxl.Workbook()\n    hdrs = [\"Line Item\", \"FY2020\", \"FY2021\", \"FY2022\", \"FY2023\", \"FY2024\", \"FY2025\"]\n    formula_fill = PatternFill(\"solid\", fgColor=\"E0E0E0\")\n\n    # Revenue Build\n    ws = wb.active\n    ws.title = \"Revenue Build\"\n    ws.append(hdrs)\n    for c in ws[1]: c.font = Font(bold=True)\n    rev_items = [\"Segment A Revenue\", \"Segment A Growth\", \"Segment B Revenue\",\n                 \"Segment B Growth\", \"Total Revenue\"]\n    for i, item in enumerate(rev_items, 2):\n        ws.cell(row=i, column=1, value=item)\n        for col in range(2, 8):\n            cell = ws.cell(row=i, column=col)\n            cl = openpyxl.utils.get_column_letter(col)\n            if \"Growth\" in item:\n                cell.number_format = '0.0%'\n           \n\n... [File truncated: 3000 chars omitted]",
  "language": "python",
  "truncated": true,
  "original_size": 18000
}

9. [Source 9] read_source_content({"source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/excel_io/writer.py"}): {
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/excel_io/writer.py",
  "content": "import openpyxl\nfrom backend.models.schemas import SyntheticPayload\n\ndef write_synthetic_data(template_path: str, payload: SyntheticPayload, output_path: str) -> str:\n    wb = openpyxl.load_workbook(template_path, data_only=False)\n    \n    for cell_value in payload.cells:\n        if cell_value.sheet_name in wb.sheetnames:\n            ws = wb[cell_value.sheet_name]\n            cell = ws[cell_value.cell_ref]\n            \n            existing_val = cell.value\n            if isinstance(existing_val, str) and existing_val.startswith(\"=\"):\n                continue\n                \n            ws[cell_value.cell_ref] = cell_value.value\n            \n    wb.save(output_path)\n    return output_path\n",
  "language": "python",
  "truncated": false,
  "original_size": 698
}

10. [Reflection] ## Key Findings So Far

### 1. Template Row Layout (from generate_templates.py)

**LBO Income Statement (actual):**
- Row 2: Revenue (INPUT), Row 3: COGS (INPUT), Row 4: Gross Profit (FORMULA)
- Row 5: SG&A (INPUT), Row 6: EBITDA (FORMULA), Row 7: D&A (INPUT)
- Row 8: EBIT (FORMULA), Row 9: Interest Expense (FORMULA from DS!16)
- Row 10: EBT (FORMULA), Row 11: Tax (INPUT), Row 12: Net Income (FORMULA)

**LBO Balance Sheet (actual):**
- Row 2: Cash (INPUT), Row 3: AR (INPUT), Row 4: Inventory (INPUT), Row 5: Other Curr (INPUT)
- Row 6: Total Curr Assets (FORMULA), Row 7: PP&E Net (INPUT)
- Row 8: Goodwill (INPUT), Row 9: Other Non-Curr (INPUT), Row 10: Total Assets (FORMULA)
- Row 11: AP (INPUT), Row 12: Accrued (INPUT), Row 13: Curr Debt (INPUT)
- Row 14: Total Curr Liab (FORMULA), Row 15: Senior Debt (INPUT), Row 16: Mezz Debt (INPUT)
- Row 17: Total Liabilities (FORMULA), Row 18: Common Equity (INPUT)
- Row 19: Retained Earnings (FORMULA!), Row 20: Total Equity (FORMULA)
- Row 21: Total L&E (FORMULA)

**Cash Flow (sheet named 'Cash Flow' NOT 'Cash Flow Statement'):**
- Row 2: NI (FORMULA), Row 3: D&A (FORMULA), Row 4: WC Changes (INPUT - single line!)
- Row 5: Operating CF (FORMULA), Row 6: CapEx (INPUT), Row 7: Investing CF (FORMULA)
- Row 8: Debt Drawdowns (INPUT), Row 9: Debt Repayments (INPUT), Row 10: Dividends (INPUT)
- Row 11: Financing CF (FORMULA), Row 12: Net Change (FORMULA)
- Row 13: Beginning Cash (FORMULA!), Row 14: Ending Cash (FORMULA)

**Debt Schedule:**
- Row 2: Senior Debt (section header), Row 3: Begin Bal, Row 4: Drawdowns, Row 5: Repayments
- Row 6: Ending Bal (FORMULA), Row 7: Interest Rate, Row 8: Interest Expense (FORMULA: =B3*B7, BEGIN×RATE)
- Row 9: Mezzanine Debt (section header), Row 10: Begin Bal, Row 11: Drawdowns, Row 12: Repayments
- Row 13: Ending Bal (FORMULA), Row 14: Interest Rate, Row 15: Interest Expense (FORMULA: =B10*B14, BEGIN×RATE)
- Row 16: Total Interest (FORMULA), Row 17: Total Ending Debt (FORMULA)

### 2. Critical Mismatches Confirmed
- **Sheet name**: Solver uses 'Cash Flow Statement', template uses 'Cash Flow'
- **Interest method**: Solver uses AVERAGE balance × rate, template uses BEGIN balance × rate
- **Retained Earnings is a FORMULA**: Solver tries to write to it, writer SKIPS it
- **Beginning Cash is a FORMULA**: Same problem
- **Every single row number is wrong** in both post_processor.py and _add_validation_sheet
- **Template is much simpler**: No R&D, Other OpEx, PP&E Gross/Accum Depr, Intangibles, Deferred items, AOCI
- **Working capital is a single input cell**, not 5 separate items

### 3. Writer Formula-Skip
Confirmed: writer.py checks `existing_val.startswith('=')` and skips. So post-processor adjustments to formula cells are silently discarded.

### Gaps Remaining
- Need the truncated part of main.py (validation sections 7-8, summary dashboard)
- Need to understand the 3-Statement and DCF template layouts for generalization
- Need to design the row_map builder and normalization strategy

### Confidence: HIGH on diagnosis, MEDIUM on implementation plan (need more detail)

### Next Actions:
1. Read the remaining part of main.py (sections 7-8)
2. Read the orchestrator.py to understand how post_processor is called
3. Design the row_map builder and implementation plan

11. [Source 10] think({"reflection": "## Key Findings So Far\n\n### 1. Template Row Layout (from generate_templates.py)\n\n**LBO Income Statement (actual):**\n- Row 2: Revenue (INPUT), Row 3: COGS (INPUT), Row 4: Gross Profit (FORMULA)\n- Row 5: SG&A (INPUT), Row 6: EBITDA (FORMULA), Row 7: D&A (INPUT)\n- Row 8: EBIT (FORMULA), Row 9: Interest Expense (FORMULA from DS!16)\n- Row 10: EBT (FORMULA), Row 11: Tax (INPUT), Row 12: Net Income (FORMULA)\n\n**LBO Balance Sheet (actual):**\n- Row 2: Cash (INPUT), Row 3: AR (INPUT), Row 4: Inventory (INPUT), Row 5: Other Curr (INPUT)\n- Row 6: Total Curr Assets (FORMULA), Row 7: PP&E Net (INPUT)\n- Row 8: Goodwill (INPUT), Row 9: Other Non-Curr (INPUT), Row 10: Total Assets (FORMULA)\n- Row 11: AP (INPUT), Row 12: Accrued (INPUT), Row 13: Curr Debt (INPUT)\n- Row 14: Total Curr Liab (FORMULA), Row 15: Senior Debt (INPUT), Row 16: Mezz Debt (INPUT)\n- Row 17: Total Liabilities (FORMULA), Row 18: Common Equity (INPUT)\n- Row 19: Retained Earnings (FORMULA!), Row 20: Total Equity (FORMULA)\n- Row 21: Total L&E (FORMULA)\n\n**Cash Flow (sheet named 'Cash Flow' NOT 'Cash Flow Statement'):**\n- Row 2: NI (FORMULA), Row 3: D&A (FORMULA), Row 4: WC Changes (INPUT - single line!)\n- Row 5: Operating CF (FORMULA), Row 6: CapEx (INPUT), Row 7: Investing CF (FORMULA)\n- Row 8: Debt Drawdowns (INPUT), Row 9: Debt Repayments (INPUT), Row 10: Dividends (INPUT)\n- Row 11: Financing CF (FORMULA), Row 12: Net Change (FORMULA)\n- Row 13: Beginning Cash (FORMULA!), Row 14: Ending Cash (FORMULA)\n\n**Debt Schedule:**\n- Row 2: Senior Debt (section header), Row 3: Begin Bal, Row 4: Drawdowns, Row 5: Repayments\n- Row 6: Ending Bal (FORMULA), Row 7: Interest Rate, Row 8: Interest Expense (FORMULA: =B3*B7, BEGIN\u00d7RATE)\n- Row 9: Mezzanine Debt (section header), Row 10: Begin Bal, Row 11: Drawdowns, Row 12: Repayments\n- Row 13: Ending Bal (FORMULA), Row 14: Interest Rate, Row 15: Interest Expense (FORMULA: =B10*B14, BEGIN\u00d7RATE)\n- Row 16: Total Interest (FORMULA), Row 17: Total Ending Debt (FORMULA)\n\n### 2. Critical Mismatches Confirmed\n- **Sheet name**: Solver uses 'Cash Flow Statement', template uses 'Cash Flow'\n- **Interest method**: Solver uses AVERAGE balance \u00d7 rate, template uses BEGIN balance \u00d7 rate\n- **Retained Earnings is a FORMULA**: Solver tries to write to it, writer SKIPS it\n- **Beginning Cash is a FORMULA**: Same problem\n- **Every single row number is wrong** in both post_processor.py and _add_validation_sheet\n- **Template is much simpler**: No R&D, Other OpEx, PP&E Gross/Accum Depr, Intangibles, Deferred items, AOCI\n- **Working capital is a single input cell**, not 5 separate items\n\n### 3. Writer Formula-Skip\nConfirmed: writer.py checks `existing_val.startswith('=')` and skips. So post-processor adjustments to formula cells are silently discarded.\n\n### Gaps Remaining\n- Need the truncated part of main.py (validation sections 7-8, summary dashboard)\n- Need to understand the 3-Statement and DCF template layouts for generalization\n- Need to design the row_map builder and normalization strategy\n\n### Confidence: HIGH on diagnosis, MEDIUM on implementation plan (need more detail)\n\n### Next Actions:\n1. Read the remaining part of main.py (sections 7-8)\n2. Read the orchestrator.py to understand how post_processor is called\n3. Design the row_map builder and implementation plan"}): Reflection recorded. Continue with next action.

12. [Source 11] read_source_content({"source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/orchestrator.py"}): {
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/orchestrator.py",
  "content": "import asyncio\nimport uuid\nimport time\nimport logging\nfrom typing import Callable, Awaitable\nfrom datetime import datetime\n\nfrom backend.config import Settings\nfrom backend.models.schemas import JobState, WSEvent, AuditLogEntry, TemplateSchema, SyntheticPayload\nfrom backend.excel_io.parser import parse_template\nfrom backend.excel_io.writer import write_synthetic_data\nfrom backend.agents.schema_extractor import extract_schema\nfrom backend.agents.synthetic_gen import generate_synthetic_data\nfrom backend.agents.validator import DeterministicValidator\nfrom backend.agents.post_processor import post_process\nfrom backend.middleware import cost_tracker\n\nlogger = logging.getLogger(__name__)\n\nclass PipelineOrchestrator:\n    def __init__(self, settings: Settings):\n        self.settings = settings\n        self.jobs: dict[str, JobState] = {}\n\n    def _update_status(self, job_id: str, status: str):\n        self.jobs[job_id].status = status\n\n    def _log_audit(self, job_id: str, phase: str, detail: str, agent: str = None, data: dict = None):\n        entry = AuditLogEntry(\n            timestamp=datetime.utcnow().isoformat() + \"Z\",\n            phase=phase,\n            detail=detail,\n            agent=agent,\n            data=data\n        )\n        self.jobs[job_id].audit_log.append(entry)\n\n    async def run_pipeline(self, job_id: str, file_path: str, ws_callback: Callable[[WSEvent], Awaitable[None]]):\n        try:\n            await asyncio.wait_for(\n                self._execute(job_id, file_path, ws_callback),\n                timeout=self.settings.generation_timeout_s\n            )\n        except asyncio.TimeoutError:\n            self._update_status(job_id, \"error\")\n            self.jobs[job_id].error_message = \"Generation timed out\"\n            await ws_callback(WSEvent(job_id=job_id, phase=\"error\", event_type=\"error\", detail=\"Generation timed out\"))\n        except Exception as e:\n            self._update_status(job_id, \"error\")\n            self.jobs[job_id].error_message = str(e)\n            await ws_callback(WSEvent(job_id=job_id, phase=\"error\", event_type=\"error\", detail=str(e)))\n\n    async def _execute(self, job_id: str, file_path: str, ws_callback: Callable[[WSEvent], Awaitable[None]]):\n        # 1. Parse Phase\n        self._update_status(job_id, \"parsing\")\n        await ws_callback(WSEvent(job_id=job_id, phase=\"parse\", event_type=\"progress\", detail=\"Parsing Excel template...\"))\n        \n        parsed = await asyncio.to_thread(parse_template, file_path)\n        self._log_audit(job_id, \"parse\", \"Template parsed\", data={\"total_input_cells\": parsed[\"total_input_cells\"]})\n        await ws_callback(WSEvent(job_id=job_id, phase=\"parse\", event_type=\"progress\", detail=f\"Found {parsed['total_input_cells']} input cells across {len(parsed['sheets'])} sheets\"))\n        for sheet in parsed['sheets']:\n            await ws_callback(WSEvent(job_id=job_id, phase=\"parse\", event_type=\"progress\", detail=f\"[MAP] {sheet['name']} -> {len(sheet['input_cells'])} input cells\"))\n\n        # 2. Schema Extraction Phase\n        self._update_status(job_id, \"extracting_schema\")\n        await ws_callback(WSEvent(job_id=job_id, phase=\"schema_extract\", event_type=\"progress\", detail=\"Schema extraction starting...\"))\n        \n        async def schema_progress(msg):\n            await ws_callback(WSEvent(job_id=job_id, phase=\"schema_extract\", event_type=\"progress\", detail=msg))\n\n        schema = await extract_schema(parsed, self.settings, on_progress=schema_progress)\n        self.jobs[job_id].template_schema = schema\n        self._log_audit(job_id, \"schema_extract\", \"Schema extracted successfully\", agent=self.settings.gemini_fast_model)\n\n        cost_entry = cost_tracker.log_cost(\"schema_extractor\", self.settings.gemini_fast_model, {\"prompt_tokens\": 1000, \"completion_tokens\": 500, \"total_tokens\": 1500})\n        self.jobs[job_id].cost_entries.append(cost_entry)\n        \n        await ws_callback(WSEvent(job_id=job_id, phase=\"schema_extract\", event_type=\"progress\", detail=f\"[TYPE] Model classified as: {schema.model_type}\"))\n        for ref in schema.inter_sheet_refs:\n            await ws_callback(WSEvent(job_id=job_id, phase=\"schema_extract\", event_type=\"progress\", detail=f\"[LINK] {ref.source_sheet}.{ref.source_column} -> {ref.target_sheet}.{ref.target_column} \u2713\"))\n\n        # 3. Generation & Validation Loop\n        self._update_status(job_id, \"generating\")\n        retry_instructions = None\n        \n        for attempt in range(self.settings.max_retries):\n            # Generate\n            await ws_callback(WSEvent(job_id=job_id, phase=\"generate\", event_type=\"progress\", detail=\"Synthetic generation starting (sheet-by-sheet)...\"))\n            payload = await generate_synthetic_data(schema, self.settings, retry_instructions, parsed_template=parsed)\n\n            # Post-process: fix rolling balances, sign conventions, zero fills\n            raw_cells = [c.model_dump() for c in payload.cells]\n            fixed_cells = post_process(raw_cells, parsed)\n            from backend.models.schemas import CellValue\n            payload.cells = [CellValue(**c) for c in fixed_cells]\n\n            self.jobs[job_id].synthetic_payload = payload\n            self._log_audit(job_id, \"generate\", f\"Generated synthetic payload (attempt {attempt+1})\", agent=self.settings.gemini_model)\n\n            gen_cost = cost_tracker.log_cost(\"synthetic_gen\", self.settings.gemini_model, payload.generation_metadata.token_usage)\n            self.jobs[job_id].cost_entries.append(gen_cost)\n            \n            for cell in payload.cells:\n                await ws_callback(WSEvent(\n                    job_id=job_id, phase=\"generate\", event_type=\"cell_update\",\n                    detail=f\"{cell.sheet_name}.{cell.header} [{cell.period}] = {cell.value}\",\n                    data={\"sheet\": cell.sheet_name, \"cell_ref\": cell.cell_ref, \"value\": cell.value}\n                ))\n            \n            # Validate\n            self._update_status(job_id, \"validating\")\n            validator = DeterministicValidator(schema)\n            result = validator.validate(payload)\n            self.jobs[job_id].validation_result = result\n            \n            for rule in result.rules:\n                if rule.passed:\n                    await ws_callback(WSEvent(job_id=job_id, phase=\"validate\", event_type=\"validation\", detail=f\"\u2713 {rule.rule_name} ({rule.period})\"))\n            \n            for adj in result.adjustments:\n                await ws_callback(WSEvent(job_id=job_id, phase=\"validate\", event_type=\"validation\", detail=f\"\u26a1 Adjusted {adj.target_cell} by {adj.delta:+,.0f} to force {adj.reason}\"))\n            \n            if result.status == \"FAILED\":\n                if attempt < self.settings.max_retries - 1:\n                    retry_instructions = validator.build_retry_instructions()\n                    self.jobs[job_id].retry_count += 1\n                    self._log_audit(job_id, \"validate\", f\"Validation failed, retrying. {retry_instructions}\", agent=\"DeterministicValidator\")\n                    await ws_callback(WSEvent(job_id=job_id, phase=\"validate\", event_type=\"progress\", detail=f\"Retrying generation (attempt {attempt+2})...\"))\n                    self._update_status(job_id, \"generating\")\n                    continue\n                else:\n                    raise Exception(\"Validation failed after maximum retries\")\n            \n            # Passed\n            self._log_audit(job_id, \"validate\", \"Validation passed\", agent=\"DeterministicValidator\", data={\"status\": result.status})\n            \n            # 4. Write Phase\n            self._update_status(job_id, \"writing\")\n            output_path = f\"/tmp/safe_harbor/{job_id}/output.xlsx\"\n            import os\n            os.makedirs(os.path.dirname(output_path), exist_ok=True)\n            \n            final_payload = result.validated_payload if result.validated_payload else payload\n            await asyncio.to_thread(write_synthetic_data, file_path, final_payload, output_path)\n            \n            self.jobs[job_id].output_file_path = output_path\n            self._update_status(job_id, \"complete\")\n            self._log_audit(job_id, \"write\", \"Output file generated successfully\")\n            \n            await ws_callback(WSEvent(job_id=job_id, phase=\"write\", event_type=\"complete\", detail=\"Success\", data=result.model_dump()))\n            break\n",
  "language": "python",
  "truncated": false,
  "original_size": 8347
}

13. [Source 12] read_source_content({"source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/agents/validator.py"}): {
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/agents/validator.py",
  "content": "from datetime import datetime\nimport copy\nfrom backend.models.schemas import TemplateSchema, SyntheticPayload, ValidationResult, ValidationRuleResult, PlugAdjustment\n\n\nclass DeterministicValidator:\n    def __init__(self, schema: TemplateSchema):\n        self.schema = schema\n        self.adjustments = []\n        self.needs_regeneration = []\n\n    def validate(self, payload: SyntheticPayload) -> ValidationResult:\n        # Group cells by period and header for fast lookup\n        # lookup[period][header_lower] = CellValue\n        self.lookup = {}\n        for cell in payload.cells:\n            if cell.period not in self.lookup:\n                self.lookup[cell.period] = {}\n            self.lookup[cell.period][cell.header.lower().strip()] = cell\n\n        self.adjustments = []\n        self.needs_regeneration = []\n\n        rules_results = []\n        rules_results.extend(self._rule_balance_sheet_identity(payload))\n        rules_results.extend(self._rule_cash_flow_reconciliation(payload))\n        rules_results.extend(self._rule_net_income_linkage(payload))\n        rules_results.extend(self._rule_margin_bounds(payload))\n        rules_results.extend(self._rule_depreciation_constraint(payload))\n        rules_results.extend(self._rule_debt_schedule_integrity(payload))\n\n        status = \"PASSED\"\n        if self.needs_regeneration:\n            status = \"FAILED\"\n        elif self.adjustments:\n            status = \"PASSED_WITH_PLUGS\"\n\n        validated_payload = self._apply_plug_adjustments(payload, self.adjustments) if status != \"FAILED\" else None\n\n        return ValidationResult(\n            status=status,\n            rules=rules_results,\n            adjustments=self.adjustments,\n            needs_regeneration=self.needs_regeneration,\n            validated_payload=validated_payload,\n            validation_timestamp=datetime.utcnow().isoformat() + \"Z\"\n        )\n\n    def _get_val(self, period, header_keywords):\n        \"\"\"Fuzzy match: returns first CellValue whose lowered header contains any keyword.\"\"\"\n        period_data = self.lookup.get(period, {})\n        for h, cell in period_data.items():\n            for kw in header_keywords:\n                if kw in h:\n                    return cell\n        return None\n\n    def _sorted_periods(self):\n        \"\"\"Return periods sorted lexicographically (FY2020 < FY2021 etc.).\"\"\"\n        return sorted(self.lookup.keys())\n\n    # \u2500\u2500 Rule 1: Balance Sheet Identity \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n    def _rule_balance_sheet_identity(self, payload: SyntheticPayload) -> list[ValidationRuleResult]:\n        results = []\n        for period in self.lookup.keys():\n            assets = self._get_val(period, [\"total assets\"])\n            liab = self._get_val(period, [\"total liabilities\"])\n            eq = self._get_val(period, [\"total equity\"])\n\n            if assets and liab and eq:\n                a_val = float(assets.value)\n                l_val = float(liab.value)\n                e_val = float(eq.value)\n\n                delta = a_val - (l_val + e_val)\n                passed = abs(delta) < 0.01\n\n                adj = None\n                if not passed:\n                    cash_cell = self._get_val(period, [\"cash\"])\n                    if cash_cell:\n                        orig = float(cash_cell.value)\n                        adj_val = orig + delta\n                        adj = PlugAdjustment(\n                            target_cell=cash_cell.header,\n                            target_sheet=cash_cell.sheet_name,\n                            period=period,\n                            original_value=orig,\n                            adjusted_value=adj_val,\n                            delta=delta,\n                            reason=f\"BS imbalance: Assets - (Liab + Eq) = {delta:+,.0f}\"\n                        )\n                        self.adjustments.append(adj)\n                    else:\n                        self.needs_regeneration.append(\"Cash / Total Assets\")\n\n                results.append(ValidationRuleResult(\n                    rule_name=\"balance_sheet_identity\",\n                    period=period,\n                    passed=passed,\n                    expected=l_val + e_val,\n                    actual=a_val,\n                    delta=delta,\n                    adjustment_applied=adj\n                ))\n        return results\n\n    # \u2500\u2500 Rule 2: Cash Flow Reconciliation \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n    def _rule_cash_flow_reconciliation(self, payload: SyntheticPayload) -> list[ValidationRuleResult]:\n        results = []\n        periods = self._sorted_periods()\n        prev_ending_cash = None\n\n        for period in periods:\n            ending = self._get_val(period, [\"ending cash\", \"cash end\"])\n            beginning = self._get_val(period, [\"beginning cash\", \"cash begin\", \"opening cash\"])\n            net_cf = self._get_val(period, [\"net change in cash\", \"net cash flow\", \"total cash flow\"])\n\n            if ending and net_cf:\n                e_val = float(ending.value)\n                n_val = float(net_cf.value)\n\n                # Beginning cash: prefer explicit cell, else use prior period ending\n                if beginning:\n                    b_val = float(beginning.value)\n                elif prev_ending_cash is not None:\n                    b_val = prev_ending_cash\n                else:\n                    b_val = 0.0\n\n                expected_ending = b_val + n_val\n                delta = e_val - expected_ending\n                passed = abs(delta) < 0.01\n\n                adj = None\n                if not passed:\n                    # Plug via \"Other Cash Flow Items\" or adjust net_cf\n                    other_cf = self._get_val(period, [\"other cash flow\", \"other operating\", \"other cf\"])\n                    if other_cf:\n                        orig = float(other_cf.value)\n                        adj = PlugAdjustment(\n                            target_cell=other_cf.header,\n                            target_sheet=other_cf.sheet_name,\n                            period=period,\n                            original_value=orig,\n                            adjusted_value=orig + delta,\n                            delta=delta,\n                            reason=f\"CF mismatch: Ending - (Begin + Net) = {delta:+,.0f}\"\n                        )\n                        self.adjustments.append(adj)\n                    else:\n                        # No plug account available \u2014 adjust ending cash directly\n                        adj = PlugAdjustment(\n                            target_cell=ending.header,\n                            target_sheet=ending.sheet_name,\n                            period=period,\n                            original_value=e_val,\n                            adjusted_value=expected_ending,\n                            delta=-delta,\n                            reason=f\"CF mismatch: forced Ending Cash = Begin + Net CF\"\n                        )\n                        self.adjustments.append(adj)\n\n                results.append(ValidationRuleResult(\n                    rule_name=\"cash_flow_reconciliation\",\n                    period=period,\n                    passed=passed,\n                    expected=expected_ending,\n                    actual=e_val,\n                    delta=delta,\n                    adjustment_applied=adj\n                ))\n                prev_ending_cash = e_val if passed else expected_ending\n            else:\n                if ending:\n                    prev_ending_cash = float(ending.value)\n        return results\n\n    # \u2500\u2500 Rule 3: Net Income Linkage \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n    def _rule_net_income_linkage(self, payload: SyntheticPayload) -> list[ValidationRuleResult]:\n        results = []\n        for period in self.lookup.keys():\n            pl_ni = self._get_val(period, [\"net income\"])\n            cf_ni = None\n            # Look for net income specifically on cash flow sheet\n            period_data = self.lookup.get(period, {})\n            for h, cell in period_data.items():\n                if \"net income\" in h and cell.sheet_name.lower() in [\"cash flow\", \"cash flow statement\", \"cf\"]:\n                    cf_ni = cell\n                    break\n\n            if pl_ni and cf_ni and pl_ni.sheet_name != cf_ni.sheet_name:\n                pl_val = float(pl_ni.value)\n                cf_val = float(cf_ni.value)\n                delta = pl_val - cf_val\n                passed = abs(delta) < 0.01\n\n                adj = None\n                if not passed:\n                    # Force CF net income to match P&L\n                    adj = PlugAdjustment(\n                        target_cell=cf_ni.header,\n                        target_sheet=cf_ni.sheet_name,\n                        period=period,\n                        original_value=cf_val,\n                        adjusted_value=pl_val,\n                        delta=delta,\n                        reason=f\"NI linkage: P&L NI ({pl_val:,.0f}) != CF NI ({cf_val:,.0f})\"\n                    )\n                    self.adjustments.append(adj)\n\n                results.append(ValidationRuleResult(\n                    rule_name=\"net_income_linkage\",\n                    period=period,\n                    passed=passed,\n                    expected=pl_val,\n                    actual=cf_val,\n                    delta=delta,\n                    adjustment_applied=adj\n                ))\n        return results\n\n    # \u2500\u2500 Rule 4: Margin Bounds \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n    def _rule_margin_bounds(self, payload: SyntheticPayload) -> list[ValidationRuleResult]:\n        results = []\n        for period in self.lookup.keys():\n            rev = self._get_val(period, [\"revenue\", \"sales\", \"total revenue\"])\n            if not rev or float(rev.value) == 0:\n                continue\n            r_val = float(rev.value)\n\n            # EBITDA margin\n            ebitda = self._get_val(period, [\"ebitda\"])\n            if ebitda:\n                margin = float(ebitda.value) / r_val\n                passed = -0.5 <= margin <= 0.8\n                if not passed:\n                    self.needs_regeneration.append(ebitda.header)\n                results.append(ValidationRuleResult(\n                    rule_name=\"ebitda_margin_bounds\",\n                    period=period,\n                    passed=passed,\n                    expected=0.15,\n                    actual=round(margin, 4),\n                    delta=round(margin - 0.15, 4)\n                ))\n\n            # Gross margin\n            cogs = self._get_val(period, [\"cogs\", \"cost of goods\", \"cost of revenue\"])\n            if cogs:\n                gross_margin = (r_val - float(cogs.value)) / r_val\n                passed = 0.0 <= gross_margin <= 1.0\n                if not passed:\n                    self.needs_regeneration.append(cogs.header)\n                results.append(ValidationRuleResult(\n                    rule_name=\"gross_margin_bounds\",\n                    period=period,\n                    passed=passed,\n                    expected=0.5,\n                    actual=round(gross_margin, 4),\n                    delta=round(gross_margin - 0.5, 4)\n                ))\n\n            # Net margin\n            ni = self._get_val(period, [\"net income\"])\n            if ni:\n                net_margin = float(ni.value) / r_val\n                passed = -1.0 <= net_margin <= 0.5\n                if not passed:\n                    self.needs_regeneration.append(ni.header)\n                results.append(ValidationRuleResult(\n                    rule_name=\"net_margin_bounds\",\n                    period=period,\n                    passed=passed,\n                    expected=0.10,\n                    actual=round(net_margin, 4),\n                    delta=round(net_margin - 0.10, 4)\n                ))\n        return results\n\n    # \u2500\u2500 Rule 5: Depreciation Constraint \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n    def _rule_depreciation_constraint(self, payload: SyntheticPayload) -> list[ValidationRuleResult]:\n        results = []\n        periods = self._sorted_periods()\n        cum_dep = 0.0\n        cum_capex = 0.0\n        opening_ppe = 0.0\n\n        # Try to get opening PP&E from the first period\n        if periods:\n            ppe_cell = self._get_val(periods[0], [\"pp&e\", \"ppe\", \"property plant\", \"fixed assets\"])\n            if ppe_cell:\n                opening_ppe = float(ppe_cell.value)\n\n        for period in periods:\n            dep = self._get_val(period, [\"depreciation\", \"d&a\", \"depreciation & amortization\"])\n            capex = self._get_val(period, [\"capex\", \"capital expenditure\", \"capital expenditures\"])\n\n            if dep:\n                d_val = float(dep.value)\n                cum_dep += abs(d_val)  # depreciation may be stored as negative\n\n                if capex:\n                    cum_capex += abs(float(capex.value))\n\n                ceiling = cum_capex + opening_ppe\n                passed = cum_dep <= ceiling + 0.01\n\n                adj = None\n                if not passed:\n                    # Cap depreciation at the allowed maximum\n                    overshoot = cum_dep - ceiling\n                    new_dep = abs(d_val) - overshoot\n                    adj = PlugAdjustment(\n                        target_cell=dep.header,\n                        target_sheet=dep.sheet_name,\n                        period=period,\n                        original_value=d_val,\n                        adjusted_value=-abs(new_dep) if d_val < 0 else new_dep,\n                        delta=-overshoot,\n                        reason=f\"Depreciation exceeds CapEx + PP&E ceiling by {overshoot:,.0f}\"\n                    )\n                    self.adjustments.append(adj)\n                    cum_dep = ceiling  # reset after cap\n\n                results.append(ValidationRuleResult(\n                    rule_name=\"depreciation_constraint\",\n                    period=period,\n                    passed=passed,\n                    expected=ceiling,\n                    actual=cum_dep,\n                    delta=cum_dep - ceiling,\n                    adjustment_applied=adj\n                ))\n        return results\n\n    # \u2500\u2500 Rule 6: Debt Schedule Integrity \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n    def _rule_debt_schedule_integrity(self, payload: SyntheticPayload) -> list[ValidationRuleResult]:\n        results = []\n        periods = self._sorted_periods()\n\n        # Detect debt tranches from column headers\n        tranche_keywords = [\n            (\"senior debt\", \"senior\"),\n            (\"mezzanine\", \"mezzanine\"),\n            (\"term loan\", \"term loan\"),\n            (\"revolver\", \"revolver\"),\n        ]\n\n        for kw_list, tranche_name in tranche_keywords:\n            prev_ending = None\n            for period in periods:\n                ending = self._get_val(period, [f\"ending {kw_list}\", f\"{kw_list} ending\", f\"ending balance\"])\n                beginning = self._get_val(period, [f\"beginning {kw_list}\", f\"{kw_list} beginning\", f\"beginning balance\"])\n                drawdowns = self._get_val(period, [f\"{kw_list} drawdown\", \"drawdown\"])\n  \n\n... [File truncated: 3010 chars omitted]",
  "language": "python",
  "truncated": true,
  "original_size": 18010
}

14. [Source 13] read_source_content({"source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/models/schemas.py"}): {
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/models/schemas.py",
  "content": "from typing import Literal, Optional, List\nfrom pydantic import BaseModel, Field\n\nclass ColumnConstraints(BaseModel):\n    min_value: Optional[float] = None\n    max_value: Optional[float] = None\n    growth_rate_range: Optional[List[float]] = None  # [min, max] e.g. [-0.1, 0.3]\n    must_be_positive: bool = False\n    must_be_negative: bool = False\n    sum_equals: Optional[str] = None\n\nclass ColumnSchema(BaseModel):\n    header: str\n    data_type: Literal[\n        \"currency_USD\", \"currency_EUR\", \"currency_GBP\",\n        \"percentage\", \"ratio\", \"integer\", \"date\", \"text\"\n    ]\n    temporal_range: Optional[str] = None\n    periods: List[str] = Field(default_factory=list)\n    is_input: bool\n    cell_references: List[str] = Field(default_factory=list)\n    sheet_name: str\n    constraints: ColumnConstraints\n\nclass InterSheetReference(BaseModel):\n    source_sheet: str\n    source_column: str\n    target_sheet: str\n    target_column: str\n    relationship: Literal[\"equals\", \"feeds_into\", \"delta\"]\n\nclass SheetSchema(BaseModel):\n    name: str\n    columns: List[ColumnSchema]\n\nclass TemplateSchema(BaseModel):\n    model_type: Literal[\"LBO\", \"DCF\", \"3-statement\", \"unknown\"]\n    industry: str\n    currency: str\n    sheets: List[SheetSchema]\n    inter_sheet_refs: List[InterSheetReference]\n    total_input_cells: int\n\nclass CellValue(BaseModel):\n    sheet_name: str\n    cell_ref: str\n    header: str\n    period: str\n    value: float | int | str\n\nclass TokenUsage(BaseModel):\n    prompt_tokens: int\n    completion_tokens: int\n    total_tokens: int\n\nclass GenerationMetadata(BaseModel):\n    model_used: str\n    temperature: float\n    token_usage: TokenUsage\n    generation_time_ms: int\n\nclass SyntheticPayload(BaseModel):\n    model_type: str\n    industry: str\n    currency: str\n    cells: List[CellValue]\n    generation_metadata: GenerationMetadata\n\nclass PlugAdjustment(BaseModel):\n    target_cell: str\n    target_sheet: str\n    period: str\n    original_value: float\n    adjusted_value: float\n    delta: float\n    reason: str\n\nclass ValidationRuleResult(BaseModel):\n    rule_name: str\n    period: str\n    passed: bool\n    expected: Optional[float] = None\n    actual: Optional[float] = None\n    delta: Optional[float] = None\n    adjustment_applied: Optional[PlugAdjustment] = None\n\nclass ValidationResult(BaseModel):\n    status: Literal[\"PASSED\", \"PASSED_WITH_PLUGS\", \"FAILED\"]\n    rules: List[ValidationRuleResult]\n    adjustments: List[PlugAdjustment]\n    needs_regeneration: List[str]\n    validated_payload: Optional[SyntheticPayload] = None\n    validation_timestamp: str\n\nclass AuditLogEntry(BaseModel):\n    timestamp: str\n    phase: Literal[\"upload\", \"parse\", \"schema_extract\", \"generate\", \"validate\", \"write\"]\n    agent: Optional[str] = None\n    detail: str\n    data: Optional[dict] = None\n\nclass JobState(BaseModel):\n    job_id: str\n    status: Literal[\"pending\", \"parsing\", \"extracting_schema\", \"generating\", \"validating\", \"writing\", \"complete\", \"error\"]\n    template_schema: Optional[TemplateSchema] = None\n    synthetic_payload: Optional[SyntheticPayload] = None\n    validation_result: Optional[ValidationResult] = None\n    audit_log: List[AuditLogEntry] = Field(default_factory=list)\n    cost_entries: List[dict] = Field(default_factory=list)\n    output_file_path: Optional[str] = None\n    error_message: Optional[str] = None\n    retry_count: int = 0\n\nclass WSEvent(BaseModel):\n    job_id: str\n    phase: str\n    event_type: Literal[\"progress\", \"cell_update\", \"validation\", \"complete\", \"error\"]\n    detail: str\n    data: Optional[dict] = None\n",
  "language": "python",
  "truncated": false,
  "original_size": 3543
}

15. [Source 14] code_grep({"repository_id": "Kaide-LABS/tracelight-safe-harbor", "pattern": "Section 7|Section 8|Returns Analysis|SUMMARY DASHBOARD|def _add_validation|has_ra|has_is|has_bs|has_cf|has_ds", "path": "safe-harbor/backend", "context_lines": 4, "max_total_matches": 50}): {
  "success": true,
  "matches": {},
  "pattern": "Section 7|Section 8|Returns Analysis|SUMMARY DASHBOARD|def _add_validation|has_ra|has_is|has_bs|has_cf|has_ds",
  "path_filter": "safe-harbor/backend",
  "total_matches": 0,
  "files_searched": 0,
  "files_with_matches": 0,
  "truncated": false,
  "options": {
    "case_sensitive": false,
    "lines_before": 4,
    "lines_after": 4,
    "output_mode": "content",
    "whole_word": false,
    "fixed_string": false,
    "highlight": false,
    "include_line_numbers": true,
    "group_by_file": true
  }
}

16. [Source 15] query({"query": "_add_validation_sheet Returns Analysis summary dashboard section 8 validation formulas", "repositories": ["Kaide-LABS/tracelight-safe-harbor"]}): {
  "content": "Query='_add_validation_sheet Returns Analysis summary dashboard section 8 validation formulas'. Repo results=5 (projects=1). Doc results=0 (sources=0).",
  "sources": [
    {
      "content": "Kaide-LABS/tracelight-safe-harbor/safe-harbor/backend/agents/validator.py\nCalls: PlugAdjustment, ValidationRuleResult, _get_val, abs, append\nControl flow: 12 branches, 8 loops, complexity 27\n\ndef _rule_balance_sheet_identity(self, payload: SyntheticPayload) -> list[ValidationRuleResult]:\n        results = []\n        for period in self.lookup.keys():\n            assets = self._get_val(period, [\"total assets\"])\n            liab = self._get_val(period, [\"total liabilities\"])\n            eq = self._get_val(period, [\"total equity\"])\n            \n            if assets and liab and eq:\n                a_val = float(assets.value)\n                l_val = float(liab.value)\n                e_val = float(eq.value)\n                \n                delta = a_val - (l_val + e_val)\n                passed = abs(delta) < 0.01\n                \n                adj = None\n                if not passed:\n                    cash_cell = self._get_val(period, [\"cash\"])\n                    if cash_cell:\n                        orig = float(cash_cell.value)\n                        adj_val = orig + delta\n                        adj = PlugAdjustment(\n                            target_cell=cash_cell.header,\n                            target_sheet=cash_cell.sheet_name,\n                            period=period,\n                            original_value=orig,\n                            adjusted_value=adj_val,\n                            delta=delta,\n                            reason=f\"BS imbalance: Assets - (Liab + Eq) = {delta:+,.0f}\"\n                        )\n                        self.adjustments.append(adj)\n                    else:\n                        # Fallback if no cash cell found\n                        self.needs_regeneration.append(\"Cash / Total Assets\")\n                        \n                results.append(ValidationRuleResult(\n                    rule_name=\"balance_sheet_identity\",\n                    period=period,\n                    passed=passed,\n                    expected=l_val + e_val,\n                    actual=a_val,\n                    delta=delta,\n                    adjustment_applied=adj\n                ))\n        return results\n\n    def _rule_margin_bounds(self, payload: SyntheticPayload) -> list[ValidationRuleResult]:\n        results = []\n        for period in self.lookup.keys():\n            rev = self._get_val(period, [\"revenue\", \"sales\"])\n            ebitda = self._get_val(period, [\"ebitda\"])\n            \n            if rev and ebitda and float(rev.value) != 0:\n                r_val = float(rev.value)\n                e_val = float(ebitda.value)\n                margin = e_val / r_val\n                \n                passed = -0.5 <= margin <= 0.8\n                if not passed:\n                    self.needs_regeneration.append(ebitda.header)\n                    \n                results.append(ValidationRuleResult(\n                    rule_name=\"ebitda_margin_bounds\",\n                    period=period,\n                    passed=passed,\n                    expected=0.15,\n                    actual=margin,\n                    delta=margin - 0.15\n                ))\n        return results\n\n    def _apply_plug_adjustments(self, payload: SyntheticPayload, adjustments: list[PlugAdjustment]) -> SyntheticPayload:\n        new_payload = copy.deepcopy(payload)\n        for adj in adjustments:\n            for cell in new_payload.cells:\n                if cell.period == adj.period and cell.header == adj.target_cell and cell.sheet_name == adj.target_sheet:\n                    cell.value = adj.adjusted_value\n        return new_payload",
      "metadata": {
        "source_type": "repository",
        "repository_project_id": "e83393b7-1ee7-4b81-b0a0-fffc1b7afa1b",
        "file_path": "Kaide-LABS/tracelight-safe-harbor/safe-harbor/backend/agents/validator.py",
        "score": 0.68437004
      }
    },
    {
      "content": "Kaide-LABS/tracelight-safe-harbor/PRD.md\n\n```\n[SCAN] Detecting sheets... 4 found\n[MAP]  Income Statement   23 columns mapped\n[MAP]  Balance Sheet   31 columns mapped\n[MAP]  Cash Flow   18 columns mapped\n[MAP]  Debt Schedule   12 columns mapped\n[LINK] P&L.Net_Income   CF.Net_Income  \n[LINK] CF.Ending_Cash   BS.Cash  \n[TYPE] Model classified as: Leveraged Buyout\n[DONE] Schema extraction complete. 84 input cells identified.\n```\n- Animated DAG visualization: Nodes for each sheet, edges for\ninter-sheet references, pulsing as they're discovered.\n- Duration: ~5-8 seconds.\n\n### Screen 3: Data Generation (The \"Waterfall\" Phase)\n- Full-width Excel-like grid view.\n- Numbers cascade into cells row by row, sheet by sheet.\n- Each cell briefly flashes AMBER as it's written, then GREEN as the\nValidation Agent confirms it.\n- Bottom ticker: \"Generating 5-year historicals for Healthcare SaaS...\"\n- Real-time validation badges appearing as constraints pass:\n```\n  Balance Sheet Balanced (Year 1)\n  Balance Sheet Balanced (Year 2)\n  Cash Flow Reconciled (Year 1)\n  Debt Schedule Verified\n...\n```\n- If a plug adjustment occurs, show it transparently:\n```\n  Adjusted Cash by +$142K to force BS equilibrium (Year 3)\n```\nThis BUILDS trust. It shows the system is honest about corrections,\nnot hiding them.\n- Duration: ~15-25 seconds.\n\n### Screen 4: The Verdict (The \"Magic Moment\")\n- Full-screen modal with large badge:\n```\n                                        \n   SYNTHETIC MODEL VERIFIED  \n   Balance Sheet Balanced (all 5 years)\n   Cash Flow Reconciled (all 5 years)\n   Debt Schedule Amortized Correctly\n   Margins Within Industry Bounds\n   Zero Sensitive Data  \nModel Type:    Leveraged Buyout\nIndustry:      Healthcare SaaS\nTime Horizon:  FY2020   FY2030\nInput Cells:   84 populated\nValidation:    6/6 rules passed  \n[Download .xlsx]     [  START TESTING IN TRACELIGHT]\n                                        \n```\n- The \"START TESTING\" button is the primary CTA. It loads the populated\nmodel directly into Tracelight's core Excel add-in environment.\n- The prospect is now using Tracelight's real product with a model\nthat feels real but triggers zero InfoSec concerns.\n\n### Screen 5: Audit Trail (For the CTO)\n- Expandable panel showing:\n- Full JSON schema extracted in Step 3\n- Every synthetic value generated with its constraint bounds\n- Every validation rule result\n- Every plug adjustment with the exact delta\n- Timestamps for each agent's execution\n- Model/token usage breakdown\n- This is built specifically for Aleksander. He will click this.\nIf it's not there, he won't trust the system.\n\n---\n\n## 4. PHASE 1 EXECUTION SPEC",
      "metadata": {
        "source_type": "repository",
        "repository_project_id": "e83393b7-1ee7-4b81-b0a0-fffc1b7afa1b",
        "file_path": "Kaide-LABS/tracelight-safe-harbor/PRD.md",
        "score": 0.6688491
      }
    },
    {
      "content": "Kaide-LABS/tracelight-safe-harbor/PRD.md\n\nSTEP 3   Deterministic Validation Agent (Hour 6-12)\n- Build validator.py as a pure Python class:\n- Method: validate(payload: SyntheticPayload)   ValidationResult\n- Implement all 6 hardcoded rules (see architecture above)\n- Implement plug-account adjustment logic\n- Implement retry signal (returns which line items need regeneration)\n- TEST: Feed it deliberately broken data (BS doesn't balance,\nnegative margins, depreciation > CapEx). Verify it catches every\nviolation and produces correct plug adjustments.\n- This is the trust anchor. It must be bulletproof before proceeding.\n\nSTEP 4   Schema Extraction Agent (Hour 12-18)\n- Build schema_extractor.py:\n- Takes parsed Excel JSON from parser.py\n- Sends to Gemini 2.0 Flash via Vertex AI\n- System prompt: \"You are a financial model analyst. Given the\nfollowing Excel template structure, classify each column by its\nfinancial data type, identify temporal ranges, detect inter-sheet\ndependencies, and classify the model type. Output strict JSON\nconforming to the TemplateSchema.\"\n- Parse response into TemplateSchema Pydantic model\n- Fallback: If Gemini fails or returns malformed JSON, retry 2x.\nIf still failing, fall back to GPT-4o for schema extraction.\n- TEST: Run against LBO, DCF, and 3-Statement templates. Verify\ncorrect classification of every column.\n\nSTEP 5   Synthetic Generation Agent (Hour 18-26)\n- Build synthetic_gen.py:\n- Takes TemplateSchema from Step 4\n- Sends to GPT-4o with Structured Outputs mode\n- response_format enforces SyntheticPayload schema\n- System prompt includes industry-specific constraints from schema\n- Temperature: 0.3\n- Chain: Generate   Validate   If validation fails, send failure\ndetails back to GPT-4o with instruction to regenerate specific\nline items   Re-validate   Max 3 loops\n- TEST: Generate synthetic data for each template type. Verify\nthe Validation Agent passes on first or second attempt.\n\nSTEP 6   Orchestrator (Hour 26-32)\n- Build orchestrator.py:\n- Receives uploaded .xlsx via FastAPI endpoint\n- Executes pipeline: Parse   Schema Extract   Generate   Validate   Write\n- WebSocket connection to frontend for real-time progress updates\n- Sends structured events: {\"phase\": \"schema\", \"detail\": \"Mapping Income Statement...\"}\n- Error handling: timeout after 60 seconds, graceful degradation\n- Build main.py:\n- POST /api/upload   receives .xlsx, returns job_id\n- WS /ws/{job_id}   streams progress events to frontend\n- GET /api/download/{job_id}   returns populated .xlsx\n\nSTEP 7   Frontend (Hour 32-48)\n- Build React components in order:\n1. UploadZone.jsx   drag-and-drop with sample template buttons\n2. SchemaTerminal.jsx   terminal-style feed consuming WS events\n3. DataWaterfall.jsx   grid visualization with cell-by-cell animation\n4. VerdictBadge.jsx   full-screen validation summary\n5. AuditTrail.jsx   expandable JSON inspector for the CTO\n- useWebSocket.js hook manages the WS connection and event routing\n- Tailwind config matches Tracelight's dark UI aesthetic\n\nSTEP 8   Integration & Polish (Hour 48-60)\n- End-to-end testing with all three template types\n- Error state handling (corrupt files, empty files, files with data)\n- Loading states and animations\n- Mobile responsiveness (prospects may demo on tablets)\n- Cost tracking: log API costs per generation for the demo",
      "metadata": {
        "source_type": "repository",
        "repository_project_id": "e83393b7-1ee7-4b81-b0a0-fffc1b7afa1b",
        "file_path": "Kaide-LABS/tracelight-safe-harbor/PRD.md",
        "score": 0.6659189
      }
    },
    {
      "content": "Kaide-LABS/tracelight-safe-harbor/ADJACENT_IDEAS.md\n\n### **Technical Pipeline**  \n**DATA IN:**\n2-5 completed .xlsx financial models of the same target company, each\nbuilt by a different analyst (potentially using different template\nstructures, different sheet naming, different row ordering). Optionally,\na \"target entity identifier\" (company name, ticker, or CIK) to help\nthe system confirm all models refer to the same entity.\n**AGENT ROUTING:**\nAgent 1: Model Normalization Agent (Gemini 2.0 Flash   Google Vertex AI)\n   For each uploaded model:\n     Parses the full workbook structure (openpyxl)\n     Identifies the model type (LBO, DCF, 3-Statement, Merger)\n     Maps every input assumption to a canonical taxonomy:\n    e.g.,  Rev Growth Y1  /  Revenue CAGR 2025  /  Top-line\n    growth rate  all map to   REVENUE\\_GROWTH\\_RATE\\_FY2025\n     Extracts all key assumptions into a standardized JSON:\n    {  analyst :  Analyst\\_A ,\n     assumptions : {\n     REVENUE\\_GROWTH\\_RATE\\_FY2025 : 0.12,\n     ENTRY\\_MULTIPLE\\_EV\\_EBITDA : 4.2,\n     EXIT\\_MULTIPLE\\_EV\\_EBITDA : 5.0,\n     SENIOR\\_DEBT\\_RATE : 0.065,\n     \n    },\n     outputs : {\n     IRR : 0.234,\n     MOIC : 2.8,\n     EQUITY\\_VALUE : 485000000\n    }\n    }\n     Handles structural differences: Analyst A might have\n  revenue on Sheet 1 Row 15; Analyst B on Sheet 3 Row 42\\.\n  The agent resolves this semantically, not positionally.\n \n  WHY GEMINI: Semantic comprehension across diverse structures.\n  Long context handles full multi-sheet workbooks. Fast.\n \nAgent 2: Divergence Detection Engine (Python   No LLM)\n   Receives normalized assumption JSONs from all analysts\n   For each canonical assumption key:\n     Calculates: mean, median, std deviation, min, max, range\n     Flags HIGH DIVERGENCE assumptions where the coefficient\n    of variation exceeds a configurable threshold (default: 15%)\n     Ranks all assumptions by divergence magnitude\n     Identifies the single assumption with the highest\n  sensitivity to the output IRR (via a finite-difference\n  approximation: perturb each assumption  1%, measure IRR\n  delta, rank by absolute sensitivity)\n \n  WHY PURE PYTHON: Statistical calculations must be exact.\n  No LLM stochasticity in the divergence math.\n \nAgent 3: Consensus Narrative Agent (GPT-4o   OpenAI API)\n   Receives the ranked divergence report \\+ sensitivity analysis\n   Generates a structured Investment Committee briefing:\n      TOP 5 ASSUMPTION DIVERGENCES    ranked list with each\n    analyst s value, the consensus range, and a plain-English\n    explanation of why this divergence matters\n      HIGHEST-SENSITIVITY VARIABLE    the single assumption\n    that most affects the deal s IRR, with a recommendation\n    for which analyst s estimate to interrogate first\n      CONSENSUS OUTPUT RANGE    the IRR/MOIC range implied",
      "metadata": {
        "source_type": "repository",
        "repository_project_id": "e83393b7-1ee7-4b81-b0a0-fffc1b7afa1b",
        "file_path": "Kaide-LABS/tracelight-safe-harbor/ADJACENT_IDEAS.md",
        "score": 0.6634993
      }
    },
    {
      "content": "Kaide-LABS/tracelight-safe-harbor/PHASE_1_SPEC.md\n\n### Functions  \n#### `parse_template(file_path: str) -> dict`  \n**Input:** Path to uploaded `.xlsx` on disk.  \n**Logic:**\n1. `wb = openpyxl.load_workbook(file_path, data_only=False)`   preserves formulas.\n2. For each `ws` in `wb.worksheets`:\n- Read row 1 as headers (skip empty columns).\n- For each column with a header:\n- Scan cells in rows 2..N.\n- If `cell.value` is `None` or empty string   `is_input = True`.\n- If `cell.value` is a string starting with `=`   `is_input = False` (formula cell).\n- Collect all `cell_references` for input cells (e.g. `\"B5\"` from `cell.coordinate`).\n- Detect temporal headers by regex: match `FY\\d{4}`, `CY\\d{4}`, `\\d{4}E`, `\\d{4}A`, or pure year integers.\n3. Extract named ranges via `wb.defined_names.definedName`   iterate the `DefinedNameList`, call `.attr_text` to get the sheet/cell references.\n4. Detect inter-sheet references:\n- For every formula cell, parse the string for patterns like `'Sheet Name'!CellRef` or `SheetName!CellRef`.\n- Use regex: `r\"'?([^'!]+)'?!([A-Z]+\\d+)\"`.\n- Build a list of `{\"source_sheet\": current_sheet, \"source_cell\": cell_ref, \"target_sheet\": matched_sheet, \"target_cell\": matched_cell}`.\n5. Detect if file contains data in input cells (non-empty, non-formula). If more than 5% of input cells have values, raise `TemplateNotEmptyError`.  \n**Output:** A `dict` matching the shape needed by the Schema Extraction Agent:\n```python\n{\n\"file_name\": str,\n\"sheets\": [\n{\n\"name\": str,\n\"headers\": [{\"column_letter\": str, \"header\": str, \"row\": int}],\n\"input_cells\": [{\"ref\": str, \"column_header\": str}],\n\"formula_cells\": [{\"ref\": str, \"formula\": str, \"column_header\": str}],\n\"temporal_headers\": [str],  # detected year/period values\n}\n],\n\"named_ranges\": [{\"name\": str, \"sheet\": str, \"cell_range\": str}],\n\"inter_sheet_refs\": [{\"source_sheet\": str, \"source_cell\": str, \"target_sheet\": str, \"target_cell\": str}],\n\"total_input_cells\": int\n}\n```  \n**Error Handling:**\n- `openpyxl.utils.exceptions.InvalidFileException`   raise `InvalidTemplateError(\"Corrupt or unsupported Excel file\")`.\n- File size > `settings.max_file_size_mb`   raise `FileTooLargeError`.  \n---",
      "metadata": {
        "source_type": "repository",
        "repository_project_id": "e83393b7-1ee7-4b81-b0a0-fffc1b7afa1b",
        "file_path": "Kaide-LABS/tracelight-safe-harbor/PHASE_1_SPEC.md",
        "score": 0.66290784
      }
    }
  ],
  "meta": {
    "search_mode": "unified",
    "include_sources": true,
    "fast_mode": true,
    "resolved_repositories": [
      "Kaide-LABS/tracelight-safe-harbor"
    ],
    "resolved_data_sources": []
  },
  "repository_result": {
    "results": [
      {
        "repository": "e83393b7-1ee7-4b81-b0a0-fffc1b7afa1b",
        "file": "Kaide-LABS/tracelight-safe-harbor/safe-harbor/backend/agents/validator.py",
        "content": "Kaide-LABS/tracelight-safe-harbor/safe-harbor/backend/agents/validator.py\nCalls: PlugAdjustment, ValidationRuleResult, _get_val, abs, append\nControl flow: 12 branches, 8 loops, complexity 27\n\ndef _rule_balance_sheet_identity(self, payload: SyntheticPayload) -> list[ValidationRuleResult]:\n        results = []\n        for period in self.lookup.keys():\n            assets = self._get_val(period, [\"total assets\"])\n            liab = self._get_val(period, [\"total liabilities\"])\n            eq = self._get_val(period, [\"total equity\"])\n            \n            if assets and liab and eq:\n                a_val = float(assets.value)\n                l_val = float(liab.value)\n                e_val = float(eq.value)\n                \n                delta = a_val - (l_val + e_val)\n                passed = abs(delta) < 0.01\n                \n                adj = None\n                if not passed:\n                    cash_cell = self._get_val(period, [\"cash\"])\n                    if cash_cell:\n                        orig = float(cash_cell.value)\n                        adj_val = orig + delta\n                        adj = PlugAdjustment(\n                            target_cell=cash_cell.header,\n                            target_sheet=cash_cell.sheet_name,\n                            period=period,\n                            original_value=orig,\n                            adjusted_value=adj_val,\n                            delta=delta,\n                            reason=f\"BS imbalance: Assets - (Liab + Eq) = {delta:+,.0f}\"\n                        )\n                        self.adjustments.append(adj)\n                    else:\n                        # Fallback if no cash cell found\n                        self.needs_regeneration.append(\"Cash / Total Assets\")\n                        \n                results.append(ValidationRuleResult(\n                    rule_name=\"balance_sheet_identity\",\n                    period=period,\n                    passed=passed,\n                    expected=l_val + e_val,\n                    actual=a_val,\n                    delta=delta,\n                    adjustment_applied=adj\n                ))\n        return results\n\n    def _rule_margin_bounds(self, payload: SyntheticPayload) -> list[ValidationRuleResult]:\n        results = []\n        for period in self.lookup.keys():\n            rev = self._get_val(period, [\"revenue\", \"sales\"])\n            ebitda = self._get_val(period, [\"ebitda\"])\n            \n            if rev and ebitda and float(rev.value) != 0:\n                r_val = float(rev.value)\n                e_val = float(ebitda.value)\n                margin = e_val / r_val\n                \n                passed = -0.5 <= margin <= 0.8\n                if not passed:\n                    self.needs_regeneration.append(ebitda.header)\n                    \n                results.append(ValidationRuleResult(\n                    rule_name=\"ebitda_margin_bounds\",\n                    period=period,\n                    passed=passed,\n                    expected=0.15,\n                    actual=margin,\n                    delta=margin - 0.15\n                ))\n        return results\n\n    def _apply_plug_adjustments(self, payload: SyntheticPayload, adjustments: list[PlugAdjustment]) -> SyntheticPayload:\n        new_payload = copy.deepcopy(payload)\n        for adj in adjustments:\n            for cell in new_payload.cells:\n                if cell.period == adj.period and cell.header == adj.target_cell and cell.sheet_name == adj.target_sheet:\n                    cell.value = adj.adjusted_value\n        return new_payload",
        "score": 0.68437004
      },
      {
        "repository": "e83393b7-1ee7-4b81-b0a0-fffc1b7afa1b",
        "file": "Kaide-LABS/tracelight-safe-harbor/PRD.md",
        "content": "Kaide-LABS/tracelight-safe-harbor/PRD.md\n\n```\n[SCAN] Detecting sheets... 4 found\n[MAP]  Income Statement   23 columns mapped\n[MAP]  Balance Sheet   31 columns mapped\n[MAP]  Cash Flow   18 columns mapped\n[MAP]  Debt Schedule   12 columns mapped\n[LINK] P&L.Net_Income   CF.Net_Income  \n[LINK] CF.Ending_Cash   BS.Cash  \n[TYPE] Model classified as: Leveraged Buyout\n[DONE] Schema extraction complete. 84 input cells identified.\n```\n- Animated DAG visualization: Nodes for each sheet, edges for\ninter-sheet references, pulsing as they're discovered.\n- Duration: ~5-8 seconds.\n\n### Screen 3: Data Generation (The \"Waterfall\" Phase)\n- Full-width Excel-like grid view.\n- Numbers cascade into cells row by row, sheet by sheet.\n- Each cell briefly flashes AMBER as it's written, then GREEN as the\nValidation Agent confirms it.\n- Bottom ticker: \"Generating 5-year historicals for Healthcare SaaS...\"\n- Real-time validation badges appearing as constraints pass:\n```\n  Balance Sheet Balanced (Year 1)\n  Balance Sheet Balanced (Year 2)\n  Cash Flow Reconciled (Year 1)\n  Debt Schedule Verified\n...\n```\n- If a plug adjustment occurs, show it transparently:\n```\n  Adjusted Cash by +$142K to force BS equilibrium (Year 3)\n```\nThis BUILDS trust. It shows the system is honest about corrections,\nnot hiding them.\n- Duration: ~15-25 seconds.\n\n### Screen 4: The Verdict (The \"Magic Moment\")\n- Full-screen modal with large badge:\n```\n                                        \n   SYNTHETIC MODEL VERIFIED  \n   Balance Sheet Balanced (all 5 years)\n   Cash Flow Reconciled (all 5 years)\n   Debt Schedule Amortized Correctly\n   Margins Within Industry Bounds\n   Zero Sensitive Data  \nModel Type:    Leveraged Buyout\nIndustry:      Healthcare SaaS\nTime Horizon:  FY2020   FY2030\nInput Cells:   84 populated\nValidation:    6/6 rules passed  \n[Download .xlsx]     [  START TESTING IN TRACELIGHT]\n                                        \n```\n- The \"START TESTING\" button is the primary CTA. It loads the populated\nmodel directly into Tracelight's core Excel add-in environment.\n- The prospect is now using Tracelight's real product with a model\nthat feels real but triggers zero InfoSec concerns.\n\n### Screen 5: Audit Trail (For the CTO)\n- Expandable panel showing:\n- Full JSON schema extracted in Step 3\n- Every synthetic value generated with its constraint bounds\n- Every validation rule result\n- Every plug adjustment with the exact delta\n- Timestamps for each agent's execution\n- Model/token usage breakdown\n- This is built specifically for Aleksander. He will click this.\nIf it's not there, he won't trust the system.\n\n---\n\n## 4. PHASE 1 EXECUTION SPEC",
        "score": 0.6688491
      },
      {
        "repository": "e83393b7-1ee7-4b81-b0a0-fffc1b7afa1b",
        "file": "Kaide-LABS/tracelight-safe-harbor/PRD.md",
        "content": "Kaide-LABS/tracelight-safe-harbor/PRD.md\n\nSTEP 3   Deterministic Validation Agent (Hour 6-12)\n- Build validator.py as a pure Python class:\n- Method: validate(payload: SyntheticPayload)   ValidationResult\n- Implement all 6 hardcoded rules (see architecture above)\n- Implement plug-account adjustment logic\n- Implement retry signal (returns which line items need regeneration)\n- TEST: Feed it deliberately broken data (BS doesn't balance,\nnegative margins, depreciation > CapEx). Verify it catches every\nviolation and produces correct plug adjustments.\n- This is the trust anchor. It must be bulletproof before proceeding.\n\nSTEP 4   Schema Extraction Agent (Hour 12-18)\n- Build schema_extractor.py:\n- Takes parsed Excel JSON from parser.py\n- Sends to Gemini 2.0 Flash via Vertex AI\n- System prompt: \"You are a financial model analyst. Given the\nfollowing Excel template structure, classify each column by its\nfinancial data type, identify temporal ranges, detect inter-sheet\ndependencies, and classify the model type. Output strict JSON\nconforming to the TemplateSchema.\"\n- Parse response into TemplateSchema Pydantic model\n- Fallback: If Gemini fails or returns malformed JSON, retry 2x.\nIf still failing, fall back to GPT-4o for schema extraction.\n- TEST: Run against LBO, DCF, and 3-Statement templates. Verify\ncorrect classification of every column.\n\nSTEP 5   Synthetic Generation Agent (Hour 18-26)\n- Build synthetic_gen.py:\n- Takes TemplateSchema from Step 4\n- Sends to GPT-4o with Structured Outputs mode\n- response_format enforces SyntheticPayload schema\n- System prompt includes industry-specific constraints from schema\n- Temperature: 0.3\n- Chain: Generate   Validate   If validation fails, send failure\ndetails back to GPT-4o with instruction to regenerate specific\nline items   Re-validate   Max 3 loops\n- TEST: Generate synthetic data for each template type. Verify\nthe Validation Agent passes on first or second attempt.\n\nSTEP 6   Orchestrator (Hour 26-32)\n- Build orchestrator.py:\n- Receives uploaded .xlsx via FastAPI endpoint\n- Executes pipeline: Parse   Schema Extract   Generate   Validate   Write\n- WebSocket connection to frontend for real-time progress updates\n- Sends structured events: {\"phase\": \"schema\", \"detail\": \"Mapping Income Statement...\"}\n- Error handling: timeout after 60 seconds, graceful degradation\n- Build main.py:\n- POST /api/upload   receives .xlsx, returns job_id\n- WS /ws/{job_id}   streams progress events to frontend\n- GET /api/download/{job_id}   returns populated .xlsx\n\nSTEP 7   Frontend (Hour 32-48)\n- Build React components in order:\n1. UploadZone.jsx   drag-and-drop with sample template buttons\n2. SchemaTerminal.jsx   terminal-style feed consuming WS events\n3. DataWaterfall.jsx   grid visualization with cell-by-cell animation\n4. VerdictBadge.jsx   full-screen validation summary\n5. AuditTrail.jsx   expandable JSON inspector for the CTO\n- useWebSocket.js hook manages the WS connection and event routing\n- Tailwind config matches Tracelight's dark UI aesthetic\n\nSTEP 8   Integration & Polish (Hour 48-60)\n- End-to-end testing with all three template types\n- Error state handling (corrupt files, empty files, files with data)\n- Loading states and animations\n- Mobile responsiveness (prospects may demo on tablets)\n- Cost tracking: log API costs per generation for the demo",
        "score": 0.6659189
      },
      {
        "repository": "e83393b7-1ee7-4b81-b0a0-fffc1b7afa1b",
        "file": "Kaide-LABS/tracelight-safe-harbor/ADJACENT_IDEAS.md",
        "content": "Kaide-LABS/tracelight-safe-harbor/ADJACENT_IDEAS.md\n\n### **Technical Pipeline**  \n**DATA IN:**\n2-5 completed .xlsx financial models of the same target company, each\nbuilt by a different analyst (potentially using different template\nstructures, different sheet naming, different row ordering). Optionally,\na \"target entity identifier\" (company name, ticker, or CIK) to help\nthe system confirm all models refer to the same entity.\n**AGENT ROUTING:**\nAgent 1: Model Normalization Agent (Gemini 2.0 Flash   Google Vertex AI)\n   For each uploaded model:\n     Parses the full workbook structure (openpyxl)\n     Identifies the model type (LBO, DCF, 3-Statement, Merger)\n     Maps every input assumption to a canonical taxonomy:\n    e.g.,  Rev Growth Y1  /  Revenue CAGR 2025  /  Top-line\n    growth rate  all map to   REVENUE\\_GROWTH\\_RATE\\_FY2025\n     Extracts all key assumptions into a standardized JSON:\n    {  analyst :  Analyst\\_A ,\n     assumptions : {\n     REVENUE\\_GROWTH\\_RATE\\_FY2025 : 0.12,\n     ENTRY\\_MULTIPLE\\_EV\\_EBITDA : 4.2,\n     EXIT\\_MULTIPLE\\_EV\\_EBITDA : 5.0,\n     SENIOR\\_DEBT\\_RATE : 0.065,\n     \n    },\n     outputs : {\n     IRR : 0.234,\n     MOIC : 2.8,\n     EQUITY\\_VALUE : 485000000\n    }\n    }\n     Handles structural differences: Analyst A might have\n  revenue on Sheet 1 Row 15; Analyst B on Sheet 3 Row 42\\.\n  The agent resolves this semantically, not positionally.\n \n  WHY GEMINI: Semantic comprehension across diverse structures.\n  Long context handles full multi-sheet workbooks. Fast.\n \nAgent 2: Divergence Detection Engine (Python   No LLM)\n   Receives normalized assumption JSONs from all analysts\n   For each canonical assumption key:\n     Calculates: mean, median, std deviation, min, max, range\n     Flags HIGH DIVERGENCE assumptions where the coefficient\n    of variation exceeds a configurable threshold (default: 15%)\n     Ranks all assumptions by divergence magnitude\n     Identifies the single assumption with the highest\n  sensitivity to the output IRR (via a finite-difference\n  approximation: perturb each assumption  1%, measure IRR\n  delta, rank by absolute sensitivity)\n \n  WHY PURE PYTHON: Statistical calculations must be exact.\n  No LLM stochasticity in the divergence math.\n \nAgent 3: Consensus Narrative Agent (GPT-4o   OpenAI API)\n   Receives the ranked divergence report \\+ sensitivity analysis\n   Generates a structured Investment Committee briefing:\n      TOP 5 ASSUMPTION DIVERGENCES    ranked list with each\n    analyst s value, the consensus range, and a plain-English\n    explanation of why this divergence matters\n      HIGHEST-SENSITIVITY VARIABLE    the single assumption\n    that most affects the deal s IRR, with a recommendation\n    for which analyst s estimate to interrogate first\n      CONSENSUS OUTPUT RANGE    the IRR/MOIC range implied",
        "score": 0.6634993
      },
      {
        "repository": "e83393b7-1ee7-4b81-b0a0-fffc1b7afa1b",
        "file": "Kaide-LABS/tracelight-safe-harbor/PHASE_1_SPEC.md",
        "content": "Kaide-LABS/tracelight-safe-harbor/PHASE_1_SPEC.md\n\n### Functions  \n#### `parse_template(file_path: str) -> dict`  \n**Input:** Path to uploaded `.xlsx` on disk.  \n**Logic:**\n1. `wb = openpyxl.load_workbook(file_path, data_only=False)`   preserves formulas.\n2. For each `ws` in `wb.worksheets`:\n- Read row 1 as headers (skip empty columns).\n- For each column with a header:\n- Scan cells in rows 2..N.\n- If `cell.value` is `None` or empty string   `is_input = True`.\n- If `cell.value` is a string starting with `=`   `is_input = False` (formula cell).\n- Collect all `cell_references` for input cells (e.g. `\"B5\"` from `cell.coordinate`).\n- Detect temporal headers by regex: match `FY\\d{4}`, `CY\\d{4}`, `\\d{4}E`, `\\d{4}A`, or pure year integers.\n3. Extract named ranges via `wb.defined_names.definedName`   iterate the `DefinedNameList`, call `.attr_text` to get the sheet/cell references.\n4. Detect inter-sheet references:\n- For every formula cell, parse the string for patterns like `'Sheet Name'!CellRef` or `SheetName!CellRef`.\n- Use regex: `r\"'?([^'!]+)'?!([A-Z]+\\d+)\"`.\n- Build a list of `{\"source_sheet\": current_sheet, \"source_cell\": cell_ref, \"target_sheet\": matched_sheet, \"target_cell\": matched_cell}`.\n5. Detect if file contains data in input cells (non-empty, non-formula). If more than 5% of input cells have values, raise `TemplateNotEmptyError`.  \n**Output:** A `dict` matching the shape needed by the Schema Extraction Agent:\n```python\n{\n\"file_name\": str,\n\"sheets\": [\n{\n\"name\": str,\n\"headers\": [{\"column_letter\": str, \"header\": str, \"row\": int}],\n\"input_cells\": [{\"ref\": str, \"column_header\": str}],\n\"formula_cells\": [{\"ref\": str, \"formula\": str, \"column_header\": str}],\n\"temporal_headers\": [str],  # detected year/period values\n}\n],\n\"named_ranges\": [{\"name\": str, \"sheet\": str, \"cell_range\": str}],\n\"inter_sheet_refs\": [{\"source_sheet\": str, \"source_cell\": str, \"target_sheet\": str, \"target_cell\": str}],\n\"total_input_cells\": int\n}\n```  \n**Error Handling:**\n- `openpyxl.utils.exceptions.InvalidFileException`   raise `InvalidTemplateError(\"Corrupt or unsupported Excel file\")`.\n- File size > `settings.max_file_size_mb`   raise `FileTooLargeError`.  \n---",
        "score": 0.66290784
      }
    ],
    "total_results": 5,
    "repositories_searched": 1
  },
  "documentation_result": null
}

17. [Source 16] read_source_content({"source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/scripts/verify_templates.py"}): {
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/scripts/verify_templates.py",
  "content": "\"\"\"Verify generated templates are structurally correct.\"\"\"\nimport openpyxl\nimport sys\n\ndef verify_lbo():\n    wb = openpyxl.load_workbook(\"../templates/lbo_template.xlsx\", data_only=False)\n    assert len(wb.sheetnames) == 5, f\"Expected 5 sheets, got {len(wb.sheetnames)}\"\n    assert \"Income Statement\" in wb.sheetnames\n    assert \"Debt Schedule\" in wb.sheetnames\n    assert \"Returns Analysis\" in wb.sheetnames\n\n    # Check IS Interest Expense references DS row 16\n    ws = wb[\"Income Statement\"]\n    ie_cell = ws.cell(row=9, column=2)  # Interest Expense, FY2020\n    assert ie_cell.value and \"Debt Schedule\" in str(ie_cell.value), f\"IS Interest Expense formula wrong: {ie_cell.value}\"\n    assert \"16\" in str(ie_cell.value), f\"Should reference row 16, got: {ie_cell.value}\"\n\n    # Count input cells (empty non-formula cells)\n    input_count = 0\n    for ws in wb.worksheets:\n        for row in ws.iter_rows(min_row=2, values_only=False):\n            for cell in row[1:]:  # skip label column\n                if cell.value is None or (isinstance(cell.value, (int, float)) and cell.value == 0):\n                    input_count += 1\n    assert input_count > 30, f\"Expected > 30 input cells, got {input_count}\"\n    print(f\"LBO template: OK ({len(wb.sheetnames)} sheets, {input_count} input cells)\")\n\ndef verify_three_statement():\n    wb = openpyxl.load_workbook(\"../templates/three_statement_template.xlsx\", data_only=False)\n    assert len(wb.sheetnames) == 3, f\"Expected 3 sheets, got {len(wb.sheetnames)}\"\n    assert \"Debt Schedule\" not in wb.sheetnames\n    assert \"Returns Analysis\" not in wb.sheetnames\n    print(f\"3-Statement template: OK ({len(wb.sheetnames)} sheets)\")\n\ndef verify_dcf():\n    wb = openpyxl.load_workbook(\"../templates/dcf_template.xlsx\", data_only=False)\n    assert len(wb.sheetnames) == 4, f\"Expected 4 sheets, got {len(wb.sheetnames)}\"\n    assert \"Revenue Build\" in wb.sheetnames\n    assert \"DCF Valuation\" in wb.sheetnames\n    print(f\"DCF template: OK ({len(wb.sheetnames)} sheets)\")\n\nif __name__ == \"__main__\":\n    verify_lbo()\n    verify_three_statement()\n    verify_dcf()\n    print(\"\\nAll templates verified successfully.\")\n",
  "language": "python",
  "truncated": false,
  "original_size": 2146
}

18. [Source 17] read_source_content({"source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/agents/synthetic_gen.py"}): {
  "source": "Kaide-LABS/tracelight-safe-harbor:safe-harbor/backend/agents/synthetic_gen.py",
  "content": "import time\nimport json\nimport asyncio\nimport functools\nimport logging\nfrom google import genai\nfrom google.genai import types\nfrom backend.models.schemas import TemplateSchema, SyntheticPayload, GenerationMetadata, TokenUsage, CellValue\nfrom backend.config import Settings\n\nlogger = logging.getLogger(__name__)\n\n# Smaller chunks = LLM never skips. 25 cells \u00d7 ~5 tokens each = tiny output.\nMAX_CELLS_PER_CHUNK = 25\n\nFINANCIAL_CONTEXT = \"\"\"FINANCIAL PARAMETERS:\n- Base revenue: $150M-$500M with 8-12% annual growth\n- COGS: 50-65% of revenue\n- SG&A: 10-20% of revenue\n- R&D: 3-8% of revenue\n- D&A: 3-6% of revenue\n- Effective tax rate: 21-28% (as decimal, e.g. 0.25)\n- EBITDA margins: 15-35%\n- Senior debt interest rate: 5-8% (as decimal, e.g. 0.065)\n- Mezzanine/PIK interest rate: 8-14% (as decimal, e.g. 0.10)\n- Senior debt beginning balance: $200M-$500M, repaying 5-15% annually\n- Mezzanine beginning balance: $50M-$150M\n- CapEx: $10M-$30M annually\n- Working capital changes: negative 2-5% of revenue change\n- Cash beginning of period: $20M-$50M\n- Entry EV/EBITDA multiple: 8x-12x\n- Exit EV/EBITDA multiple: 8x-12x\n- Investment horizon: 5 years\n\nRULES:\n- Revenue should grow steadily. Costs should scale proportionally.\n- Percentages/rates as DECIMALS (25% = 0.25, NOT 25)\n- Currency values as whole numbers (no decimals for large amounts)\n- Generate REALISTIC values \u2014 no zeros, no ones, no placeholder values\n- EVERY key must have a value. Do NOT skip any.\"\"\"\n\n\nasync def _llm_generate_values(client, model: str, prompt: str) -> tuple[dict, int]:\n    \"\"\"Call Gemini and return a parsed dict of {key: value} + token count.\"\"\"\n    response = await asyncio.to_thread(\n        functools.partial(\n            client.models.generate_content,\n            model=model,\n            contents=prompt,\n            config=types.GenerateContentConfig(\n                temperature=1.0,\n                max_output_tokens=8192,\n                thinking_config=types.ThinkingConfig(thinking_budget=512),\n                response_mime_type=\"application/json\",\n            ),\n        )\n    )\n    raw_text = response.text\n    if raw_text.startswith(\"```json\"):\n        raw_text = raw_text[7:]\n    if raw_text.endswith(\"```\"):\n        raw_text = raw_text[:-3]\n    parsed = json.loads(raw_text)\n    # Normalize: if it returned a list, convert to dict by index\n    if isinstance(parsed, list):\n        parsed = {str(i + 1): v for i, v in enumerate(parsed)}\n    # If nested (e.g. {\"values\": {...}}), unwrap\n    if len(parsed) == 1 and isinstance(list(parsed.values())[0], dict):\n        parsed = list(parsed.values())[0]\n    usage_meta = getattr(response, 'usage_metadata', None)\n    tokens = getattr(usage_meta, 'candidates_token_count', 0) if usage_meta else 0\n    return parsed, tokens\n\n\ndef _build_cell_grid(cells: list) -> str:\n    \"\"\"Build a numbered grid: 1. B4 Revenue [FY2020] (currency)\"\"\"\n    lines = []\n    for i, c in enumerate(cells, 1):\n        header = c[\"header\"]\n        period = c.get(\"period\", \"\")\n        cell_ref = c[\"cell_ref\"]\n        # Infer type hint from header\n        h_lower = header.lower()\n        if any(k in h_lower for k in [\"rate\", \"margin\", \"%\", \"yield\", \"irr\"]):\n            hint = \"decimal 0-1\"\n        elif any(k in h_lower for k in [\"multiple\", \"moic\", \"ev/\"]):\n            hint = \"ratio e.g. 10.5\"\n        elif any(k in h_lower for k in [\"year\", \"horizon\"]):\n            hint = \"integer e.g. 2020 or 5\"\n        else:\n            hint = \"currency integer\"\n        lines.append(f'{i}. [{cell_ref}] {header} | {period} | {hint}')\n    return \"\\n\".join(lines)\n\n\nasync def _generate_chunk(client, model: str, schema: TemplateSchema, sheet_name: str,\n                          cells: list, prior_sheets: dict, chunk_label: str = \"\") -> tuple[list, int]:\n    \"\"\"Generate values for a chunk. LLM returns {\"1\": value, \"2\": value, ...}. Python maps back to cells.\"\"\"\n    cell_count = len(cells)\n    grid = _build_cell_grid(cells)\n\n    prompt = f\"\"\"Generate {cell_count} realistic values for a {schema.model_type} financial model ({schema.industry}, {schema.currency}).\nSheet: \"{sheet_name}\"\n\n{FINANCIAL_CONTEXT}\n\n{\"PRIOR VALUES (for cross-sheet consistency):\" + chr(10) + json.dumps(prior_sheets, indent=2) if prior_sheets else \"\"}\n\nReturn a JSON object with keys \"1\" through \"{cell_count}\", each mapping to a numeric value.\nExample: {{\"1\": 300000000, \"2\": 330000000, \"3\": 0.55}}\n\nCELLS (generate a value for ALL {cell_count}):\n{grid}\"\"\"\n\n    values_dict, tokens = await _llm_generate_values(client, model, prompt)\n    total_tokens = tokens\n\n    # Map values back to cells deterministically\n    result = []\n    missing_indices = []\n    for i, cell in enumerate(cells, 1):\n        key = str(i)\n        if key in values_dict:\n            val = values_dict[key]\n            # Handle nested objects (LLM sometimes returns {\"1\": {\"value\": 300}})\n            if isinstance(val, dict):\n                val = val.get(\"value\", val.get(\"v\", 0))\n            result.append({\n                \"sheet_name\": cell[\"sheet_name\"],\n                \"cell_ref\": cell[\"cell_ref\"],\n                \"header\": cell[\"header\"],\n                \"period\": cell.get(\"period\", \"\"),\n                \"value\": val,\n            })\n        else:\n            missing_indices.append(i)\n\n    # Backfill any missing keys\n    if missing_indices:\n        logger.info(f\"  {sheet_name}{chunk_label}: backfilling {len(missing_indices)} missing values\")\n        missing_cells = [cells[i - 1] for i in missing_indices]\n        missing_grid = _build_cell_grid(missing_cells)\n\n        backfill_prompt = f\"\"\"Generate {len(missing_cells)} values for a {schema.model_type} model. Sheet: \"{sheet_name}\".\n\n{FINANCIAL_CONTEXT}\n\nReturn JSON: {{\"1\": value, \"2\": value, ...}}\n\nCELLS:\n{missing_grid}\"\"\"\n\n        backfill_dict, bf_tokens = await _llm_generate_values(client, model, backfill_prompt)\n        total_tokens += bf_tokens\n\n        for j, cell in enumerate(missing_cells, 1):\n            val = backfill_dict.get(str(j), 0)\n            if isinstance(val, dict):\n                val = val.get(\"value\", val.get(\"v\", 0))\n            result.append({\n                \"sheet_name\": cell[\"sheet_name\"],\n                \"cell_ref\": cell[\"cell_ref\"],\n                \"header\": cell[\"header\"],\n                \"period\": cell.get(\"period\", \"\"),\n                \"value\": val,\n            })\n\n    logger.info(f\"  {sheet_name}{chunk_label}: {len(result)}/{cell_count} cells\")\n    return result, total_tokens\n\n\ndef _split_chunks(cells: list, max_size: int = MAX_CELLS_PER_CHUNK) -> list[list]:\n    return [cells[i:i + max_size] for i in range(0, len(cells), max_size)]\n\n\ndef _extract_cross_sheet_values(cells: list) -> dict:\n    \"\"\"Extract key financial values for cross-sheet consistency.\"\"\"\n    context = {}\n    keywords = [\n        \"revenue\", \"net income\", \"ebitda\", \"total assets\", \"total liabilities\",\n        \"total equity\", \"beginning balance\", \"ending balance\", \"d&a\",\n        \"depreciation\", \"capex\", \"interest\", \"cash\", \"debt\"\n    ]\n    for cell in cells:\n        header = cell.get(\"header\", \"\").lower()\n        if any(kw in header for kw in keywords):\n            key = f\"{cell.get('header', '')}|{cell.get('period', '')}\"\n            context[key] = cell.get(\"value\")\n    return context\n\n\nasync def _generate_sheet(client, model: str, schema: TemplateSchema, sheet_name: str,\n                          cells: list, prior_sheets: dict) -> tuple[list, int]:\n    \"\"\"Generate all cells for a sheet, sub-chunking and parallelizing.\"\"\"\n    chunks = _split_chunks(cells)\n    if len(chunks) == 1:\n        return await _generate_chunk(client, model, schema, sheet_name, cells, prior_sheets)\n\n    tasks = []\n    for i, chunk in enumerate(chunks):\n        label = f\" [{i+1}/{len(chunks)}]\"\n        tasks.append(_generate_chunk(client, model, schema, sheet_name, chunk, prior_sheets, label))\n\n    results = await asyncio.gather(*tasks)\n    all_cells = []\n    total_tokens = 0\n    for cells_result, tokens in results:\n        all_cells.extend(cells_result)\n        total_tokens += tokens\n    return all_cells, total_tokens\n\n\nasync def generate_synthetic_data(schema: TemplateSchema, settings: Settings,\n                                  retry_instructions: str = None, parsed_template: dict = None) -> SyntheticPayload:\n    client = genai.Client(api_key=settings.gemini_api_key)\n\n    # Group input cells by sheet from parser output\n    sheets_cells = {}\n    if parsed_template:\n        for sheet in parsed_template[\"sheets\"]:\n            cells = []\n            for ic in sheet[\"input_cells\"]:\n                cells.append({\n                    \"sheet_name\": sheet[\"name\"],\n                    \"header\": ic[\"column_header\"],\n                    \"period\": ic.get(\"period\", \"\"),\n                    \"cell_ref\": ic[\"ref\"],\n                })\n            if cells:\n                sheets_cells[sheet[\"name\"]] = cells\n    else:\n        for sheet in schema.sheets:\n            for col in sheet.columns:\n                if col.is_input and col.periods:\n                    for period in col.periods:\n                        idx = col.periods.index(period)\n                        if sheet.name not in sheets_cells:\n                            sheets_cells[sheet.name] = []\n                        sheets_cells[sheet.name].append({\n                            \"sheet_name\": sheet.name,\n                            \"header\": col.header,\n                            \"period\": period,\n                            \"cell_ref\": col.cell_references[idx] if idx < len(col.cell_references) else \"\"\n                        })\n\n    total_cells = sum(len(cells) for cells in sheets_cells.values())\n    logger.info(f\"Generating {total_cells} cells across {len(sheets_cells)} sheets (max {MAX_CELLS_PER_CHUNK}/chunk)\")\n\n    start_time = time.time()\n    all_cells = []\n    total_tokens = 0\n    prior_sheets = {}\n\n    # Phase 1: Income Statement (baseline revenue/costs)\n    # Phase 2: Debt Schedule (needs IS context)\n    # Phase 3: Everything else in parallel\n    phase1 = [\"Income Statement\"]\n    phase2 = [\"Debt Schedule\"]\n    phase3 = [name for name in sheets_cells if name not in phase1 + phase2]\n\n    for phase_sheets in [phase1, phase2]:\n        for sheet_name in phase_sheets:\n            if sheet_name not in sheets_cells:\n                continue\n            cells = sheets_cells[sheet_name]\n            result, tokens = await _generate_sheet(client, settings.gemini_model, schema, sheet_name, cells, prior_sheets)\n            all_cells.extend(result)\n            total_tokens += tokens\n            prior_sheets.update(_extract_cross_sheet_values(result))\n\n    if phase3:\n        tasks = [\n            _generate_sheet(client, settings.gemini_model, schema, sheet_name, sheets_cells[sheet_name], prior_sheets)\n            for sheet_name in phase3\n        ]\n        results = await asyncio.gather(*tasks)\n        for result, tokens in results:\n            all_cells.extend(result)\n            total_tokens += tokens\n\n    generation_time = int((time.time() - start_time) * 1000)\n\n    cell_values = []\n    for c in all_cells:\n        try:\n            cell_values.append(CellValue(\n                sheet_name=c.get(\"sheet_name\", \"\"),\n                cell_ref=c.get(\"cell_ref\", \"\"),\n                header=c.get(\"header\", \"\"),\n                period=c.get(\"period\", \"\"),\n                value=c.get(\"value\", 0),\n            ))\n        except Exception as e:\n            logger.warning(f\"Skipping malformed cell: {c} \u2014 {e}\")\n\n    result = SyntheticPayload(\n        model_type=schema.model_type,\n        industry=schema.industry,\n        currency=schema.currency,\n        cells=cell_values,\n        generation_metadata=GenerationMetadata(\n            model_used=settings.gemini_model,\n            temperature=1.0,\n            token_usage=TokenUsage(\n                prompt_tokens=0,\n                completion_tokens=total_tokens,\n                total_tokens=total_tokens\n            ),\n            generation_time_ms=generation_time\n        )\n    )\n\n    logger.info(f\"Total: {len(result.cells)} cells generated (expected {total_cells}) in {generation_time}ms\")\n    return result\n",
  "language": "python",
  "truncated": false,
  "original_size": 12100
}

19. [Source 18] code_grep({"repository_id": "Kaide-LABS/tracelight-safe-harbor", "pattern": "def create_dcf|DCF Valuation|Free Cash Flow|WACC|Terminal", "path": "safe-harbor/scripts/generate_templates.py", "context_lines": 6, "max_total_matches": 30}): {
  "success": true,
  "matches": {},
  "pattern": "def create_dcf|DCF Valuation|Free Cash Flow|WACC|Terminal",
  "path_filter": "safe-harbor/scripts/generate_templates.py",
  "total_matches": 0,
  "files_searched": 0,
  "files_with_matches": 0,
  "truncated": false,
  "options": {
    "case_sensitive": false,
    "lines_before": 6,
    "lines_after": 6,
    "output_mode": "content",
    "whole_word": false,
    "fixed_string": false,
    "highlight": false,
    "include_line_numbers": true,
    "group_by_file": true
  }
}

20. [Reflection] ## Final Synthesis Before Report

### Complete Data Flow (confirmed through source code):
1. **Parser** → produces `{sheet_name, ref, column_header (section-qualified), period, formula}` with separate `input_cells` and `formula_cells` lists
2. **Synthetic Gen** → only touches `input_cells` from parser, preserves `cell_ref` exactly, generates values via LLM in chunks of 25
3. **Post-Processor** → receives flat cells + parsed_template (BUT IGNORES parsed_template!), builds grids keyed by `(sheet_name, row_number)`, simulates using HARDCODED row numbers that don't match any template
4. **Validator** → uses fuzzy keyword matching on headers (template-agnostic, good design)
5. **Writer** → skips formula cells, writes only to input cells
6. **Google Sheets + Validation Tab** → builds formulas with HARDCODED row references that don't match template

### Critical Bugs Confirmed:

**Bug 1: Sheet Name Mismatch**
- post_processor.py: `CF = "Cash Flow Statement"`
- Actual template: `"Cash Flow"`
- Validation builder: `has_cf = 'Cash Flow Statement' in sheet_names` → always False!
- Result: ALL cash flow processing is silently skipped

**Bug 2: Every Row Number Wrong** (post_processor + validation builder)
- IS Revenue: solver uses row 4, actual is row 2
- BS Cash: solver uses row 5, actual is row 2 
- CF Net Income: solver uses row 5, actual is row 2
- DS Senior Begin: solver uses row 5, actual is row 3
- ...and dozens more (see complete mapping)

**Bug 3: Interest Calculation Method Mismatch**
- Solver: `(begin + end) / 2 × rate` (average balance)
- Template: `begin × rate` (beginning balance)
- This creates a systematic error in interest → NI → CF → Debt circularity

**Bug 4: Formula Cell Overwrite Attempt**
- Solver tries to write: Retained Earnings (BS row 19 - FORMULA), Beginning Cash (CF row 13 - FORMULA)
- Writer silently skips these because they start with `=`
- Result: solver's circular reference resolution is completely discarded

**Bug 5: Validation Div-by-Zero**
- Revenue Growth for FY2020 tries `FY2020/FY2019-1` but FY2019 doesn't exist → #ERROR!

**Bug 6: Avg Growth #NAME? Error**
- Uses `len(rows)` (Python variable) in formula string, creating malformed range reference

**Bug 7: Working Capital Granularity Mismatch**
- Solver simulates 5 separate WC items (AR, Inv, AP, Accrued, DefRev)
- Template has single "Changes in Working Capital" input cell

**Bug 8: parsed_template Parameter Ignored**
- `post_process(cells, parsed_template=None)` receives parsed_template but NEVER uses it
- This is the key architectural gap — all the row mapping data is available but unused

### Design Decisions for Row Map Builder:

1. **Normalization Strategy**: Use a canonical alias dictionary mapping qualified headers to canonical keys. Example:
   - `"Revenue"` → `"revenue"`
   - `"SENIOR SECURED DEBT > Beginning Balance"` → `"senior_begin_bal"` (but actual template uses just "Beginning Balance" under "Senior Debt" section)
   - Need to handle: section prefix + item name → canonical key

2. **Template Type Detection**: Check sheet names:
   - Has "Debt Schedule" + "Returns Analysis" → LBO
   - Has "Revenue Build" + "DCF Valuation" → DCF
   - Has IS + BS + CF only → 3-Statement

3. **Formula vs Input Detection**: Parser already separates these into `input_cells` and `formula_cells` lists

4. **Solver Strategy Per Template**:
   - LBO: Full IS→DS→CF→BS circular reference solver
   - DCF: No debt circularity, simpler (UFCF → Terminal Value → WACC)
   - 3-Statement: Simplified debt handling

### Confidence Level: HIGH — Ready to produce comprehensive report

21. [Source 19] think({"reflection": "## Final Synthesis Before Report\n\n### Complete Data Flow (confirmed through source code):\n1. **Parser** \u2192 produces `{sheet_name, ref, column_header (section-qualified), period, formula}` with separate `input_cells` and `formula_cells` lists\n2. **Synthetic Gen** \u2192 only touches `input_cells` from parser, preserves `cell_ref` exactly, generates values via LLM in chunks of 25\n3. **Post-Processor** \u2192 receives flat cells + parsed_template (BUT IGNORES parsed_template!), builds grids keyed by `(sheet_name, row_number)`, simulates using HARDCODED row numbers that don't match any template\n4. **Validator** \u2192 uses fuzzy keyword matching on headers (template-agnostic, good design)\n5. **Writer** \u2192 skips formula cells, writes only to input cells\n6. **Google Sheets + Validation Tab** \u2192 builds formulas with HARDCODED row references that don't match template\n\n### Critical Bugs Confirmed:\n\n**Bug 1: Sheet Name Mismatch**\n- post_processor.py: `CF = \"Cash Flow Statement\"`\n- Actual template: `\"Cash Flow\"`\n- Validation builder: `has_cf = 'Cash Flow Statement' in sheet_names` \u2192 always False!\n- Result: ALL cash flow processing is silently skipped\n\n**Bug 2: Every Row Number Wrong** (post_processor + validation builder)\n- IS Revenue: solver uses row 4, actual is row 2\n- BS Cash: solver uses row 5, actual is row 2 \n- CF Net Income: solver uses row 5, actual is row 2\n- DS Senior Begin: solver uses row 5, actual is row 3\n- ...and dozens more (see complete mapping)\n\n**Bug 3: Interest Calculation Method Mismatch**\n- Solver: `(begin + end) / 2 \u00d7 rate` (average balance)\n- Template: `begin \u00d7 rate` (beginning balance)\n- This creates a systematic error in interest \u2192 NI \u2192 CF \u2192 Debt circularity\n\n**Bug 4: Formula Cell Overwrite Attempt**\n- Solver tries to write: Retained Earnings (BS row 19 - FORMULA), Beginning Cash (CF row 13 - FORMULA)\n- Writer silently skips these because they start with `=`\n- Result: solver's circular reference resolution is completely discarded\n\n**Bug 5: Validation Div-by-Zero**\n- Revenue Growth for FY2020 tries `FY2020/FY2019-1` but FY2019 doesn't exist \u2192 #ERROR!\n\n**Bug 6: Avg Growth #NAME? Error**\n- Uses `len(rows)` (Python variable) in formula string, creating malformed range reference\n\n**Bug 7: Working Capital Granularity Mismatch**\n- Solver simulates 5 separate WC items (AR, Inv, AP, Accrued, DefRev)\n- Template has single \"Changes in Working Capital\" input cell\n\n**Bug 8: parsed_template Parameter Ignored**\n- `post_process(cells, parsed_template=None)` receives parsed_template but NEVER uses it\n- This is the key architectural gap \u2014 all the row mapping data is available but unused\n\n### Design Decisions for Row Map Builder:\n\n1. **Normalization Strategy**: Use a canonical alias dictionary mapping qualified headers to canonical keys. Example:\n   - `\"Revenue\"` \u2192 `\"revenue\"`\n   - `\"SENIOR SECURED DEBT > Beginning Balance\"` \u2192 `\"senior_begin_bal\"` (but actual template uses just \"Beginning Balance\" under \"Senior Debt\" section)\n   - Need to handle: section prefix + item name \u2192 canonical key\n\n2. **Template Type Detection**: Check sheet names:\n   - Has \"Debt Schedule\" + \"Returns Analysis\" \u2192 LBO\n   - Has \"Revenue Build\" + \"DCF Valuation\" \u2192 DCF\n   - Has IS + BS + CF only \u2192 3-Statement\n\n3. **Formula vs Input Detection**: Parser already separates these into `input_cells` and `formula_cells` lists\n\n4. **Solver Strategy Per Template**:\n   - LBO: Full IS\u2192DS\u2192CF\u2192BS circular reference solver\n   - DCF: No debt circularity, simpler (UFCF \u2192 Terminal Value \u2192 WACC)\n   - 3-Statement: Simplified debt handling\n\n### Confidence Level: HIGH \u2014 Ready to produce comprehensive report"}): Reflection recorded. Continue with next action.
