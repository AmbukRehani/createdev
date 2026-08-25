from app.agents.nodes.respond import RespondNode
from app.core.config import get_settings
from app.repositories.query_template_repository import QueryTemplateRepository
from tests.conftest import FakeLLM, make_state


async def test_respond_param_value_not_in_data_clarifies_with_valid_options(db_session):
    # FakeLLM configured with no "respond" entry — if respond ever tried
    # to call the LLM here, it would raise loudly and fail this test.
    fake_llm = FakeLLM({})
    node = RespondNode(fake_llm, QueryTemplateRepository(db_session), db_session, get_settings())

    delta = await node(
        make_state(
            question="time to hire in Enginering",
            intent="avg_time_to_hire_by_dept",
            params={"department": "Enginering", "year": 2025},
            confidence=0.95,
        )
    )

    assert delta["route"] == "clarified"
    assert "Enginering" in delta["clarification"]
    assert "Engineering" in delta["clarification"]  # a real valid option is listed
    assert fake_llm.calls == []


async def test_respond_empty_result_set_returns_no_matching_records(db_session):
    fake_llm = FakeLLM({})  # must never be called for an empty result
    node = RespondNode(fake_llm, QueryTemplateRepository(db_session), db_session, get_settings())

    # A valid department + a year outside the seeded 2024-2025 window —
    # guaranteed empty by construction (app/scripts/seed_sample_data.py),
    # not dependent on the random seed's exact distribution.
    delta = await node(
        make_state(
            question="average time to hire in Engineering in 2000",
            intent="avg_time_to_hire_by_dept",
            params={"department": "Engineering", "year": 2000},
            confidence=0.95,
        )
    )

    assert delta["route"] == "answer"
    assert delta["answer"] == "No matching records found."
    assert delta["rows"] == []
    assert fake_llm.calls == []  # never invented content — no LLM call at all
