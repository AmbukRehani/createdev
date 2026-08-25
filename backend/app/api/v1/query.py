"""Thin HTTP layer for POST /api/v1/query: parse request, delegate to
QueryService, serialize response. No business logic here."""
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tracing import get_trace_id
from app.db.session import get_db
from app.schemas.query import QueryRequest, QueryResponse
from app.services.query_service import QueryService

router = APIRouter()
_service = QueryService()


@router.post("/query", response_model=QueryResponse)
async def post_query(
    request: QueryRequest, db: AsyncSession = Depends(get_db)
) -> QueryResponse:
    # Client-supplied trace_id (DESIGN §6 request body) wins; otherwise
    # fall back to the one TracingMiddleware already resolved for this
    # request (from X-Request-ID or a fresh uuid4 — DESIGN §7).
    trace_id = request.trace_id or UUID(get_trace_id())
    return await _service.handle_query(request, trace_id=trace_id, session=db)
