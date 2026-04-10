"""
Template-driven row map builder.
Converts parser output into a universal lookup that eliminates all hardcoded row numbers.
Handles both the verbose LBO_Model.xlsx and compact generate_templates.py layouts.
"""
import re
from typing import Optional

# Maps (lowercase normalized header) → canonical key.
# EXACT matches only — no fuzzy/substring matching.
CANONICAL_ALIASES: dict[str, str] = {
    # ── Income Statement (compact template) ──
    "revenue": "is_revenue",
    "cogs": "is_cogs",
    "sg&a": "is_sga",
    "sga": "is_sga",
    "d&a": "is_da",
    "tax": "is_tax",
    "gross profit": "is_gross_profit",
    "ebitda": "is_ebitda",
    "ebit": "is_ebit",
    "interest expense": "is_interest_expense",
    "ebt": "is_ebt",
    "net income": "is_net_income",
    "total interest expense": "is_total_interest",

    # ── Income Statement (verbose LBO_Model.xlsx) ──
    "cost of goods sold": "is_cogs",
    "cost of revenue": "is_cogs",
    "sales": "is_revenue",
    "total revenue": "is_revenue",
    "selling, general & administrative": "is_sga",
    "selling general & administrative": "is_sga",
    "research & development": "is_rnd",
    "other operating expenses": "is_other_opex",
    "total operating expenses": "is_total_opex",
    "depreciation & amortization": "is_da",
    "depreciation": "is_da",
    "ebit (operating income)": "is_ebit",
    "interest expense \u2014 senior debt": "is_interest_senior",
    "interest expense \u2014 mezzanine": "is_interest_mezz",
    "earnings before tax": "is_ebt",
    "effective tax rate": "is_tax_rate",
    "income tax expense": "is_tax",
    "tax expense": "is_tax",

    # ── Balance Sheet (compact) ──
    "cash": "bs_cash",
    "accounts receivable": "bs_ar",
    "inventory": "bs_inventory",
    "other current assets": "bs_other_curr",
    "total current assets": "bs_total_curr_assets",
    "pp&e net": "bs_ppe_net",
    "goodwill": "bs_goodwill",
    "other non-current assets": "bs_other_noncurr",
    "total assets": "bs_total_assets",
    "accounts payable": "bs_ap",
    "accrued expenses": "bs_accrued",
    "current portion of debt": "bs_curr_debt",
    "total current liabilities": "bs_total_curr_liab",
    "senior debt": "bs_senior_debt",
    "mezzanine debt": "bs_mezz_debt",
    "total liabilities": "bs_total_liab",
    "common equity": "bs_common_equity",
    "retained earnings": "bs_retained_earnings",
    "total equity": "bs_total_equity",
    "total liabilities & equity": "bs_total_liab_equity",

    # ── Balance Sheet (verbose — section-qualified from parser) ──
    "assets > cash & cash equivalents": "bs_cash",
    "cash & cash equivalents": "bs_cash",
    "assets > accounts receivable, net": "bs_ar",
    "assets > inventory": "bs_inventory",
    "assets > prepaid expenses & other current": "bs_other_curr",
    "assets > property, plant & equipment, gross": "bs_ppe_gross",
    "assets > less: accumulated depreciation": "bs_accum_depr",
    "pp&e, net": "bs_ppe_net",
    "assets > goodwill": "bs_goodwill",
    "assets > intangible assets, net": "bs_intangibles",
    "assets > deferred tax assets": "bs_deferred_tax_a",
    "assets > other long-term assets": "bs_other_noncurr",
    "total non-current assets": "bs_total_noncurr_assets",
    "liabilities > accounts payable": "bs_ap",
    "liabilities > accrued liabilities & compensation": "bs_accrued",
    "liabilities > deferred revenue": "bs_deferred_rev",
    "liabilities > current portion of long-term debt": "bs_curr_debt",
    "current portion of long-term debt": "bs_curr_debt",
    "senior secured debt (net of current)": "bs_senior_debt",
    "mezzanine / pik debt": "bs_mezz_debt",
    "total long-term debt": "bs_lt_debt",
    "liabilities > deferred tax liabilities": "bs_deferred_tax_l",
    "liabilities > other long-term liabilities": "bs_other_lt_liab",
    "total non-current liabilities": "bs_total_noncurr_liab",
    "shareholders' equity > common stock & additional paid-in capital": "bs_common_equity",
    "shareholders' equity > retained earnings / (accumulated deficit)": "bs_retained_earnings",
    "retained earnings / (accumulated deficit)": "bs_retained_earnings",
    "shareholders' equity > accumulated other comprehensive income (loss)": "bs_aoci",
    "total shareholders' equity": "bs_total_equity",
    "total liabilities + equity": "bs_total_liab_equity",
    "balance sheet check  (must = 0)": "bs_check",
    "debt": "bs_total_debt",

    # ── Cash Flow (compact) ──
    "changes in working capital": "cf_wc_changes",
    "operating cf": "cf_ops",
    "capex": "cf_capex",
    "investing cf": "cf_inv",
    "debt drawdowns": "cf_debt_draws",
    "debt repayments": "cf_debt_repay",
    "dividends": "cf_dividends",
    "financing cf": "cf_fin",
    "net change in cash": "cf_net_change",
    "beginning cash": "cf_begin_cash",
    "ending cash": "cf_end_cash",

    # ── Cash Flow (verbose — section-qualified) ──
    "operating activities > changes in working capital": "cf_wc_changes",
    "add: depreciation & amortization": "cf_da",
    "net cash from operating activities": "cf_ops",
    "investing activities > capital expenditures (capex)": "cf_capex",
    "capital expenditures (capex)": "cf_capex",
    "investing activities > acquisitions, net of cash acquired": "cf_acquisitions",
    "investing activities > other investing activities": "cf_other_inv",
    "net cash from investing activities": "cf_inv",
    "proceeds from debt drawdowns": "cf_debt_draws",
    "repayment of debt": "cf_debt_repay",
    "financing activities > dividends paid to equity holders": "cf_dividends",
    "dividends paid to equity holders": "cf_dividends",
    "net cash from financing activities": "cf_fin",
    "net increase / (decrease) in cash": "cf_net_change",
    "cash & equivalents \u2014 beginning of period": "cf_begin_cash",
    "financing activities > cash & equivalents \u2014 beginning of period": "cf_begin_cash",
    "cash & equivalents \u2014 end of period": "cf_end_cash",
    "net change in working capital": "cf_net_wc",

    # ── Debt Schedule (section-qualified from verbose template) ──
    "senior secured debt > beginning balance": "ds_senior_begin",
    "senior secured debt > add: drawdowns & fundings": "ds_senior_draw",
    "senior secured debt > less: scheduled repayments": "ds_senior_repay",
    "senior secured debt > annual interest rate (pik %)": "ds_senior_rate",
    "mezzanine / pik debt > beginning balance": "ds_mezz_begin",
    "mezzanine / pik debt > add: drawdowns & fundings": "ds_mezz_draw",
    "mezzanine / pik debt > less: scheduled repayments": "ds_mezz_repay",
    "mezzanine / pik debt > annual interest rate (pik %)": "ds_mezz_rate",
    "total cash interest expense": "ds_total_interest",

    # ── Debt Schedule (compact — no section qualification) ──
    # These are handled specially in _process_ds_compact() below
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
    "wacc": "dcf_wacc",
    "terminal growth rate": "dcf_terminal_growth",
    "terminal value": "dcf_terminal_value",
    "pv of fcfs": "dcf_pv_fcfs",
    "enterprise value": "dcf_ev",
    "unlevered fcf": "dcf_ufcf",
}

