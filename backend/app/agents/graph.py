"""DESIGN §3: understand -> conditional edge -> respond | clarify -> END.

Gate: confidence < settings.confidence_threshold routes to clarify. Built
fresh per request (nodes close over request-scoped session/budget/llm —
no shared graph instance across concurrent requests).
"""
import structlog
from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm import LLMClient
from app.agents.logging import log_node_complete
from app.agents.nodes.respond import RespondNode
from app.agents.nodes.understand import UnderstandNode
from app.agents.state import GraphState
from app.core.config import Settings
from app.repositories.query_template_repository import QueryTemplateRepository

logger = structlog.get_logger()


class ClarifyNode:
    """Reached only from the low-confidence edge off `understand`.
    respond.py's own bad-param-value short-circuit produces the same
    route="clarified" state shape directly, without traversing here."""

    def __init__(self, template_repo: QueryTemplateRepository) -> None:
        self._template_repo = template_repo

    async def __call__(self, state: GraphState) -> dict:
        templates = await self._template_repo.list_enabled()
        options = ", ".join(sorted(t.intent for t in templates))
        clarification = (
            "I'm not confident enough to answer that. Could you rephrase, "
            f"or ask about one of: {options}?"
        )
        logger.debug("clarify_answer", clarification=clarification)
        log_node_complete("clarify", route="clarified", confidence=state["confidence"])
        return {"route": "clarified", "clarification": clarification}


def _route_after_understand(settings: Settings):
    def route(state: GraphState) -> str:
        decision = "clarify" if state["confidence"] < settings.confidence_threshold else "respond"
        logger.info(
            "route_decision",
            decision=decision,
            confidence=state["confidence"],
            threshold=settings.confidence_threshold,
        )
        return decision

    return route


def build_graph(
    llm: LLMClient,
    template_repo: QueryTemplateRepository,
    session: AsyncSession,
    settings: Settings,
):
    graph = StateGraph(GraphState)

    graph.add_node("understand", UnderstandNode(llm, template_repo))
    graph.add_node("respond", RespondNode(llm, template_repo, session, settings))
    graph.add_node("clarify", ClarifyNode(template_repo))

    graph.set_entry_point("understand")
    graph.add_conditional_edges(
        "understand",
        _route_after_understand(settings),
        {"respond": "respond", "clarify": "clarify"},
    )
    graph.add_edge("respond", END)
    graph.add_edge("clarify", END)

    return graph.compile()
