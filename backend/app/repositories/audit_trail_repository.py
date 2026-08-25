"""The only place ORM queries for audit_trail live."""
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_trail import AuditTrail


class AuditTrailRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        trace_id: uuid.UUID,
        question: str,
        confidence: Decimal,
        route: str,
        latency_ms: int,
        answer: str | None = None,
        intent: str | None = None,
        params: dict | None = None,
        row_count: int | None = None,
    ) -> AuditTrail:
        row = AuditTrail(
            trace_id=trace_id,
            question=question,
            answer=answer,
            intent=intent,
            params=params or {},
            confidence=confidence,
            route=route,
            row_count=row_count,
            latency_ms=latency_ms,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def get_by_trace_id(self, trace_id: uuid.UUID) -> AuditTrail | None:
        result = await self._session.execute(
            select(AuditTrail).where(AuditTrail.trace_id == trace_id)
        )
        return result.scalar_one_or_none()