# Sheet-scoped overrides: (sheet_role, normalized_header) → canonical
# These take priority over global aliases to avoid cross-sheet collisions.
SHEET_SCOPED_OVERRIDES: dict[tuple[str, str], str] = {
    ("cf", "net income"): "cf_net_income",
    ("cf", "d&a"): "cf_da",
    ("ds", "total interest expense"): "ds_total_interest",
    ("is", "total interest expense"): "is_interest_expense",
    ("ds", "total ending debt"): "ds_total_debt",
    ("ds", "ending balance"): "ds_senior_end",  # first occurrence (senior)
    ("ds", "average balance"): "ds_senior_avg",
    ("ds", "cash interest expense"): "ds_senior_interest",
    ("bs", "senior debt"): "bs_senior_debt",
    ("bs", "mezzanine debt"): "bs_mezz_debt",
}

# DS items that appear once per tranche without section qualification (compact template).
# We detect the tranche boundary by the "Senior Debt" / "Mezzanine Debt" label rows.
DS_TRANCHE_ITEMS = {
    "beginning balance": "begin",
    "drawdowns": "draw",
    "repayments": "repay",
    "ending balance": "end",
    "interest rate": "rate",
    "interest expense": "interest",
}


def _normalize_header(raw_header: str) -> str:
    """Normalize a parser-produced header for canonical matching."""
    h = raw_header.strip().lower()
    h = re.sub(r'\s*>\s*', ' > ', h)
    h = re.sub(r'\s+', ' ', h)
    return h


