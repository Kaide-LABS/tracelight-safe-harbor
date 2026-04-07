import pytest
import os
from backend.excel_io.parser import parse_template, TemplateNotEmptyError

def test_parse_lbo_template(sample_lbo_path):
    if not os.path.exists(sample_lbo_path):
        pytest.skip("Template not generated yet")
    result = parse_template(sample_lbo_path)
    assert len(result["sheets"]) >= 3
    assert result["total_input_cells"] > 0
    assert len(result["inter_sheet_refs"]) > 0

def test_parse_empty_check():
    # Placeholder for TemplateNotEmptyError check
    assert True

def test_parse_formula_detection():
    # Placeholder for formula parsing check
    assert True
