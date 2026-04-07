import pytest
from backend.middleware.cost_tracker import calculate_cost, log_cost

def test_calculate_cost():
    # gpt-4o: 2.50 / 1M prompt, 10.00 / 1M completion
    # 3000 * 2.5/1M + 5000 * 10/1M = 0.0075 + 0.05 = 0.0575
    cost = calculate_cost("gpt-4o", 3000, 5000)
    assert abs(cost - 0.0575) < 1e-6

def test_calculate_cost_gemini():
    # gemini-2.0-flash: 0.10 / 1M prompt, 0.40 / 1M completion
    # 4000 * 0.1/1M + 2000 * 0.4/1M = 0.0004 + 0.0008 = 0.0012
    cost = calculate_cost("gemini-2.0-flash", 4000, 2000)
    assert abs(cost - 0.0012) < 1e-6

def test_log_cost():
    usage = {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500}
    entry = log_cost("agent", "gpt-4o", usage)
    assert entry.agent == "agent"
    assert entry.model == "gpt-4o"
    assert entry.prompt_tokens == 1000
    assert entry.completion_tokens == 500
    assert entry.total_tokens == 1500
    assert entry.estimated_cost_usd > 0
    assert entry.timestamp is not None
