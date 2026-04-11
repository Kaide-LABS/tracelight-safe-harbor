"""
Archetype Conformance Validator — READ-ONLY layer.

Extracts KPIs from the validated payload, compares against locked parameter
ranges for the selected scenario, and produces a scored conformance report.

Never modifies cells. Never blocks the pipeline. Pure observation.

Sources:
  - Guo, Hotchkiss & Song (2011), J. Finance 66(2)
  - Axelson, Jenkinson, Strömberg & Weisbach (2013), J. Finance 68(6)
  - Bain & Company (2024), Global Private Equity Report
  - RL Hulett (2024), Software & Tech-Enabled Services M&A Update Q3 2024
"""

import logging
from backend.models.schemas import SyntheticPayload

logger = logging.getLogger(__name__)


# ── Locked parameter ranges per archetype ──────────────────────────────
# Each tuple is (min, max). "entry" = first period, "exit" = last period.

ARCHETYPE_RANGES = {

    "general": {
        "revenue_base":             (250_000_000, 500_000_000),
        "revenue_growth_yoy":       (0.08, 0.12),
        "ebitda_margin_entry":      (0.18, 0.30),
        "ebitda_margin_exit":       (0.18, 0.30),
        "gross_margin":             (0.35, 0.45),
        "sga_pct_revenue":          (0.12, 0.18),
        "debt_to_ebitda_entry":     (4.0, 8.0),
        "senior_debt_entry":        (300_000_000, 500_000_000),
        "irr":                      (0.15, 0.30),
        "moic":                     (2.0, 3.5),
    },

    "distressed_turnaround": {
        "revenue_base":             (100_000_000, 400_000_000),
        "revenue_growth_entry":     (-0.05, 0.02),    # FY2021 (restructuring drag)
        "revenue_growth_exit":      (0.04, 0.10),      # FY2024-FY2025 (recovery)
        "ebitda_margin_entry":      (0.03, 0.08),
        "ebitda_margin_exit":       (0.14, 0.20),
        "margin_trajectory":        "expanding",        # must show upward arc
        "cogs_pct_revenue":         (0.70, 0.85),
        "sga_pct_revenue":          (0.15, 0.22),
        # NOTE: debt_to_ebitda_entry omitted — meaningless for distressed (entry EBITDA is
        # at trough levels; PE sponsors underwrite to normalized/exit EBITDA, not entry)
        "senior_debt_entry":        (400_000_000, 600_000_000),
        "irr":                      (0.20, 0.35),
        "moic":                     (2.5, 4.0),
    },

    "high_growth_tech": {
        "revenue_base":             (50_000_000, 250_000_000),
        "revenue_growth_yoy":       (0.18, 0.30),
        "ebitda_margin_entry":      (-0.05, 0.10),
        "ebitda_margin_exit":       (0.18, 0.28),
        "margin_trajectory":        "expanding",
        "gross_margin":             (0.65, 0.80),
        "sga_pct_revenue":          (0.35, 0.55),
        # NOTE: debt_to_ebitda_entry omitted — tech buyouts price on revenue multiples,
        # not EBITDA; entry EBITDA is near-zero so the ratio is structurally meaningless
        "senior_debt_entry":        (50_000_000, 200_000_000),
        "irr":                      (0.20, 0.30),
        "moic":                     (2.5, 3.5),
    },

    "mature_cashcow": {
        "revenue_base":             (250_000_000, 750_000_000),
        "revenue_growth_yoy":       (0.02, 0.05),
        "ebitda_margin_entry":      (0.16, 0.20),
        "ebitda_margin_exit":       (0.17, 0.22),
        "cogs_pct_revenue":         (0.58, 0.65),
        "sga_pct_revenue":          (0.12, 0.16),
        "debt_to_ebitda_entry":     (5.0, 7.0),
        "senior_debt_entry":        (400_000_000, 600_000_000),
        "irr":                      (0.15, 0.25),
        "moic":                     (2.0, 3.0),
    },
}

