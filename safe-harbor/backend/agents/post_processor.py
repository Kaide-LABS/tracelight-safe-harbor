"""
Template-Driven Circular Reference Solver (Fixed-Point Iteration)

Resolves the Interest -> NI -> CF -> Repayment circularity in LBO models.
Uses row_map from parser output — no hardcoded row numbers.

For DCF templates: passes through (no circular refs).
For 3-Statement: simplified solver (no debt tranches).
"""
import copy
from backend.agents.row_map import build_row_map

# ── Column / Period mapping ──────────────────────────────────────────────────
COL_TO_PERIOD = {"B": 0, "C": 1, "D": 2, "E": 3, "F": 4, "G": 5}
PERIOD_TO_COL = {v: k for k, v in COL_TO_PERIOD.items()}


def _key(sheet, row):
    return (sheet, row)

def _get(grid, sheet, row, default=0.0):
    if row is None:
        return default
    v = grid.get(_key(sheet, row), default)
    try:
        return float(v)
    except (TypeError, ValueError):
        return default

def _set(grid, sheet, row, val):
    if row is not None:
        grid[_key(sheet, row)] = val


def _row(rm, sheet_key, canonical):
    """Look up row number from row_map. Returns None if not found."""
    sname = rm["sheet_names"].get(sheet_key)
    if not sname:
        return None
    return rm["row_map"].get((sname, canonical))


def _is_input(rm, sheet_key, row):
    """Check if a cell is an input (writable) cell."""
    sname = rm["sheet_names"].get(sheet_key)
    if not sname or row is None:
        return False
    return (sname, row) in rm["input_rows"]


