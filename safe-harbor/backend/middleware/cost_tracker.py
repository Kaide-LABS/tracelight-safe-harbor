from pydantic import BaseModel
from datetime import datetime

MODEL_PRICING = {
    "gpt-4o": {"input": 2.50 / 1_000_000, "output": 10.00 / 1_000_000},
    "gemini-2.0-flash": {"input": 0.10 / 1_000_000, "output": 0.40 / 1_000_000},
    "text-embedding-3-small": {"input": 0.02 / 1_000_000, "output": 0.0},
}

class TokenUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class APICostEntry(BaseModel):
    agent: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    timestamp: str

def calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    pricing = MODEL_PRICING.get(model, {"input": 0.0, "output": 0.0})
    cost = (prompt_tokens * pricing["input"]) + (completion_tokens * pricing["output"])
    return cost

def log_cost(agent: str, model: str, usage) -> APICostEntry:
    # usage could be dict or TokenUsage object
    if isinstance(usage, dict):
        p_tokens = usage.get("prompt_tokens", 0)
        c_tokens = usage.get("completion_tokens", 0)
        t_tokens = usage.get("total_tokens", 0)
    else:
        p_tokens = getattr(usage, "prompt_tokens", 0)
        c_tokens = getattr(usage, "completion_tokens", 0)
        t_tokens = getattr(usage, "total_tokens", 0)
        
    cost = calculate_cost(model, p_tokens, c_tokens)
    return APICostEntry(
        agent=agent,
        model=model,
        prompt_tokens=p_tokens,
        completion_tokens=c_tokens,
        total_tokens=t_tokens,
        estimated_cost_usd=cost,
        timestamp=datetime.utcnow().isoformat() + "Z"
    )
