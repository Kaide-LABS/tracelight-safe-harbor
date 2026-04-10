"""
LBO Circular Reference Solver (Fixed-Point Iteration)
Based on Gemini Deep Research + Claude Red-Team implementation.

Takes flat cell list, modifies ONLY input cells:
- Retained Earnings (BS row 40) — all periods
- Beginning Cash (CF row 31) — t>0
- Scheduled Repayments (DS rows 7, 18) — t>0 (positive, template subtracts)

Uses Banach fixed-point iteration to resolve the Interest → NI → CF → Repayment circularity.
"""
import copy

# ── Column / Period mapping ──────────────────────────────────────────────────
COL_TO_PERIOD = {"B": 0, "C": 1, "D": 2, "E": 3, "F": 4, "G": 5}
PERIOD_TO_COL = {v: k for k, v in COL_TO_PERIOD.items()}

# ── Sheet names (must match actual template) ─────────────────────────────────
IS = "Income Statement"
DS = "Debt Schedule"
CF = "Cash Flow Statement"
BS = "Balance Sheet"


def _key(sheet, row):
    return (sheet, row)

def _get(grid, sheet, row, default=0.0):
    v = grid.get(_key(sheet, row), default)
    try:
        return float(v)
    except (TypeError, ValueError):
        return default

def _set(grid, sheet, row, val):
    grid[_key(sheet, row)] = val


