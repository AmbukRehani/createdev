from app.agents.llm import LLMParseError
from app.agents.nodes.understand import Understanding, UnderstandNode
from app.core.config import get_settings
from app.repositories.query_template_repository import QueryTemplateRepository
from tests.conftest import FakeLLM, make_state


async def test_understand_low_confidence_routes_to_clarify(db_session):
    fake_llm = FakeLLM(
        {"understand": Understanding(intent="top_sources_by_hires", params={}, confidence=0.2)}
    )
    node = UnderstandNode(fake_llm, QueryTemplateRepository(db_session))

    delta = await node(make_state(question="vague question"))

    # understand() only ever returns intent/params/confidence — it makes
    # no routing decision itself. "Template is not selected" here means:
    # the delta contains nothing that would cause execution to proceed
    # (no route/answer/rows key), and the confidence it returned is below
    # the threshold the gate checks.
    assert set(delta.keys()) == {"intent", "params", "confidence"}
    assert delta["confidence"] == 0.2
    assert delta["confidence"] < get_settings().confidence_threshold


async def test_understand_malformed_output_retries_once_then_clarifies(db_session):
    # Represents llm.structured() having already retried once internally
    # (that retry loop is llm.py's own responsibility, tested elsewhere)
    # and still failing to produce valid JSON.
    fake_llm = FakeLLM({"understand": LLMParseError("still not valid JSON after retry")})
    node = UnderstandNode(fake_llm, QueryTemplateRepository(db_session))

    delta = await node(make_state(question="???"))

    assert delta == {"intent": None, "params": {}, "confidence": 0.0}
    assert delta["confidence"] < get_settings().confidence_threshold
