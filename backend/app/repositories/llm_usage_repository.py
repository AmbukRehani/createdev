"""The only place ORM queries for llm_usage live."""
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_usage import LlmUsage


@dataclass
class CostBreakdownEntry:
    node: str
    model: str
    calls: int
    cost_usd: float


@dataclass
class CostSummary:
    total_requests: int
    total_cost_usd: float
    avg_cost_usd_per_request: float
    breakdown: list[CostBreakdownEntry]


class LlmUsageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        trace_id: uuid.UUID,
        node: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: Decimal | float,
        latency_ms: int,
    ) -> LlmUsage:
        row = LlmUsage(
            trace_id=trace_id,
            node=node,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def list_by_trace_id(self, trace_id: uuid.UUID) -> list[LlmUsage]:
        result = await self._session.execute(
            select(LlmUsage)
            .where(LlmUsage.trace_id == trace_id)
            .order_by(LlmUsage.created_at)
        )
        return list(result.scalars().all())

    async def get_cost_summary(self, since: datetime) -> CostSummary:
        """Two SQL-side aggregate queries — no rows are ever loaded into
        Python and summed there. (Not one combined query: a single
        GROUP BY node/model would return zero rows for an empty window,
        which would silently lose the total_requests=0/total_cost_usd=0
        result too — two queries sidesteps that correctness trap.)
        """
        totals_stmt = select(
            func.count(func.distinct(LlmUsage.trace_id)).label("total_requests"),
            func.coalesce(func.sum(LlmUsage.cost_usd), 0).label("total_cost_usd"),
        ).where(LlmUsage.created_at >= since)
        totals = (await self._session.execute(totals_stmt)).one()

        total_requests = totals.total_requests
        total_cost_usd = float(totals.total_cost_usd)
        # A trivial division of two already-aggregated scalars, not a
        # row-level computation — safest done here to dodge divide-by-zero.
        avg_cost_usd_per_request = (
            total_cost_usd / total_requests if total_requests else 0.0
        )

        breakdown_stmt = (
            select(
                LlmUsage.node,
                LlmUsage.model,
                func.count().label("calls"),
                func.coalesce(func.sum(LlmUsage.cost_usd), 0).label("cost_usd"),
            )
            .where(LlmUsage.created_at >= since)
            .group_by(LlmUsage.node, LlmUsage.model)
            .order_by(LlmUsage.node, LlmUsage.model)
        )
        breakdown_rows = (await self._session.execute(breakdown_stmt)).all()

        return CostSummary(
            total_requests=total_requests,
            total_cost_usd=total_cost_usd,
            avg_cost_usd_per_request=avg_cost_usd_per_request,
            breakdown=[
                CostBreakdownEntry(
                    node=row.node,
                    model=row.model,
                    calls=row.calls,
                    cost_usd=float(row.cost_usd),
                )
                for row in breakdown_rows
            ],
        )
