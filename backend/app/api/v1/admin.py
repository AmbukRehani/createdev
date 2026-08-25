"""Thin HTTP layer for GET /api/v1/admin/cost: parse the window, delegate
the aggregation to the repository, serialize. All read logic lives there.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.llm_usage_repository import LlmUsageRepository
from app.schemas.admin import CostBreakdownEntry, CostSummaryResponse

router = APIRouter()


@router.get("/admin/cost", response_model=CostSummaryResponse)
async def get_cost_summary(
    hours: int = Query(24, gt=0, description="Aggregation window, in hours."),
    db: AsyncSession = Depends(get_db),
) -> CostSummaryResponse:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    summary = await LlmUsageRepository(db).get_cost_summary(since)

    return CostSummaryResponse(
        window_hours=hours,
        total_requests=summary.total_requests,
        total_cost_usd=summary.total_cost_usd,
        avg_cost_usd_per_request=summary.avg_cost_usd_per_request,
        breakdown=[
            CostBreakdownEntry(
                node=entry.node, model=entry.model, calls=entry.calls, cost_usd=entry.cost_usd
            )
            for entry in summary.breakdown
        ],
    )
