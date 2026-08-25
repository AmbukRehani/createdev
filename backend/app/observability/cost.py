"""Per-request LLM spend tracking and persistence to llm_usage.

A RequestBudget is constructed once per /v1/query request (one per
trace_id) and threaded into LLMClient. Every provider call — including a
failed-parse attempt that gets retried, which still cost real money —
adds one entry. cost_usd on each entry is computed at call time by
app/agents/llm.py and stored as-is; nothing here re-derives it.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from app.core.errors import AppError
from app.repositories.llm_usage_repository import LlmUsageRepository


class BudgetExceeded(AppError):
    code = "budget_exceeded"
    message = "Request cost budget exceeded."
    # Quota-exceeded semantics; not otherwise specified — flagging as a
    # judgment call in case a different status is wanted.
    status_code = 429


@dataclass
class BudgetEntry:
    node: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    latency_ms: int


@dataclass
class RequestBudget:
    limit_usd: float
    trace_id: UUID
    entries: list[BudgetEntry] = field(default_factory=list)
    total_usd: float = 0.0
    _persisted_count: int = field(default=0, repr=False)

    def assert_within_budget(self) -> None:
        """Checked before each physical provider call. Reflects spend
        already committed by prior calls in this request — it cannot
        predict the cost of the call about to be made."""
        if self.total_usd >= self.limit_usd:
            raise BudgetExceeded(
                f"Request {self.trace_id} has spent ${self.total_usd:.6f}, "
                f"at or over its ${self.limit_usd:.6f} budget."
            )

    def add(
        self,
        *,
        node: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
        latency_ms: int,
    ) -> None:
        self.entries.append(
            BudgetEntry(
                node=node,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
            )
        )
        self.total_usd += cost_usd

    async def persist(self, repo: LlmUsageRepository) -> None:
        """Flushes entries to llm_usage, keyed by trace_id. Safe to call
        more than once — only entries added since the last persist() are
        written, so nothing is double-inserted."""
        for entry in self.entries[self._persisted_count :]:
            await repo.create(
                trace_id=self.trace_id,
                node=entry.node,
                model=entry.model,
                prompt_tokens=entry.prompt_tokens,
                completion_tokens=entry.completion_tokens,
                cost_usd=Decimal(str(entry.cost_usd)),
                latency_ms=entry.latency_ms,
            )
        self._persisted_count = len(self.entries)