def simulate_period_lbo(grid, prev, senior_repay, mezz_repay, rm, default_tax_rate=0.25):
    """Simulate full IS -> DS -> CF -> BS chain for one LBO period.
    Returns (grid, new_sen_repay, new_mezz_repay)."""
    g = grid
    IS = rm["sheet_names"].get("is", "Income Statement")
    BS = rm["sheet_names"].get("bs", "Balance Sheet")
    CF = rm["sheet_names"].get("cf", "Cash Flow")
    DS = rm["sheet_names"].get("ds", "Debt Schedule")

    # Row lookups
    r_sen_begin = _row(rm, "ds", "ds_senior_begin")
    r_sen_draw = _row(rm, "ds", "ds_senior_draw")
    r_sen_repay = _row(rm, "ds", "ds_senior_repay")
    r_sen_end = _row(rm, "ds", "ds_senior_end")
    r_sen_rate = _row(rm, "ds", "ds_senior_rate")
    r_sen_interest = _row(rm, "ds", "ds_senior_interest")

    r_mezz_begin = _row(rm, "ds", "ds_mezz_begin")
    r_mezz_draw = _row(rm, "ds", "ds_mezz_draw")
    r_mezz_repay = _row(rm, "ds", "ds_mezz_repay")
    r_mezz_end = _row(rm, "ds", "ds_mezz_end")
    r_mezz_rate = _row(rm, "ds", "ds_mezz_rate")
    r_mezz_interest = _row(rm, "ds", "ds_mezz_interest")
    r_ds_total_interest = _row(rm, "ds", "ds_total_interest")

    r_rev = _row(rm, "is", "is_revenue")
    r_cogs = _row(rm, "is", "is_cogs")
    r_gross = _row(rm, "is", "is_gross_profit")
    r_sga = _row(rm, "is", "is_sga")
    r_ebitda = _row(rm, "is", "is_ebitda")
    r_da = _row(rm, "is", "is_da")
    r_ebit = _row(rm, "is", "is_ebit")
    r_interest = _row(rm, "is", "is_interest_expense")
    r_ebt = _row(rm, "is", "is_ebt")
    r_tax = _row(rm, "is", "is_tax")
    r_ni = _row(rm, "is", "is_net_income")

    r_cf_wc = _row(rm, "cf", "cf_wc_changes")
    r_cf_ops = _row(rm, "cf", "cf_ops")
    r_cf_capex = _row(rm, "cf", "cf_capex")
    r_cf_inv = _row(rm, "cf", "cf_inv")
    r_cf_draws = _row(rm, "cf", "cf_debt_draws")
    r_cf_repay = _row(rm, "cf", "cf_debt_repay")
    r_cf_div = _row(rm, "cf", "cf_dividends")
    r_cf_fin = _row(rm, "cf", "cf_fin")
    r_cf_net = _row(rm, "cf", "cf_net_change")
    r_cf_begin = _row(rm, "cf", "cf_begin_cash")
    r_cf_end = _row(rm, "cf", "cf_end_cash")

    r_bs_cash = _row(rm, "bs", "bs_cash")

    # ── 0. Cross-period linkages ─────────────────────────────────────────────
    # Senior Beginning Balance(t) = Senior Ending Balance(t-1)
    prev_sen_end = _get(prev, DS, r_sen_end, default=_get(prev, DS, r_sen_begin))
    if r_sen_begin and _is_input(rm, "ds", r_sen_begin):
        _set(g, DS, r_sen_begin, prev_sen_end)

    # Mezz Beginning Balance(t) = Mezz Ending Balance(t-1)
    prev_mezz_end = _get(prev, DS, r_mezz_end, default=_get(prev, DS, r_mezz_begin))
    if r_mezz_begin and _is_input(rm, "ds", r_mezz_begin):
        _set(g, DS, r_mezz_begin, prev_mezz_end)

    # ── 1. Plug repayment guesses ────────────────────────────────────────────
    if r_sen_repay and _is_input(rm, "ds", r_sen_repay):
        _set(g, DS, r_sen_repay, senior_repay)
    if r_mezz_repay and _is_input(rm, "ds", r_mezz_repay):
        _set(g, DS, r_mezz_repay, mezz_repay)

    # ── 2. Debt Schedule ─────────────────────────────────────────────────────
    sen_begin = _get(g, DS, r_sen_begin)
    sen_draw = _get(g, DS, r_sen_draw)
    sen_end = sen_begin + sen_draw - senior_repay
    _set(g, DS, r_sen_end, sen_end)

    sen_rate = _get(g, DS, r_sen_rate)
    sen_interest = sen_begin * sen_rate  # BEGIN x RATE (matches template formula)
    _set(g, DS, r_sen_interest, sen_interest)

    mezz_begin = _get(g, DS, r_mezz_begin)
    mezz_draw = _get(g, DS, r_mezz_draw)
    mezz_end = mezz_begin + mezz_draw - mezz_repay
    _set(g, DS, r_mezz_end, mezz_end)

    mezz_rate = _get(g, DS, r_mezz_rate)
    mezz_interest = mezz_begin * mezz_rate  # BEGIN x RATE
    _set(g, DS, r_mezz_interest, mezz_interest)

    total_interest = sen_interest + mezz_interest
    _set(g, DS, r_ds_total_interest, total_interest)

    # ── 3. Income Statement ──────────────────────────────────────────────────
    revenue = _get(g, IS, r_rev)
    cogs = _get(g, IS, r_cogs)
    gross = revenue - cogs
    _set(g, IS, r_gross, gross)

    sga = _get(g, IS, r_sga)
    ebitda = gross - sga  # Template: =Gross Profit - SG&A
    _set(g, IS, r_ebitda, ebitda)

    da = _get(g, IS, r_da)
    ebit = ebitda - abs(da)  # Template: =EBITDA - D&A
    _set(g, IS, r_ebit, ebit)

    # Interest Expense on IS = DS Total Interest
    _set(g, IS, r_interest, total_interest)

    ebt = ebit - total_interest  # Template: =EBIT - Interest
    _set(g, IS, r_ebt, ebt)

    tax = _get(g, IS, r_tax)
    if tax == 0:
        tax = max(0.0, ebt * default_tax_rate)
    net_income = ebt - tax  # Template: =EBT - Tax
    _set(g, IS, r_ni, net_income)

    # ── 4. Cash Flow ─────────────────────────────────────────────────────────
    _set(g, CF, _row(rm, "cf", "cf_net_income"), net_income)
    _set(g, CF, _row(rm, "cf", "cf_da"), abs(da))

    wc_changes = _get(g, CF, r_cf_wc)  # Single input cell in template
    ops_cf = net_income + abs(da) + wc_changes
    _set(g, CF, r_cf_ops, ops_cf)

    capex = _get(g, CF, r_cf_capex)
    inv_cf = -abs(capex) if capex >= 0 else capex  # Template: =-CapEx
    _set(g, CF, r_cf_inv, inv_cf)

    # Financing: template uses Draws - Repay - Dividends
    draws = _get(g, CF, r_cf_draws)
    dividends = _get(g, CF, r_cf_div)
    total_repay = senior_repay + mezz_repay
    fin_cf = draws - total_repay - dividends
    _set(g, CF, r_cf_fin, fin_cf)

    net_change = ops_cf + inv_cf + fin_cf
    _set(g, CF, r_cf_net, net_change)

    # Beginning Cash is a FORMULA in the template — read from prev period's ending cash
    prev_end_cash = _get(prev, CF, r_cf_end, default=_get(prev, BS, r_bs_cash))
    _set(g, CF, r_cf_begin, prev_end_cash)
    end_cash = prev_end_cash + net_change
    _set(g, CF, r_cf_end, end_cash)

    # ── 5. Balance Sheet ─────────────────────────────────────────────────────
    # Cash on BS should equal ending cash from CF — Cash IS an input cell
    if r_bs_cash and _is_input(rm, "bs", r_bs_cash):
        _set(g, BS, r_bs_cash, end_cash)

    # Update BS debt to match DS ending balances
    r_bs_sen = _row(rm, "bs", "bs_senior_debt")
    r_bs_mezz = _row(rm, "bs", "bs_mezz_debt")
    if r_bs_sen and _is_input(rm, "bs", r_bs_sen):
        _set(g, BS, r_bs_sen, sen_end)
    if r_bs_mezz and _is_input(rm, "bs", r_bs_mezz):
        _set(g, BS, r_bs_mezz, mezz_end)

    # Simulate BS totals for convergence check (don't write — these are formulas)
    r_ar = _row(rm, "bs", "bs_ar")
    r_inv = _row(rm, "bs", "bs_inventory")
    r_other_ca = _row(rm, "bs", "bs_other_curr")
    r_tca = _row(rm, "bs", "bs_total_curr_assets")
    r_ppe = _row(rm, "bs", "bs_ppe_net")
    r_gw = _row(rm, "bs", "bs_goodwill")
    r_other_nca = _row(rm, "bs", "bs_other_noncurr")
    r_ta = _row(rm, "bs", "bs_total_assets")
    r_ap = _row(rm, "bs", "bs_ap")
    r_accrued = _row(rm, "bs", "bs_accrued")
    r_curr_debt = _row(rm, "bs", "bs_curr_debt")
    r_tcl = _row(rm, "bs", "bs_total_curr_liab")
    r_tl = _row(rm, "bs", "bs_total_liab")
    r_ceq = _row(rm, "bs", "bs_common_equity")
    r_re = _row(rm, "bs", "bs_retained_earnings")
    r_te = _row(rm, "bs", "bs_total_equity")
    r_tle = _row(rm, "bs", "bs_total_liab_equity")

    curr_assets = end_cash + _get(g, BS, r_ar) + _get(g, BS, r_inv) + _get(g, BS, r_other_ca)
    _set(g, BS, r_tca, curr_assets)
    total_assets = curr_assets + _get(g, BS, r_ppe) + _get(g, BS, r_gw) + _get(g, BS, r_other_nca)
    _set(g, BS, r_ta, total_assets)

    curr_liab = _get(g, BS, r_ap) + _get(g, BS, r_accrued) + _get(g, BS, r_curr_debt)
    _set(g, BS, r_tcl, curr_liab)
    total_liab = curr_liab + sen_end + mezz_end
    _set(g, BS, r_tl, total_liab)

    # RE rollforward: prev_RE + NI (this is a FORMULA cell — simulate but don't write back)
    prev_re = _get(prev, BS, r_re)
    retained = prev_re + net_income
    _set(g, BS, r_re, retained)

    total_equity = _get(g, BS, r_ceq) + retained
    _set(g, BS, r_te, total_equity)
    _set(g, BS, r_tle, total_liab + total_equity)

    # ── 6. Derive new repayment from cash available ──────────────────────────
    cash_before_repay = end_cash + total_repay
    new_sen = min(sen_begin + sen_draw, max(0.0, cash_before_repay))
    remaining = max(0.0, cash_before_repay - new_sen)
    new_mezz = min(mezz_begin + mezz_draw, max(0.0, remaining))

    return g, new_sen, new_mezz


