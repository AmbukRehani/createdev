"""Thin HTTP layer for GET /api/v1/traces/{trace_id}: fetch, assemble,
serialize. All read logic (the actual queries) lives in the repositories.
"""
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.db.session import get_db
from app.repositories.audit_trail_repository import AuditTrailRepository
from app.repositories.llm_usage_repository import LlmUsageRepository
from app.schemas.trace import TraceCallEntry, TraceResponse

router = APIRouter()


@router.get("/traces/{trace_id}", response_model=TraceResponse)
async def get_trace(trace_id: UUID, db: AsyncSession = Depends(get_db)) -> TraceResponse:
    audit_repo = AuditTrailRepository(db)
    usage_repo = LlmUsageRepository(db)

    audit = await audit_repo.get_by_trace_id(trace_id)
    if audit is None:
        raise NotFoundError(f"No trace found for {trace_id}.", code="trace_not_found")

    # Already ordered by created_at (LlmUsageRepository.list_by_trace_id).
    usage_rows = await usage_repo.list_by_trace_id(trace_id)

    return TraceResponse(
        trace_id=trace_id,
        question=audit.question,
        route=audit.route,
        confidence=audit.confidence,
        # row.cost_usd is Decimal (NUMERIC column) — sum as Decimal, then
        # cast once, rather than mixing Decimal + float mid-sum.
        total_cost_usd=float(sum((row.cost_usd for row in usage_rows), Decimal("0"))),
        # audit.latency_ms is the whole request's wall-clock time — DB
        # queries, validation, template execution included, not just the
        # sum of the LLM calls' own latencies.
        total_latency_ms=audit.latency_ms,
        calls=[
            TraceCallEntry(
                node=row.node,
                model=row.model,
                prompt_tokens=row.prompt_tokens,
                completion_tokens=row.completion_tokens,
                cost_usd=row.cost_usd,
                latency_ms=row.latency_ms,
            )
            for row in usage_rows
        ],
    )