def _sheet_role(sheet_name: str) -> Optional[str]:
    """Detect sheet role from its name."""
    s = sheet_name.lower()
    if "income" in s: return "is"
    if "balance" in s: return "bs"
    if "cash flow" in s: return "cf"
    if "debt" in s: return "ds"
    if "return" in s: return "ra"
    if "revenue build" in s: return "rev_build"
    if "dcf" in s or "valuation" in s: return "dcf"
    if "free cash" in s: return "fcf"
    return None


def _resolve_canonical(normalized_header: str, sheet_role: Optional[str] = None) -> Optional[str]:
    """Look up canonical key via EXACT match only."""
    # Sheet-scoped override first
    if sheet_role:
        override = SHEET_SCOPED_OVERRIDES.get((sheet_role, normalized_header))
        if override:
            return override

    return CANONICAL_ALIASES.get(normalized_header)


def _detect_template_type(sheet_names: dict) -> str:
    """Detect template type from available sheets."""
    if "ds" in sheet_names and "ra" in sheet_names:
        return "LBO"
    if "dcf" in sheet_names or "fcf" in sheet_names:
        return "DCF"
    if "is" in sheet_names and "bs" in sheet_names:
        return "3-statement"
    return "unknown"


def _process_ds_compact(sheet_data: dict, row_map: dict, formula_rows: set, input_rows: set, sname: str):
    """Handle compact Debt Schedule where headers aren't section-qualified.
    Detects tranche boundaries from 'Senior Debt' / 'Mezzanine Debt' label rows."""
    # Find tranche boundary rows from headers list
    tranche = "senior"  # default to senior for first items
    tranche_boundaries = []
    for h in sheet_data.get("headers", []):
        name_lower = h["header"].strip().lower()
        if name_lower in ("senior debt", "senior secured debt"):
            tranche = "senior"
            tranche_boundaries.append(("senior", h["row"]))
        elif name_lower in ("mezzanine debt", "mezzanine / pik debt"):
            tranche = "mezz"
            tranche_boundaries.append(("mezz", h["row"]))

    if not tranche_boundaries:
        return  # No tranche markers found

    def _get_tranche_for_row(row):
        """Determine which tranche a row belongs to based on position."""
        current_tranche = "senior"
        for t, boundary_row in tranche_boundaries:
            if row >= boundary_row:
                current_tranche = t
        return current_tranche

    all_cells = sheet_data.get("input_cells", []) + sheet_data.get("formula_cells", [])
    for cell in all_cells:
        ref = cell["ref"]
        row_num = int(re.search(r'\d+', ref).group())
        header = cell.get("column_header", "").strip().lower()
        is_formula = "formula" in cell

        tranche_for_row = _get_tranche_for_row(row_num)
        ds_item = DS_TRANCHE_ITEMS.get(header)

        if ds_item:
            canonical = f"ds_{tranche_for_row}_{ds_item}"
            key = (sname, canonical)
            if key not in row_map:
                row_map[key] = row_num

        if is_formula:
            formula_rows.add((sname, row_num))
        else:
            input_rows.add((sname, row_num))