def simulate_period(grid, prev, senior_repay, mezz_repay, default_tax_rate=0.25):
    """Simulate full IS → DS → CF → BS chain for one period. Returns (grid, new_sen_repay, new_mezz_repay)."""
    g = grid

    # ── 0. Cross-period linkages ─────────────────────────────────────────────
    prev_end_cash = _get(prev, CF, 32, default=_get(prev, BS, 5))
    _set(g, CF, 31, prev_end_cash)

    prev_sen_end = _get(prev, DS, 9, default=_get(prev, DS, 5))
    _set(g, DS, 5, prev_sen_end)

    prev_mezz_end = _get(prev, DS, 20, default=_get(prev, DS, 16))
    _set(g, DS, 16, prev_mezz_end)

    # ── 1. Plug repayment guesses (positive — template subtracts) ────────────
    _set(g, DS, 7, senior_repay)
    _set(g, DS, 18, mezz_repay)

    # ── 2. Debt Schedule ─────────────────────────────────────────────────────
    sen_begin = _get(g, DS, 5)
    sen_draw = _get(g, DS, 6)
    sen_end = sen_begin + sen_draw - senior_repay
    _set(g, DS, 9, sen_end)

    sen_rate = _get(g, DS, 11)
    sen_avg = (sen_begin + sen_end) / 2.0
    _set(g, DS, 12, sen_avg)
    sen_interest = sen_avg * sen_rate
    _set(g, DS, 13, sen_interest)

    mezz_begin = _get(g, DS, 16)
    mezz_draw = _get(g, DS, 17)
    mezz_end = mezz_begin + mezz_draw - mezz_repay
    _set(g, DS, 20, mezz_end)

    mezz_rate = _get(g, DS, 22)
    mezz_avg = (mezz_begin + mezz_end) / 2.0
    _set(g, DS, 23, mezz_avg)
    mezz_interest = mezz_avg * mezz_rate
    _set(g, DS, 24, mezz_interest)

    # ── 3. Income Statement ──────────────────────────────────────────────────
    revenue = _get(g, IS, 4)
    cogs = _get(g, IS, 5)
    gross = revenue - cogs
    _set(g, IS, 6, gross)

    sga = _get(g, IS, 9)
    rnd = _get(g, IS, 10)
    other_opex = _get(g, IS, 11)
    total_opex = sga + rnd + other_opex
    _set(g, IS, 12, total_opex)

    ebitda = gross - total_opex
    _set(g, IS, 14, ebitda)

    da = _get(g, IS, 17)  # negative on IS
    ebit = ebitda + da  # da is negative, so this subtracts
    _set(g, IS, 18, ebit)

    _set(g, IS, 21, sen_interest)
    _set(g, IS, 22, mezz_interest)
    total_interest = sen_interest + mezz_interest
    _set(g, IS, 23, total_interest)

    ebt = ebit - total_interest
    _set(g, IS, 25, ebt)

    tax_rate = _get(g, IS, 26, default_tax_rate)
    tax_expense = max(0.0, ebt * tax_rate)
    _set(g, IS, 27, tax_expense)

    net_income = ebt - tax_expense
    _set(g, IS, 29, net_income)

    # ── 4. Cash Flow ─────────────────────────────────────────────────────────
    _set(g, CF, 5, net_income)
    da_addback = abs(da)
    _set(g, CF, 6, da_addback)

    # Working capital changes (computed from BS deltas)
    chg_ar = -(_get(g, BS, 6) - _get(prev, BS, 6))
    chg_inv = -(_get(g, BS, 7) - _get(prev, BS, 7))
    chg_ap = _get(g, BS, 23) - _get(prev, BS, 23)
    chg_accrued = _get(g, BS, 24) - _get(prev, BS, 24)
    chg_defrev = _get(g, BS, 25) - _get(prev, BS, 25)
    _set(g, CF, 9, chg_ar)
    _set(g, CF, 10, chg_inv)
    _set(g, CF, 11, chg_ap)
    _set(g, CF, 12, chg_accrued)
    _set(g, CF, 13, chg_defrev)

    net_wc = chg_ar + chg_inv + chg_ap + chg_accrued + chg_defrev
    _set(g, CF, 14, net_wc)

    net_cash_ops = net_income + da_addback + net_wc
    _set(g, CF, 16, net_cash_ops)

    capex = _get(g, CF, 19)
    acquisitions = _get(g, CF, 20)
    other_inv = _get(g, CF, 21)
    net_cash_inv = capex + acquisitions + other_inv
    _set(g, CF, 22, net_cash_inv)

    debt_draws = sen_draw + mezz_draw
    _set(g, CF, 25, debt_draws)
    debt_repay_cf = -(senior_repay + mezz_repay)  # negative on CF
    _set(g, CF, 26, debt_repay_cf)
    dividends = _get(g, CF, 27)
    net_cash_fin = debt_draws + debt_repay_cf - dividends
    _set(g, CF, 28, net_cash_fin)

    net_change = net_cash_ops + net_cash_inv + net_cash_fin
    _set(g, CF, 30, net_change)

    beg_cash = _get(g, CF, 31)
    end_cash = beg_cash + net_change
    _set(g, CF, 32, end_cash)

    # ── 5. Balance Sheet ─────────────────────────────────────────────────────
    _set(g, BS, 5, end_cash)

    curr_assets = end_cash + _get(g, BS, 6) + _get(g, BS, 7) + _get(g, BS, 8)
    _set(g, BS, 9, curr_assets)

    ppe_net = _get(g, BS, 11) - abs(_get(g, BS, 12))
    _set(g, BS, 13, ppe_net)

    non_curr = ppe_net + _get(g, BS, 14) + _get(g, BS, 15) + _get(g, BS, 16) + _get(g, BS, 17)
    _set(g, BS, 18, non_curr)

    total_assets = curr_assets + non_curr
    _set(g, BS, 20, total_assets)

    curr_liab = _get(g, BS, 23) + _get(g, BS, 24) + _get(g, BS, 25) + _get(g, BS, 26)
    _set(g, BS, 27, curr_liab)

    _set(g, BS, 29, sen_end)
    _set(g, BS, 30, mezz_end)
    total_lt_debt = sen_end + mezz_end
    _set(g, BS, 31, total_lt_debt)

    non_curr_liab = total_lt_debt + _get(g, BS, 32) + _get(g, BS, 33)
    _set(g, BS, 34, non_curr_liab)

    total_liab = curr_liab + non_curr_liab
    _set(g, BS, 36, total_liab)

    # RE rollforward
    prev_re = _get(prev, BS, 40)
    retained = prev_re + net_income - dividends
    _set(g, BS, 40, retained)

    total_equity = _get(g, BS, 39) + retained + _get(g, BS, 41)
    _set(g, BS, 42, total_equity)
    _set(g, BS, 44, total_liab + total_equity)
    _set(g, BS, 45, total_assets - (total_liab + total_equity))

    # ── 6. Derive new repayment from cash available ──────────────────────────
    cash_before_repay = end_cash + senior_repay + mezz_repay
    new_sen = min(sen_begin + sen_draw, max(0.0, cash_before_repay))
    remaining = max(0.0, cash_before_repay - new_sen)
    new_mezz = min(mezz_begin + mezz_draw, max(0.0, remaining))

    return g, new_sen, new_mezz


