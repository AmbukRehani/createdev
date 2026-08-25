from uuid import uuid4

import pytest

import app.agents.llm as llm_mod
from app.agents.llm import LLMClient
from app.agents.nodes.understand import Understanding
from app.observability.cost import BudgetExceeded, RequestBudget


async def test_cost_budget_exceeded_raises_before_call(monkeypatch):
    budget = RequestBudget(limit_usd=0.01, trace_id=uuid4())
    budget.add(
        node="understand", model="gpt-4o-mini", prompt_tokens=100,
        completion_tokens=50, cost_usd=0.02, latency_ms=10,
    )
    assert budget.total_usd >= budget.limit_usd  # already over

    def explode(*args, **kwargs):
        raise AssertionError("ChatOpenAI must never be constructed once budget is exceeded")

    monkeypatch.setattr(llm_mod, "ChatOpenAI", explode)

    client = LLMClient(budget)

    with pytest.raises(BudgetExceeded):
        await client.structured(task="understand", prompt="x", schema=Understanding, max_tokens=10)
