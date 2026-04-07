from datetime import datetime
import json
import copy
from backend.models.schemas import TemplateSchema, SyntheticPayload, ValidationResult, ValidationRuleResult, PlugAdjustment

class DeterministicValidator:
    def __init__(self, schema: TemplateSchema):
        self.schema = schema
        self.adjustments = []
        self.needs_regeneration = []
        
    def validate(self, payload: SyntheticPayload) -> ValidationResult:
        # Group cells by period and header for fast lookup
        # lookup[period][header] = CellValue
        self.lookup = {}
        for cell in payload.cells:
            if cell.period not in self.lookup:
                self.lookup[cell.period] = {}
            # case insensitive fuzzy lookup
            self.lookup[cell.period][cell.header.lower().strip()] = cell

        self.adjustments = []
        self.needs_regeneration = []
        
        rules_results = []
        rules_results.extend(self._rule_balance_sheet_identity(payload))
        rules_results.extend(self._rule_margin_bounds(payload))
        
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
        period_data = self.lookup.get(period, {})
        for h, cell in period_data.items():
            for kw in header_keywords:
                if kw in h:
                    return cell
        return None

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
                        # Fallback if no cash cell found
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

    def _rule_margin_bounds(self, payload: SyntheticPayload) -> list[ValidationRuleResult]:
        results = []
        for period in self.lookup.keys():
            rev = self._get_val(period, ["revenue", "sales"])
            ebitda = self._get_val(period, ["ebitda"])
            
            if rev and ebitda and float(rev.value) != 0:
                r_val = float(rev.value)
                e_val = float(ebitda.value)
                margin = e_val / r_val
                
                passed = -0.5 <= margin <= 0.8
                if not passed:
                    self.needs_regeneration.append(ebitda.header)
                    
                results.append(ValidationRuleResult(
                    rule_name="ebitda_margin_bounds",
                    period=period,
                    passed=passed,
                    expected=0.15,
                    actual=margin,
                    delta=margin - 0.15
                ))
        return results

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
        return f"The following line items violated structural margin constraints or caused unpluggable balance sheet errors: {items}."