def post_process(cells, parsed_template=None):
    """
    Main entry point. Fixed-point iteration solver for LBO circular references.
    Only modifies: RetainedEarnings, BeginningCash(t>0), Repayments(t>0).
    """
    # Parse flat cells into per-period grids
    period_grids = {t: {} for t in range(6)}
    cell_index = {}  # (sheet, row, period_idx) → index in cells list

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

    # ── Phase 1: Balance historical period (t=0) ────────────────────────────
    g0 = period_grids[0]

    # Fix D&A sign: must be negative on IS
    da0 = _get(g0, IS, 17)
    if da0 > 0:
        _set(g0, IS, 17, -da0)

    # Fix repayment sign: must be positive for template formula
    for repay_row in [7, 18]:
        r = _get(g0, DS, repay_row)
        if r < 0:
            _set(g0, DS, repay_row, abs(r))

    # Compute t=0 DS ending balances
    sen_end0 = _get(g0, DS, 5) + _get(g0, DS, 6) - _get(g0, DS, 7)
    mezz_end0 = _get(g0, DS, 16) + _get(g0, DS, 17) - _get(g0, DS, 18)
    _set(g0, DS, 9, sen_end0)
    _set(g0, DS, 20, mezz_end0)

    # Compute t=0 BS totals for RE plug
    cash0 = _get(g0, BS, 5)
    curr_a0 = cash0 + _get(g0, BS, 6) + _get(g0, BS, 7) + _get(g0, BS, 8)
    ppe_net0 = _get(g0, BS, 11) - abs(_get(g0, BS, 12))
    non_curr_a0 = ppe_net0 + _get(g0, BS, 14) + _get(g0, BS, 15) + _get(g0, BS, 16) + _get(g0, BS, 17)
    total_a0 = curr_a0 + non_curr_a0

    curr_l0 = _get(g0, BS, 23) + _get(g0, BS, 24) + _get(g0, BS, 25) + _get(g0, BS, 26)
    non_curr_l0 = sen_end0 + mezz_end0 + _get(g0, BS, 32) + _get(g0, BS, 33)
    total_l0 = curr_l0 + non_curr_l0

    known_eq0 = _get(g0, BS, 39) + _get(g0, BS, 41)
    re0 = total_a0 - total_l0 - known_eq0
    _set(g0, BS, 40, re0)

    # Set t=0 EndCash for CF linkage
    _set(g0, CF, 32, cash0)
    _set(g0, CF, 31, cash0)

    # ── Phase 2: Fixed-point iteration for t=1..5 ───────────────────────────
    for t in range(1, 6):
        prev = period_grids[t - 1]
        sen_guess = 0.0
        mezz_guess = 0.0

        # Fix D&A sign for this period
        da_t = _get(period_grids[t], IS, 17)
        if da_t > 0:
            _set(period_grids[t], IS, 17, -da_t)

        for iteration in range(100):
            g = copy.copy(period_grids[t])
            g, new_sen, new_mezz = simulate_period(g, prev, sen_guess, mezz_guess)

            if abs(new_sen - sen_guess) <= 1e-4 and abs(new_mezz - mezz_guess) <= 1e-4:
                period_grids[t] = g
                break

            sen_guess = new_sen
            mezz_guess = new_mezz

    # ── Phase 3: Write back ONLY determined input cells ─────────────────────
    output = copy.deepcopy(cells)

    for t in range(6):
        g = period_grids[t]

        # Fix D&A sign in output (must be negative on IS)
        idx = cell_index.get((IS, 17, t))
        if idx is not None:
            output[idx]["value"] = -abs(_get(g, IS, 17))

        # Fix repayment signs in output (must be positive)
        for repay_row in [7, 18]:
            idx = cell_index.get((DS, repay_row, t))
            if idx is not None:
                output[idx]["value"] = abs(_get(g, DS, repay_row))

        # Retained Earnings — all periods
        idx = cell_index.get((BS, 40, t))
        if idx is not None:
            output[idx]["value"] = round(_get(g, BS, 40), 2)

        if t > 0:
            # Beginning Cash
            idx = cell_index.get((CF, 31, t))
            if idx is not None:
                output[idx]["value"] = round(_get(g, CF, 31), 2)

            # Senior Repay (positive)
            idx = cell_index.get((DS, 7, t))
            if idx is not None:
                output[idx]["value"] = round(abs(_get(g, DS, 7)), 2)

            # Mezz Repay (positive)
            idx = cell_index.get((DS, 18, t))
            if idx is not None:
                output[idx]["value"] = round(abs(_get(g, DS, 18)), 2)

    return output