def build_row_map(parsed_template: dict) -> dict:
    """Build universal row map from parser output.

    Returns dict with keys:
        row_map:       {(sheet_name, canonical_key): row_number}
        formula_rows:  set of (sheet_name, row_number) for formula cells
        input_rows:    set of (sheet_name, row_number) for input cells
        sheet_names:   {"is": "Income Statement", "bs": "Balance Sheet", ...}
        template_type: "LBO" | "DCF" | "3-statement" | "unknown"
        periods:       ["FY2020", "FY2021", ...]
        col_letters:   ["B", "C", ...]
    """
    row_map = {}
    formula_rows = set()
    input_rows = set()
    sheet_names = {}
    periods = []

    for sheet in parsed_template["sheets"]:
        sname = sheet["name"]
        role = _sheet_role(sname)
        if role:
            sheet_names[role] = sname

        # Extract periods from first sheet that has them
        if not periods and sheet.get("temporal_headers"):
            periods = list(sheet["temporal_headers"])

        # For DS sheets, check if headers are section-qualified
        ds_has_qualified = False
        if role == "ds":
            for cell in sheet.get("input_cells", []):
                h = cell.get("column_header", "")
                if " > " in h:
                    ds_has_qualified = True
                    break

        # Process input cells
        for cell in sheet.get("input_cells", []):
            ref = cell["ref"]
            row_num = int(re.search(r'\d+', ref).group())
            header = cell.get("column_header", "")
            canonical = _resolve_canonical(_normalize_header(header), role)

            if canonical:
                key = (sname, canonical)
                if key not in row_map:
                    row_map[key] = row_num

            input_rows.add((sname, row_num))

        # Process formula cells
        for cell in sheet.get("formula_cells", []):
            ref = cell["ref"]
            row_num = int(re.search(r'\d+', ref).group())
            header = cell.get("column_header", "")
            canonical = _resolve_canonical(_normalize_header(header), role)

            if canonical:
                key = (sname, canonical)
                if key not in row_map:
                    row_map[key] = row_num

            formula_rows.add((sname, row_num))

        # For compact DS without section-qualified headers, do tranche detection
        if role == "ds" and not ds_has_qualified:
            _process_ds_compact(sheet, row_map, formula_rows, input_rows, sname)

    # For verbose DS template, also map formula-only items that have generic names
    # e.g. "Ending Balance" (formula) appears without qualification in verbose template too
    for sheet in parsed_template["sheets"]:
        sname = sheet["name"]
        role = _sheet_role(sname)
        if role == "ds":
            _map_ds_formula_rows(sheet, row_map, sname)

    # Scan section headers for "TOTAL ASSETS", "TOTAL LIABILITIES", etc.
    # The parser skips these as data rows but we need them for validation formulas.
    SECTION_HEADER_MAP = {
        "total assets": "bs_total_assets",
        "total liabilities": "bs_total_liab",
        "total liabilities + equity": "bs_total_liab_equity",
        "total liabilities & equity": "bs_total_liab_equity",
    }
    for sheet in parsed_template["sheets"]:
        sname = sheet["name"]
        role = _sheet_role(sname)
        if role != "bs":
            continue
        for h in sheet.get("headers", []):
            if h.get("is_section"):
                h_lower = h["header"].strip().lower()
                canonical = SECTION_HEADER_MAP.get(h_lower)
                if canonical:
                    key = (sname, canonical)
                    if key not in row_map:
                        row_map[key] = h["row"]
                        formula_rows.add((sname, h["row"]))

    col_letters = [chr(66 + i) for i in range(len(periods))]  # B, C, D, ...
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


def _map_ds_formula_rows(sheet_data: dict, row_map: dict, sname: str):
    """Map DS formula rows (Ending Balance, Interest Expense) to correct tranche.
    Uses range-based approach: Senior items are between senior_begin and mezz_begin;
    Mezz items are after mezz_begin."""
    sen_begin = row_map.get((sname, "ds_senior_begin"))
    mezz_begin = row_map.get((sname, "ds_mezz_begin"))

    def _tranche_for_row(row):
        if sen_begin and mezz_begin:
            return "ds_senior" if row < mezz_begin else "ds_mezz"
        elif sen_begin:
            return "ds_senior"
        return "ds_mezz"

    for cell in sheet_data.get("formula_cells", []):
        ref = cell["ref"]
        row_num = int(re.search(r'\d+', ref).group())
        header = cell.get("column_header", "").strip().lower()
        prefix = _tranche_for_row(row_num)

        if header == "ending balance":
            key = (sname, f"{prefix}_end")
            if key not in row_map:
                row_map[key] = row_num
        elif header in ("cash interest expense", "interest expense"):
            key = (sname, f"{prefix}_interest")
            if key not in row_map:
                row_map[key] = row_num
        elif header == "average balance":
            key = (sname, f"{prefix}_avg")
            if key not in row_map:
                row_map[key] = row_num
        elif header == "total cash interest expense":
            key = (sname, "ds_total_interest")
            if key not in row_map:
                row_map[key] = row_num
        elif header == "total ending debt":
            key = (sname, "ds_total_debt")
            if key not in row_map:
                row_map[key] = row_num
