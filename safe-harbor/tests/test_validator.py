import pytest
from backend.agents.validator import DeterministicValidator
from backend.models.schemas import (
    TemplateSchema, SheetSchema, ColumnSchema, ColumnConstraints,
    InterSheetReference, SyntheticPayload, CellValue, GenerationMetadata, TokenUsage,
)


def _make_schema():
    return TemplateSchema(
        model_type="LBO", industry="General", currency="USD",
        sheets=[
            SheetSchema(name="Income Statement", columns=[]),
            SheetSchema(name="Balance Sheet", columns=[]),
            SheetSchema(name="Cash Flow", columns=[]),
        ],
        inter_sheet_refs=[], total_input_cells=10,
    )


def _make_metadata():
    return GenerationMetadata(
        model_used="test", temperature=0.3,
        token_usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        generation_time_ms=0,
    )


def _make_payload(cells):
    return SyntheticPayload(
        model_type="LBO", industry="General", currency="USD",
        cells=cells, generation_metadata=_make_metadata(),
    )


def test_bs_balanced():
    cells = [
        CellValue(sheet_name="Balance Sheet", cell_ref="B2", header="Cash", period="FY2022", value=100),
        CellValue(sheet_name="Balance Sheet", cell_ref="B10", header="Total Assets", period="FY2022", value=500),
        CellValue(sheet_name="Balance Sheet", cell_ref="B17", header="Total Liabilities", period="FY2022", value=300),
        CellValue(sheet_name="Balance Sheet", cell_ref="B20", header="Total Equity", period="FY2022", value=200),
    ]
    v = DeterministicValidator(_make_schema())
    result = v.validate(_make_payload(cells))
    assert result.status == "PASSED"
    bs_rules = [r for r in result.rules if r.rule_name == "balance_sheet_identity"]
    assert len(bs_rules) == 1
    assert bs_rules[0].passed is True


def test_bs_imbalanced_plug():
    cells = [
        CellValue(sheet_name="Balance Sheet", cell_ref="B2", header="Cash", period="FY2022", value=100),
        CellValue(sheet_name="Balance Sheet", cell_ref="B10", header="Total Assets", period="FY2022", value=510),
        CellValue(sheet_name="Balance Sheet", cell_ref="B17", header="Total Liabilities", period="FY2022", value=300),
        CellValue(sheet_name="Balance Sheet", cell_ref="B20", header="Total Equity", period="FY2022", value=200),
    ]
    v = DeterministicValidator(_make_schema())
    result = v.validate(_make_payload(cells))
    assert result.status == "PASSED_WITH_PLUGS"
    assert len(result.adjustments) >= 1
    adj = result.adjustments[0]
    assert adj.target_cell == "Cash"
    assert adj.delta == pytest.approx(10.0)


def test_cf_reconciliation():
    cells = [
        CellValue(sheet_name="Cash Flow", cell_ref="B14", header="Ending Cash", period="FY2022", value=200),
        CellValue(sheet_name="Cash Flow", cell_ref="B13", header="Beginning Cash", period="FY2022", value=100),
        CellValue(sheet_name="Cash Flow", cell_ref="B12", header="Net Change in Cash", period="FY2022", value=50),
    ]
    v = DeterministicValidator(_make_schema())
    result = v.validate(_make_payload(cells))
    # Ending (200) != Beginning (100) + Net (50) = 150, delta = 50
    cf_rules = [r for r in result.rules if r.rule_name == "cash_flow_reconciliation"]
    assert len(cf_rules) >= 1
    assert cf_rules[0].passed is False


def test_margin_violation():
    cells = [
        CellValue(sheet_name="Income Statement", cell_ref="B2", header="Revenue", period="FY2022", value=100),
        CellValue(sheet_name="Income Statement", cell_ref="B6", header="EBITDA", period="FY2022", value=90),
    ]
    v = DeterministicValidator(_make_schema())
    result = v.validate(_make_payload(cells))
    assert result.status == "FAILED"
    assert "EBITDA" in result.needs_regeneration


def test_all_rules_pass():
    cells = [
        CellValue(sheet_name="Balance Sheet", cell_ref="B2", header="Cash", period="FY2022", value=100),
        CellValue(sheet_name="Balance Sheet", cell_ref="B10", header="Total Assets", period="FY2022", value=500),
        CellValue(sheet_name="Balance Sheet", cell_ref="B17", header="Total Liabilities", period="FY2022", value=300),
        CellValue(sheet_name="Balance Sheet", cell_ref="B20", header="Total Equity", period="FY2022", value=200),
        CellValue(sheet_name="Income Statement", cell_ref="B2", header="Revenue", period="FY2022", value=100),
        CellValue(sheet_name="Income Statement", cell_ref="B6", header="EBITDA", period="FY2022", value=20),
    ]
    v = DeterministicValidator(_make_schema())
    result = v.validate(_make_payload(cells))
    assert result.status == "PASSED"
    assert len(result.adjustments) == 0
    assert len(result.needs_regeneration) == 0
