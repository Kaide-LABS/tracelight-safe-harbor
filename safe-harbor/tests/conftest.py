import pytest
from backend.config import get_settings

@pytest.fixture
def settings():
    return get_settings()

@pytest.fixture
def sample_lbo_path():
    return "templates/lbo_template.xlsx"