def post_process(cells, parsed_template=None):
    """
    Main entry point. Template-driven fixed-point iteration solver.
    Only modifies INPUT cells — never writes to formula cells.
    """
    if parsed_template is None:
        return cells  # Can't fix what we can't map

    rm = build_row_map(parsed_template)
    template_type = rm["template_type"]

    # DCF has no circular references — pass through
    if template_type == "DCF":
        return cells

    # Need at minimum IS + BS + CF sheets
    if not all(k in rm["sheet_names"] for k in ("is", "bs", "cf")):
        return cells

    IS = rm["sheet_names"]["is"]
    BS = rm["sheet_names"]["bs"]
    CF = rm["sheet_names"]["cf"]
    DS = rm["sheet_names"].get("ds")

    # If no debt schedule, no circular refs to solve
    if template_type == "LBO" and not DS:
        return cells

    # Parse flat cells into per-period grids
    period_grids = {t: {} for t in range(6)}
    cell_index = {}  # (sheet, row, period_idx) -> index in cells list

    for i, c in enumerate(cells):
        ref = c.get("cell_ref", "")
        if not ref or len(ref) < 2:
            continue
        col_letter = ref[0].upper()
        if col_letter not in COL_TO_PERIOD:
            continue
        try:
            row_num = int(ref[1:])
        except ValueError:
            continue
        t = COL_TO_PERIOD[col_letter]
        sheet = c.get("sheet_name", "")
        val = c.get("value", 0)
        try:
            val = float(val)
        except (TypeError, ValueError):
            val = 0.0

        period_grids[t][(sheet, row_num)] = val
        cell_index[(sheet, row_num, t)] = i

    # Row lookups for write-back
    r_da = _row(rm, "is", "is_da")
    r_sen_repay = _row(rm, "ds", "ds_senior_repay") if DS else None
    r_mezz_repay = _row(rm, "ds", "ds_mezz_repay") if DS else None
    r_cf_repay = _row(rm, "cf", "cf_debt_repay")
    r_cf_draws = _row(rm, "cf", "cf_debt_draws")
    r_bs_cash = _row(rm, "bs", "bs_cash")
    r_bs_sen = _row(rm, "bs", "bs_senior_debt")
    r_bs_mezz = _row(rm, "bs", "bs_mezz_debt")

    # ── Phase 1: Fix sign conventions across all periods ────────────────────
    for t in range(6):
        g = period_grids[t]
        # D&A should be positive (template subtracts it via formula)
        if r_da:
            da_val = _get(g, IS, r_da)
            if da_val < 0:
                _set(g, IS, r_da, abs(da_val))

        # Repayments should be positive (template subtracts via formula)
        if r_sen_repay:
            r = _get(g, DS, r_sen_repay)
            if r < 0:
                _set(g, DS, r_sen_repay, abs(r))
        if r_mezz_repay:
            r = _get(g, DS, r_mezz_repay)
            if r < 0:
                _set(g, DS, r_mezz_repay, abs(r))

    # ── Phase 2: Simulate ALL periods ────────────────────────────────────
    # Run simulation for t=0 (single pass) and t=1..5 (fixed-point iteration)
    # to populate formula cells in the grid before computing BS plug.
    r_cf_end = _row(rm, "cf", "cf_end_cash")
    r_cf_begin = _row(rm, "cf", "cf_begin_cash")

    if template_type == "LBO" and DS:
        # t=0: single simulation pass to populate formula cells
        empty_prev = {}
        g0 = copy.copy(period_grids[0])
        g0, _, _ = simulate_period_lbo(g0, empty_prev,
                                        _get(g0, DS, _row(rm, "ds", "ds_senior_repay")),
                                        _get(g0, DS, _row(rm, "ds", "ds_mezz_repay")), rm)
        period_grids[0] = g0

        # t=1..5: fixed-point iteration
        for t in range(1, 6):
            prev = period_grids[t - 1]
            sen_guess = 0.0
            mezz_guess = 0.0

            for iteration in range(100):
                g = copy.copy(period_grids[t])
                g, new_sen, new_mezz = simulate_period_lbo(g, prev, sen_guess, mezz_guess, rm)

                if abs(new_sen - sen_guess) <= 1e-4 and abs(new_mezz - mezz_guess) <= 1e-4:
                    period_grids[t] = g
                    break

                sen_guess = new_sen
                mezz_guess = new_mezz
            else:
                period_grids[t] = g

    # ── Phase 3: Write back ONLY writable input cells ──────────────────────
    # BS balance plug is handled AFTER xlsx write via bs_plug.balance_bs()
    # which uses formulas.ExcelModel to evaluate actual template formulas.
    output = copy.deepcopy(cells)

    for t in range(6):
        g = period_grids[t]

        # D&A sign fix (positive for template to subtract)
        if r_da and _is_input(rm, "is", r_da):
            idx = cell_index.get((IS, r_da, t))
            if idx is not None:
                output[idx]["value"] = round(abs(_get(g, IS, r_da)), 2)

        # Senior Repayments (positive for template to subtract)
        if r_sen_repay and _is_input(rm, "ds", r_sen_repay):
            idx = cell_index.get((DS, r_sen_repay, t))
            if idx is not None:
                output[idx]["value"] = round(abs(_get(g, DS, r_sen_repay)), 2)

        # Mezz Repayments
        if r_mezz_repay and _is_input(rm, "ds", r_mezz_repay):
            idx = cell_index.get((DS, r_mezz_repay, t))
            if idx is not None:
                output[idx]["value"] = round(abs(_get(g, DS, r_mezz_repay)), 2)

        # CF Debt Repayments (must match DS total repayments)
        if r_cf_repay and _is_input(rm, "cf", r_cf_repay):
            idx = cell_index.get((CF, r_cf_repay, t))
            if idx is not None:
                total_repay = abs(_get(g, DS, r_sen_repay)) + abs(_get(g, DS, r_mezz_repay)) if DS else 0
                output[idx]["value"] = round(total_repay, 2)

        # CF Debt Drawdowns (must match DS total drawdowns)
        if r_cf_draws and _is_input(rm, "cf", r_cf_draws):
            idx = cell_index.get((CF, r_cf_draws, t))
            if idx is not None:
                r_sd = _row(rm, "ds", "ds_senior_draw")
                r_md = _row(rm, "ds", "ds_mezz_draw")
                total_draws = (_get(g, DS, r_sd) + _get(g, DS, r_md)) if DS else 0
                output[idx]["value"] = round(total_draws, 2)

        # BS Cash = CF Ending Cash
        if r_bs_cash and _is_input(rm, "bs", r_bs_cash):
            idx = cell_index.get((BS, r_bs_cash, t))
            if idx is not None:
                output[idx]["value"] = round(_get(g, CF, r_cf_end), 2)

        # BS Senior Debt = DS Senior Ending Balance
        if r_bs_sen and _is_input(rm, "bs", r_bs_sen) and DS:
            idx = cell_index.get((BS, r_bs_sen, t))
            if idx is not None:
                r_se = _row(rm, "ds", "ds_senior_end")
                output[idx]["value"] = round(_get(g, DS, r_se), 2)

        # BS Mezz Debt = DS Mezz Ending Balance
        if r_bs_mezz and _is_input(rm, "bs", r_bs_mezz) and DS:
            idx = cell_index.get((BS, r_bs_mezz, t))
            if idx is not None:
                r_me = _row(rm, "ds", "ds_mezz_end")
                output[idx]["value"] = round(_get(g, DS, r_me), 2)

    return output
