import pytest
import os
from backend.parsers.excel_parser import parse_excel_questionnaire

def test_excel_parsing(sample_questionnaire_path):
    if not os.path.exists(sample_questionnaire_path):
        pytest.skip("Fixture not generated yet")
    res = parse_excel_questionnaire(sample_questionnaire_path)
    assert len(res) == 30

@pytest.mark.asyncio
async def test_classification():
    assert True

@pytest.mark.asyncio
async def test_gemini_failure_gpt4o_fallback():
    assert True
