from app.agents.graph import build_graph
from app.agents.nodes.understand import Understanding
from app.core.config import get_settings
from app.repositories.query_template_repository import QueryTemplateRepository
from tests.conftest import FakeLLM, make_state


async def test_graph_conditional_edge_skips_respond_when_confidence_below_threshold(db_session):
    settings = get_settings()
    assert 0.1 < settings.confidence_threshold  # sanity: this really is "low"

    # No "respond" entry configured — if the conditional edge ever routed
    # there, FakeLLM would raise and this test would fail loudly.
    fake_llm = FakeLLM(
        {"understand": Understanding(intent="top_sources_by_hires", params={}, confidence=0.1)}
    )
    template_repo = QueryTemplateRepository(db_session)
    graph = build_graph(fake_llm, template_repo, db_session, settings)

    final_state = await graph.ainvoke(make_state(question="anything"))

    assert final_state["route"] == "clarified"
    assert [call[0] for call in fake_llm.calls] == ["understand"]
