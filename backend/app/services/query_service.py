"""Orchestrates the two-node LangGraph (DESIGN §3) for POST /api/v1/query:
builds per-request LLM client + budget, runs the graph, persists
audit_trail (every route, including failures) and llm_usage, and
assembles the response. The API contract (QueryRequest/QueryResponse) is
unchanged — only this internal wiring is new.
"""
import time
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import build_graph
from app.agents.llm import LLMClient
from app.agents.state import GraphState
from app.core.config import get_settings
from app.observability.cost import RequestBudget
from app.repositories.audit_trail_repository import AuditTrailRepository
from app.repositories.llm_usage_repository import LlmUsageRepository
from app.repositories.query_template_repository import QueryTemplateRepository
from app.schemas.query import QueryRequest, QueryResponse, UsageEntry


class QueryService:
    async def handle_query(
        self, request: QueryRequest, trace_id: UUID, session: AsyncSession
    ) -> QueryResponse:
        settings = get_settings()
        start = time.monotonic()

        budget = RequestBudget(limit_usd=settings.max_request_cost_usd, trace_id=trace_id)
        llm = LLMClient(budget)
        template_repo = QueryTemplateRepository(session)
        audit_repo = AuditTrailRepository(session)
        llm_usage_repo = LlmUsageRepository(session)
        graph = build_graph(llm, template_repo, session, settings)

        initial_state: GraphState = {
            "trace_id": trace_id,
            "question": request.question,
            "intent": None,
            "params": {},
            "confidence": 0.0,
            "route": None,
            "rows": None,
            "answer": None,
            "clarification": None,
        }

        try:
            final_state: GraphState = await graph.ainvoke(initial_state)
        except Exception:
            # DESIGN §6: audit_trail is written on every route, including
            # failures. Persist what we know, then let the exception
            # continue to app.core.errors' handlers for the §6 envelope.
            latency_ms = int((time.monotonic() - start) * 1000)
            await budget.persist(llm_usage_repo)
            await audit_repo.create(
                trace_id=trace_id,
                question=request.question,
                confidence=Decimal("0"),
                route="error",
                latency_ms=latency_ms,
            )
            await session.commit()
            raise

        latency_ms = int((time.monotonic() - start) * 1000)
        await budget.persist(llm_usage_repo)

        route = final_state.get("route") or "clarified"
        confidence = final_state.get("confidence", 0.0)
        rows = final_state.get("rows")
        row_count = len(rows) if rows is not None else None
        params = final_state.get("params") or {}

        # DESIGN §5: intent is NULL "when nothing cleared threshold" — a
        # confidence condition, not a route condition. respond.py's own
        # bad-param clarify still had a confident, valid intent selected.
        cleared_threshold = confidence >= settings.confidence_threshold
        persisted_intent = final_state.get("intent") if cleared_threshold else None

        candidate_intents: list[str] = []
        if route == "clarified":
            templates = await template_repo.list_enabled()
            candidate_intents = sorted(t.intent for t in templates)

        await audit_repo.create(
            trace_id=trace_id,
            question=request.question,
            answer=final_state.get("answer") if route == "answer" else None,
            intent=persisted_intent,
            params=params,
            confidence=Decimal(str(confidence)),
            route=route,
            row_count=row_count,
            latency_ms=latency_ms,
        )
        await session.commit()

        usage = [
            UsageEntry(
                node=entry.node,
                model=entry.model,
                prompt_tokens=entry.prompt_tokens,
                completion_tokens=entry.completion_tokens,
                latency_ms=entry.latency_ms,
            )
            for entry in budget.entries
        ]

        return QueryResponse(
            trace_id=trace_id,
            route=route,
            answer=final_state.get("answer") if route == "answer" else None,
            intent=final_state.get("intent") if route == "answer" else None,
            params=params if route == "answer" else {},
            row_count=row_count if route == "answer" else None,
            clarifying_question=final_state.get("clarification") if route == "clarified" else None,
            candidate_intents=candidate_intents,
            confidence=confidence,
            latency_ms=latency_ms,
            usage=usage,
            cost_usd=budget.total_usd,
        )
