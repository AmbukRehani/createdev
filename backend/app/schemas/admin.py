"""GET /api/v1/admin/cost response contract."""
from pydantic import BaseModel


class CostBreakdownEntry(BaseModel):
    node: str
    model: str
    calls: int
    cost_usd: float


class CostSummaryResponse(BaseModel):
    window_hours: int
    total_requests: int
    total_cost_usd: float
    avg_cost_usd_per_request: float
    breakdown: list[CostBreakdownEntry]
