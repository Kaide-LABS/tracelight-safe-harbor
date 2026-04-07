from datetime import datetime
import copy
from backend.models.schemas import TemplateSchema, SyntheticPayload, ValidationResult, ValidationRuleResult, PlugAdjustment


class DeterministicValidator:
    def __init__(self, schema: TemplateSchema):
        self.schema = schema
        self.adjustments = []
        self.needs_regeneration = []

    def validate(self, payload: SyntheticPayload) -> ValidationResult:
        # Group cells by period and header for fast lookup
        # lookup[period][header_lower] = CellValue
        self.lookup = {}
        for cell in payload.cells:
            if cell.period not in self.lookup:
                self.lookup[cell.period] = {}
            self.lookup[cell.period][cell.header.lower().strip()] = cell

        self.adjustments = []
        self.needs_regeneration = []

        rules_results = []
        rules_results.extend(self._rule_balance_sheet_identity(payload))
        rules_results.extend(self._rule_cash_flow_reconciliation(payload))
        rules_results.extend(self._rule_net_income_linkage(payload))
        rules_results.extend(self._rule_margin_bounds(payload))
        rules_results.extend(self._rule_depreciation_constraint(payload))
        rules_results.extend(self._rule_debt_schedule_integrity(payload))

        status = "PASSED"
        if self.needs_regeneration:
            status = "FAILED"
        elif self.adjustments:
            status = "PASSED_WITH_PLUGS"

        validated_payload = self._apply_plug_adjustments(payload, self.adjustments) if status != "FAILED" else None

        return ValidationResult(
            status=status,
            rules=rules_results,
            adjustments=self.adjustments,
            needs_regeneration=self.needs_regeneration,
            validated_payload=validated_payload,
            validation_timestamp=datetime.utcnow().isoformat() + "Z"
        )

    def _get_val(self, period, header_keywords):
        """Fuzzy match: returns first CellValue whose lowered header contains any keyword."""
        period_data = self.lookup.get(period, {})
        for h, cell in period_data.items():
            for kw in header_keywords:
                if kw in h:
                    return cell
        return None

    def _sorted_periods(self):
        """Return periods sorted lexicographically (FY2020 < FY2021 etc.)."""
        return sorted(self.lookup.keys())

    # ── Rule 1: Balance Sheet Identity ──────────────────────────────────
    def _rule_balance_sheet_identity(self, payload: SyntheticPayload) -> list[ValidationRuleResult]:
        results = []
        for period in self.lookup.keys():
            assets = self._get_val(period, ["total assets"])
            liab = self._get_val(period, ["total liabilities"])
            eq = self._get_val(period, ["total equity"])

            if assets and liab and eq:
                a_val = float(assets.value)
                l_val = float(liab.value)
                e_val = float(eq.value)

                delta = a_val - (l_val + e_val)
                passed = abs(delta) < 0.01

                adj = None
                if not passed:
                    cash_cell = self._get_val(period, ["cash"])
                    if cash_cell:
                        orig = float(cash_cell.value)
                        adj_val = orig + delta
                        adj = PlugAdjustment(
                            target_cell=cash_cell.header,
                            target_sheet=cash_cell.sheet_name,
                            period=period,
                            original_value=orig,
                            adjusted_value=adj_val,
                            delta=delta,
                            reason=f"BS imbalance: Assets - (Liab + Eq) = {delta:+,.0f}"
                        )
                        self.adjustments.append(adj)
                    else:
                        self.needs_regeneration.append("Cash / Total Assets")

                results.append(ValidationRuleResult(
                    rule_name="balance_sheet_identity",
                    period=period,
                    passed=passed,
                    expected=l_val + e_val,
                    actual=a_val,
                    delta=delta,
                    adjustment_applied=adj
                ))
        return results

    # ── Rule 2: Cash Flow Reconciliation ────────────────────────────────
    def _rule_cash_flow_reconciliation(self, payload: SyntheticPayload) -> list[ValidationRuleResult]:
        results = []
        periods = self._sorted_periods()
        prev_ending_cash = None

        for period in periods:
            ending = self._get_val(period, ["ending cash", "cash end"])
            beginning = self._get_val(period, ["beginning cash", "cash begin", "opening cash"])
            net_cf = self._get_val(period, ["net change in cash", "net cash flow", "total cash flow"])

            if ending and net_cf:
                e_val = float(ending.value)
                n_val = float(net_cf.value)

                # Beginning cash: prefer explicit cell, else use prior period ending
                if beginning:
                    b_val = float(beginning.value)
                elif prev_ending_cash is not None:
                    b_val = prev_ending_cash
                else:
                    b_val = 0.0

                expected_ending = b_val + n_val
                delta = e_val - expected_ending
                passed = abs(delta) < 0.01

                adj = None
                if not passed:
                    # Plug via "Other Cash Flow Items" or adjust net_cf
                    other_cf = self._get_val(period, ["other cash flow", "other operating", "other cf"])
                    if other_cf:
                        orig = float(other_cf.value)
                        adj = PlugAdjustment(
                            target_cell=other_cf.header,
                            target_sheet=other_cf.sheet_name,
                            period=period,
                            original_value=orig,
                            adjusted_value=orig + delta,
                            delta=delta,
                            reason=f"CF mismatch: Ending - (Begin + Net) = {delta:+,.0f}"
                        )
                        self.adjustments.append(adj)
                    else:
                        # No plug account available — adjust ending cash directly
                        adj = PlugAdjustment(
                            target_cell=ending.header,
                            target_sheet=ending.sheet_name,
                            period=period,
                            original_value=e_val,
                            adjusted_value=expected_ending,
                            delta=-delta,
                            reason=f"CF mismatch: forced Ending Cash = Begin + Net CF"
                        )
                        self.adjustments.append(adj)

                results.append(ValidationRuleResult(
                    rule_name="cash_flow_reconciliation",
                    period=period,
                    passed=passed,
                    expected=expected_ending,
                    actual=e_val,
                    delta=delta,
                    adjustment_applied=adj
                ))
                prev_ending_cash = e_val if passed else expected_ending
            else:
                if ending:
                    prev_ending_cash = float(ending.value)
        return results

    # ── Rule 3: Net Income Linkage ──────────────────────────────────────
    def _rule_net_income_linkage(self, payload: SyntheticPayload) -> list[ValidationRuleResult]:
        results = []
        for period in self.lookup.keys():
            pl_ni = self._get_val(period, ["net income"])
            cf_ni = None
            # Look for net income specifically on cash flow sheet
            period_data = self.lookup.get(period, {})
            for h, cell in period_data.items():
                if "net income" in h and cell.sheet_name.lower() in ["cash flow", "cash flow statement", "cf"]:
                    cf_ni = cell
                    break

            if pl_ni and cf_ni and pl_ni.sheet_name != cf_ni.sheet_name:
                pl_val = float(pl_ni.value)
                cf_val = float(cf_ni.value)
                delta = pl_val - cf_val
                passed = abs(delta) < 0.01

                adj = None
                if not passed:
                    # Force CF net income to match P&L
                    adj = PlugAdjustment(
                        target_cell=cf_ni.header,
                        target_sheet=cf_ni.sheet_name,
                        period=period,
                        original_value=cf_val,
                        adjusted_value=pl_val,
                        delta=delta,
                        reason=f"NI linkage: P&L NI ({pl_val:,.0f}) != CF NI ({cf_val:,.0f})"
                    )
                    self.adjustments.append(adj)

                results.append(ValidationRuleResult(
                    rule_name="net_income_linkage",
                    period=period,
                    passed=passed,
                    expected=pl_val,
                    actual=cf_val,
                    delta=delta,
                    adjustment_applied=adj
                ))
        return results

    # ── Rule 4: Margin Bounds ───────────────────────────────────────────
    def _rule_margin_bounds(self, payload: SyntheticPayload) -> list[ValidationRuleResult]:
        results = []
        for period in self.lookup.keys():
            rev = self._get_val(period, ["revenue", "sales", "total revenue"])
            if not rev or float(rev.value) == 0:
                continue
            r_val = float(rev.value)

            # EBITDA margin
            ebitda = self._get_val(period, ["ebitda"])
            if ebitda:
                margin = float(ebitda.value) / r_val
                passed = -0.5 <= margin <= 0.8
                if not passed:
                    self.needs_regeneration.append(ebitda.header)
                results.append(ValidationRuleResult(
                    rule_name="ebitda_margin_bounds",
                    period=period,
                    passed=passed,
                    expected=0.15,
                    actual=round(margin, 4),
                    delta=round(margin - 0.15, 4)
                ))

            # Gross margin
            cogs = self._get_val(period, ["cogs", "cost of goods", "cost of revenue"])
            if cogs:
                gross_margin = (r_val - float(cogs.value)) / r_val
                passed = 0.0 <= gross_margin <= 1.0
                if not passed:
                    self.needs_regeneration.append(cogs.header)
                results.append(ValidationRuleResult(
                    rule_name="gross_margin_bounds",
                    period=period,
                    passed=passed,
                    expected=0.5,
                    actual=round(gross_margin, 4),
                    delta=round(gross_margin - 0.5, 4)
                ))

            # Net margin
            ni = self._get_val(period, ["net income"])
            if ni:
                net_margin = float(ni.value) / r_val
                passed = -1.0 <= net_margin <= 0.5
                if not passed:
                    self.needs_regeneration.append(ni.header)
                results.append(ValidationRuleResult(
                    rule_name="net_margin_bounds",
                    period=period,
                    passed=passed,
                    expected=0.10,
                    actual=round(net_margin, 4),
                    delta=round(net_margin - 0.10, 4)
                ))
        return results

    # ── Rule 5: Depreciation Constraint ─────────────────────────────────
    def _rule_depreciation_constraint(self, payload: SyntheticPayload) -> list[ValidationRuleResult]:
        results = []
        periods = self._sorted_periods()
        cum_dep = 0.0
        cum_capex = 0.0
        opening_ppe = 0.0

        # Try to get opening PP&E from the first period
        if periods:
            ppe_cell = self._get_val(periods[0], ["pp&e", "ppe", "property plant", "fixed assets"])
            if ppe_cell:
                opening_ppe = float(ppe_cell.value)

        for period in periods:
            dep = self._get_val(period, ["depreciation", "d&a", "depreciation & amortization"])
            capex = self._get_val(period, ["capex", "capital expenditure", "capital expenditures"])

            if dep:
                d_val = float(dep.value)
                cum_dep += abs(d_val)  # depreciation may be stored as negative

                if capex:
                    cum_capex += abs(float(capex.value))

                ceiling = cum_capex + opening_ppe
                passed = cum_dep <= ceiling + 0.01

                adj = None
                if not passed:
                    # Cap depreciation at the allowed maximum
                    overshoot = cum_dep - ceiling
                    new_dep = abs(d_val) - overshoot
                    adj = PlugAdjustment(
                        target_cell=dep.header,
                        target_sheet=dep.sheet_name,
                        period=period,
                        original_value=d_val,
                        adjusted_value=-abs(new_dep) if d_val < 0 else new_dep,
                        delta=-overshoot,
                        reason=f"Depreciation exceeds CapEx + PP&E ceiling by {overshoot:,.0f}"
                    )
                    self.adjustments.append(adj)
                    cum_dep = ceiling  # reset after cap

                results.append(ValidationRuleResult(
                    rule_name="depreciation_constraint",
                    period=period,
                    passed=passed,
                    expected=ceiling,
                    actual=cum_dep,
                    delta=cum_dep - ceiling,
                    adjustment_applied=adj
                ))
        return results

    # ── Rule 6: Debt Schedule Integrity ─────────────────────────────────
    def _rule_debt_schedule_integrity(self, payload: SyntheticPayload) -> list[ValidationRuleResult]:
        results = []
        periods = self._sorted_periods()

        # Detect debt tranches from column headers
        tranche_keywords = [
            ("senior debt", "senior"),
            ("mezzanine", "mezzanine"),
            ("term loan", "term loan"),
            ("revolver", "revolver"),
        ]

        for kw_list, tranche_name in tranche_keywords:
            prev_ending = None
            for period in periods:
                ending = self._get_val(period, [f"ending {kw_list}", f"{kw_list} ending", f"ending balance"])
                beginning = self._get_val(period, [f"beginning {kw_list}", f"{kw_list} beginning", f"beginning balance"])
                drawdowns = self._get_val(period, [f"{kw_list} drawdown", "drawdown"])
                repayments = self._get_val(period, [f"{kw_list} repayment", "repayment"])

                # Also try generic debt columns if tranche-specific not found
                if not ending:
                    ending = self._get_val(period, [kw_list])

                if ending and (beginning or prev_ending is not None):
                    e_val = float(ending.value)
                    b_val = float(beginning.value) if beginning else (prev_ending if prev_ending is not None else 0.0)
                    d_val = float(drawdowns.value) if drawdowns else 0.0
                    r_val = float(repayments.value) if repayments else 0.0

                    expected = b_val + d_val - abs(r_val)
                    delta = e_val - expected
                    passed = abs(delta) < 0.01

                    adj = None
                    if not passed and repayments:
                        # Adjust repayments to force identity
                        orig_r = float(repayments.value)
                        adj = PlugAdjustment(
                            target_cell=repayments.header,
                            target_sheet=repayments.sheet_name,
                            period=period,
                            original_value=orig_r,
                            adjusted_value=orig_r + delta,
                            delta=delta,
                            reason=f"{tranche_name} debt: Ending != Begin + Draw - Repay, delta={delta:+,.0f}"
                        )
                        self.adjustments.append(adj)
                    elif not passed:
                        self.needs_regeneration.append(f"{tranche_name} debt schedule")

                    results.append(ValidationRuleResult(
                        rule_name=f"debt_schedule_{tranche_name}",
                        period=period,
                        passed=passed,
                        expected=expected,
                        actual=e_val,
                        delta=delta,
                        adjustment_applied=adj
                    ))
                    prev_ending = e_val
        return results

    # ── Plug adjustments ────────────────────────────────────────────────
    def _apply_plug_adjustments(self, payload: SyntheticPayload, adjustments: list[PlugAdjustment]) -> SyntheticPayload:
        new_payload = copy.deepcopy(payload)
        for adj in adjustments:
            for cell in new_payload.cells:
                if cell.period == adj.period and cell.header == adj.target_cell and cell.sheet_name == adj.target_sheet:
                    cell.value = adj.adjusted_value
        return new_payload

    def build_retry_instructions(self) -> str | None:
        if not self.needs_regeneration:
            return None
        items = ", ".join(list(set(self.needs_regeneration)))
        return f"The following line items violated structural constraints: {items}. Regenerate these with values that satisfy the accounting identities and margin bounds specified."