# Academic sources for each metric (shown in report)
METRIC_SOURCES = {
    "revenue_base":         "Convention (archetype sizing)",
    "revenue_growth_yoy":   "Bain PE Report 2024 p14,28",
    "revenue_growth_entry": "Guo et al. (2011) Table 6 Panel B",
    "revenue_growth_exit":  "Guo et al. (2011) Table 6 — IPO exit cohort recovery",
    "ebitda_margin_entry":  "Guo et al. (2011) Table 6 Panel B; RL Hulett Q3 2024 p7",
    "ebitda_margin_exit":   "Bain PE Report 2024 p28 (margin expansion decomposition)",
    "margin_trajectory":    "Guo et al. (2011) — industry-adjusted margin Δ",
    "gross_margin":         "RL Hulett Q3 2024 p7 (software gross margins 65-80%)",
    "cogs_pct_revenue":     "Implied by EBITDA margin bounds",
    "sga_pct_revenue":      "Convention (archetype cost structure)",
    "debt_to_ebitda_entry": "Axelson et al. (2013) Table III; Bain PE Report 2024 p16",
    "senior_debt_entry":    "Axelson et al. (2013) Table III",
    "irr":                  "Guo et al. (2011) Table 5",
    "moic":                 "Convention (PE return targets)",
}


def _build_lookup(payload: SyntheticPayload) -> dict:
    """Build {period: {header_lower: CellValue}} for fast lookup."""
    lookup = {}
    for cell in payload.cells:
        if cell.period not in lookup:
            lookup[cell.period] = {}
        lookup[cell.period][cell.header.lower().strip()] = cell
    return lookup


def _get_val(lookup: dict, period: str, keywords: list[str]):
    """Fuzzy match: returns first CellValue whose lowered header contains any keyword."""
    period_data = lookup.get(period, {})
    for h, cell in period_data.items():
        for kw in keywords:
            if kw in h:
                return cell
    return None


def _safe_float(cell) -> float | None:
    if cell is None:
        return None
    try:
        return float(cell.value)
    except (ValueError, TypeError):
        return None


def _check_range(actual: float | None, expected_range: tuple, tolerance: float = 0.15) -> str:
    """
    PASS  = within range
    WARN  = within tolerance band outside range (e.g., 15% slack)
    FAIL  = outside tolerance band
    """
    if actual is None:
        return "N/A"
    lo, hi = expected_range
    if lo <= actual <= hi:
        return "PASS"
    # Tolerance band
    band = (hi - lo) * tolerance
    if (lo - band) <= actual <= (hi + band):
        return "WARN"
    return "FAIL"


