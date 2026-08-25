from app.agents.llm import _cost_usd


def test_llm_unknown_model_id_returns_zero_cost_no_exception():
    cost = _cost_usd("some-unreleased-model", prompt_tokens=1000, completion_tokens=1000)
    assert cost == 0.0
