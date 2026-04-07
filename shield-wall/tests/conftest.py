import pytest
from backend.config import get_settings
from backend.telemetry.mock_adapter import MockTelemetryAdapter

@pytest.fixture
def settings():
    return get_settings()

@pytest.fixture
def mock_adapter():
    return MockTelemetryAdapter()

@pytest.fixture
def sample_questionnaire_path():
    return "tests/fixtures/sample_questionnaire.xlsx"