def validate_archetype_conformance(payload: SyntheticPayload, scenario_type: str = "general") -> dict:
    """
    Extract KPIs from validated payload and compare against archetype parameter ranges.
    Returns a structured conformance report. NEVER modifies the payload.
    """
    ranges = ARCHETYPE_RANGES.get(scenario_type, ARCHETYPE_RANGES["general"])
    lookup = _build_lookup(payload)
    all_periods = sorted(lookup.keys())

    # Filter to fiscal year periods (FY20XX / CY20XX) for KPI extraction
    fy_periods = [p for p in all_periods if p.startswith(("FY", "CY"))]
    periods = fy_periods if fy_periods else all_periods

    if not periods:
        return {"scenario_type": scenario_type, "overall_score": "0/0", "metrics": [], "kpi_summary": {}}

    entry_period = periods[0]
    exit_period = periods[-1]

    # ── Extract raw KPIs ──────────────────────────────────────────────
    revenue_by_period = {}
    ebitda_by_period = {}
    ebitda_margin_by_period = {}
    cogs_by_period = {}
    sga_by_period = {}

    for p in periods:
        rev_cell = _get_val(lookup, p, ["revenue", "sales", "total revenue"])
        ebitda_cell = _get_val(lookup, p, ["ebitda"])
        cogs_cell = _get_val(lookup, p, ["cogs", "cost of goods", "cost of revenue"])
        sga_cell = _get_val(lookup, p, ["sg&a", "selling", "sga"])
        rd_cell = _get_val(lookup, p, ["r&d", "research & development", "research and development"])
        other_opex_cell = _get_val(lookup, p, ["other operating", "other opex"])
        da_cell = _get_val(lookup, p, ["depreciation", "d&a", "depreciation & amortization"])

        rev = _safe_float(rev_cell)
        ebitda = _safe_float(ebitda_cell)
        cogs = _safe_float(cogs_cell)
        sga = _safe_float(sga_cell)
        rd = _safe_float(rd_cell) or 0
        other_opex = _safe_float(other_opex_cell) or 0
        da = _safe_float(da_cell) or 0

        # If EBITDA not directly available, compute from IS components:
        # EBITDA = Revenue - COGS - SG&A - R&D - Other OpEx (add back D&A if it was subtracted)
        if ebitda is None and rev and cogs is not None and sga is not None:
            ebitda = rev - cogs - sga - rd - other_opex
            logger.info(f"  [CONFORMANCE] Computed EBITDA for {p}: {rev} - {cogs} - {sga} - {rd} - {other_opex} = {ebitda}")

        if rev:
            revenue_by_period[p] = rev
        if ebitda:
            ebitda_by_period[p] = ebitda
        if rev and ebitda:
            ebitda_margin_by_period[p] = ebitda / rev
        if cogs:
            cogs_by_period[p] = cogs
        if sga:
            sga_by_period[p] = sga

    # Revenue growth rates
    growth_by_period = {}
    sorted_rev_periods = sorted(revenue_by_period.keys())
    for i in range(1, len(sorted_rev_periods)):
        prev_p = sorted_rev_periods[i - 1]
        curr_p = sorted_rev_periods[i]
        prev_rev = revenue_by_period[prev_p]
        curr_rev = revenue_by_period[curr_p]
        if prev_rev and prev_rev != 0:
            growth_by_period[curr_p] = (curr_rev - prev_rev) / prev_rev

    # Debt & leverage
    senior_debt_entry = _safe_float(_get_val(lookup, entry_period,
        ["senior debt", "senior beginning", "beginning balance"]))
    entry_ebitda = ebitda_by_period.get(entry_period)
    debt_to_ebitda_entry = None
    if senior_debt_entry and entry_ebitda and entry_ebitda > 0:
        # Only compute when EBITDA is positive — ratio is meaningless with negative EBITDA
        debt_to_ebitda_entry = senior_debt_entry / entry_ebitda

    # Returns — search ALL periods including "Value" (Returns Analysis uses non-FY periods)
    irr_val = None
    for p in all_periods:
        irr_val = _safe_float(_get_val(lookup, p, ["irr"]))
        if irr_val is not None:
            break

    moic_val = None
    for p in all_periods:
            moic_val = _safe_float(_get_val(lookup, p, ["moic"]))
            if moic_val is not None:
                break

    # ── Build metrics list ────────────────────────────────────────────
    metrics = []
    total = 0
    passed = 0

    def _add_metric(name: str, period: str, actual, range_key: str):
        nonlocal total, passed
        if range_key not in ranges:
            return
        expected = ranges[range_key]
        if isinstance(expected, str):
            # Qualitative check (e.g., margin_trajectory = "expanding")
            return
        status = _check_range(actual, expected)
        total += 1
        if status == "PASS":
            passed += 1
        elif status == "WARN":
            passed += 0.5
        metrics.append({
            "name": name,
            "period": period,
            "expected_range": list(expected),
            "actual": round(actual, 4) if actual is not None else None,
            "status": status,
            "source": METRIC_SOURCES.get(range_key, ""),
        })

    # Revenue base
    entry_rev = revenue_by_period.get(entry_period)
    _add_metric("Revenue (Entry)", entry_period, entry_rev, "revenue_base")

    # Revenue growth — handle archetype-specific entry/exit splits
    if "revenue_growth_entry" in ranges and len(sorted_rev_periods) > 1:
        # First growth period = entry growth
        first_growth_period = sorted_rev_periods[1] if len(sorted_rev_periods) > 1 else None
        if first_growth_period and first_growth_period in growth_by_period:
            _add_metric("Revenue Growth (Entry)", first_growth_period,
                        growth_by_period[first_growth_period], "revenue_growth_entry")
    if "revenue_growth_exit" in ranges and len(sorted_rev_periods) > 2:
        last_growth_period = sorted_rev_periods[-1]
        if last_growth_period in growth_by_period:
            _add_metric("Revenue Growth (Exit)", last_growth_period,
                        growth_by_period[last_growth_period], "revenue_growth_exit")
    if "revenue_growth_yoy" in ranges:
        # Check average growth across all periods
        if growth_by_period:
            avg_growth = sum(growth_by_period.values()) / len(growth_by_period)
            _add_metric("Avg Revenue Growth (YoY)", "All", avg_growth, "revenue_growth_yoy")

    # EBITDA margins
    entry_margin = ebitda_margin_by_period.get(entry_period)
    exit_margin = ebitda_margin_by_period.get(exit_period)
    _add_metric("EBITDA Margin (Entry)", entry_period, entry_margin, "ebitda_margin_entry")
    _add_metric("EBITDA Margin (Exit)", exit_period, exit_margin, "ebitda_margin_exit")

    # Margin trajectory check
    if "margin_trajectory" in ranges and ranges["margin_trajectory"] == "expanding":
        if entry_margin is not None and exit_margin is not None:
            expanding = exit_margin > entry_margin
            total += 1
            status = "PASS" if expanding else "FAIL"
            if expanding:
                passed += 1
            metrics.append({
                "name": "Margin Trajectory (Expanding)",
                "period": f"{entry_period} → {exit_period}",
                "expected_range": "exit > entry",
                "actual": f"{round(entry_margin, 4)} → {round(exit_margin, 4)}",
                "status": status,
                "source": METRIC_SOURCES.get("margin_trajectory", ""),
            })

    # Gross margin
    if "gross_margin" in ranges and entry_rev and entry_period in cogs_by_period:
        gross_margin = (entry_rev - cogs_by_period[entry_period]) / entry_rev
        _add_metric("Gross Margin (Entry)", entry_period, gross_margin, "gross_margin")

    # COGS % of revenue
    if "cogs_pct_revenue" in ranges and entry_rev and entry_period in cogs_by_period:
        cogs_pct = cogs_by_period[entry_period] / entry_rev
        _add_metric("COGS % Revenue (Entry)", entry_period, cogs_pct, "cogs_pct_revenue")

    # SG&A % of revenue
    if "sga_pct_revenue" in ranges and entry_rev and entry_period in sga_by_period:
        sga_pct = sga_by_period[entry_period] / entry_rev
        _add_metric("SG&A % Revenue (Entry)", entry_period, sga_pct, "sga_pct_revenue")

    # Leverage
    _add_metric("Debt/EBITDA (Entry)", entry_period, debt_to_ebitda_entry, "debt_to_ebitda_entry")
    _add_metric("Senior Debt (Entry)", entry_period, senior_debt_entry, "senior_debt_entry")

    # Returns
    _add_metric("IRR", "Exit", irr_val, "irr")
    _add_metric("MOIC", "Exit", moic_val, "moic")

    # ── Overall score ─────────────────────────────────────────────────
    score_str = f"{passed}/{total}" if total > 0 else "0/0"
    pct = (passed / total * 100) if total > 0 else 0
    if pct >= 80:
        overall = f"{score_str} PASS"
    elif pct >= 60:
        overall = f"{score_str} WARN"
    else:
        overall = f"{score_str} FAIL"

    report = {
        "scenario_type": scenario_type,
        "overall_score": overall,
        "pass_rate_pct": round(pct, 1),
        "metrics": metrics,
        "kpi_summary": {
            "revenue_by_period": {k: round(v) for k, v in revenue_by_period.items()},
            "ebitda_by_period": {k: round(v) for k, v in ebitda_by_period.items()},
            "ebitda_margin_by_period": {k: round(v, 4) for k, v in ebitda_margin_by_period.items()},
            "revenue_growth_by_period": {k: round(v, 4) for k, v in growth_by_period.items()},
            "debt_to_ebitda_entry": round(debt_to_ebitda_entry, 2) if debt_to_ebitda_entry else None,
            "senior_debt_entry": round(senior_debt_entry) if senior_debt_entry else None,
            "irr": round(irr_val, 4) if irr_val else None,
            "moic": round(moic_val, 2) if moic_val else None,
        }
    }

    logger.info(f"[CONFORMANCE] Scenario={scenario_type} | Score={overall}")
    for m in metrics:
        logger.info(f"  {m['status']:4s} | {m['name']}: actual={m['actual']}, expected={m['expected_range']}")

    return report
