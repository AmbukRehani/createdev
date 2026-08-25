"""Shared pytest fixtures.

Never call a real provider or a real network in any test — FakeLLM below
is what every node/graph test uses instead of app.agents.llm.LLMClient.
"""
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest_asyncio
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agents.llm import LLMClient, LLMResult
from app.agents.state import GraphState
from app.core.config import get_settings
from app.db.session import get_db
from app.main import app
from app.observability.cost import RequestBudget

# --- FakeLLM ------------------------------------------------------------


class FakeLLM(LLMClient):
    """Stand-in for LLMClient. Configured per-task with either the
    Pydantic object `structured()` should return, or an Exception it
    should raise instead — never touches a provider SDK or the network.
    """

    def __init__(
        self,
        responses: dict[str, BaseModel | Exception],
        budget: RequestBudget | None = None,
    ) -> None:
        super().__init__(budget or RequestBudget(limit_usd=1.0, trace_id=uuid4()))
        self._responses = responses
        self.calls: list[tuple[str, str]] = []

    async def structured(
        self,
        task: str,
        prompt: str,
        schema: type[BaseModel],
        max_tokens: int,
        temperature: float = 0.0,
    ) -> LLMResult:
        self.calls.append((task, prompt))
        self._budget.assert_within_budget()

        if task not in self._responses:
            raise AssertionError(f"FakeLLM was not configured for task {task!r}")

        outcome = self._responses[task]
        if isinstance(outcome, Exception):
            raise outcome

        result = LLMResult(
            parsed=outcome,
            model=f"fake-{task}",
            prompt_tokens=10,
            completion_tokens=5,
            cost_usd=0.0,
            latency_ms=0,
        )
        self._budget.add(
            node=task,
            model=result.model,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            cost_usd=result.cost_usd,
            latency_ms=result.latency_ms,
        )
        return result


# --- state helper ---------------------------------------------------------


def make_state(
    *,
    question: str = "test question",
    trace_id: UUID | None = None,
    intent: str | None = None,
    params: dict[str, Any] | None = None,
    confidence: float = 0.0,
    route: str | None = None,
    rows: list[dict[str, Any]] | None = None,
    answer: str | None = None,
    clarification: str | None = None,
) -> GraphState:
    return {
        "trace_id": trace_id or uuid4(),
        "question": question,
        "intent": intent,
        "params": params or {},
        "confidence": confidence,
        "route": route,
        "rows": rows,
        "answer": answer,
        "clarification": clarification,
    }


# --- db_session -------------------------------------------------------


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Real Postgres. The whole test runs inside one connection-level
    transaction that's rolled back at teardown — verified to survive
    application code calling session.commit()/session.begin() internally
    (respond.py's read-only template execution does exactly that), and
    to still let SET TRANSACTION READ ONLY genuinely enforce itself when
    nested this way (confirmed against real Postgres, not assumed).

    Uses its own engine rather than app.db.session's lru_cache'd one:
    that cache lives for the process, but pytest-asyncio gives each test
    function its own event loop, and an asyncpg pool can't be reused
    across loops.
    """
    engine = create_async_engine(get_settings().database_url)
    async with engine.connect() as conn:
        outer_trans = await conn.begin()
        sessionmaker = async_sessionmaker(bind=conn, expire_on_commit=False)
        async with sessionmaker() as session:
            yield session
        await outer_trans.rollback()
    await engine.dispose()


# --- client -------------------------------------------------------------


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """HTTP-level fixture, driving the real /api/v1/query flow end to end.

    Deliberately does NOT reuse db_session's transaction-wrapping. The
    real request flow mixes a SET TRANSACTION READ ONLY block
    (respond.py's template execution) with later writes in the same
    request (audit_trail/llm_usage). Verified against real Postgres:
    nesting that inside db_session's outer wrapped transaction leaks the
    read-only characteristic to those later writes and breaks them with
    `cannot execute INSERT in a read-only transaction` — a genuine
    Postgres transaction-model limitation (SET TRANSACTION applies to the
    whole enclosing transaction, not a savepoint within it), not a
    SQLAlchemy quirk to configure around.

    So this fixture gives each request a real, production-identical
    session instead (get_db's own sessionmaker shape, just pointed at its
    own engine), and cleans up afterward by clearing the two tables this
    flow can ever write to — there's no fixture/seed data in either, so
    this is safe and total, not scoped to just this test's rows.
    """
    engine = create_async_engine(get_settings().database_url)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)

    async with engine.connect() as conn:
        await conn.execute(text("DELETE FROM audit_trail"))
        await conn.execute(text("DELETE FROM llm_usage"))
        await conn.commit()
    await engine.dispose()
