"""DESIGN §3b: look up the template by intent, validate params (types +
existence), execute read-only with LIMIT enforced, summarize the rows
grounded in them. The model never writes SQL.
"""
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import structlog
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm import LLMClient, LLMParseError
from app.agents.logging import log_node_complete
from app.agents.param_validation import validate_params
from app.agents.prompt_loader import load_prompt
from app.agents.state import GraphState
from app.core.config import Settings
from app.models.job import Job
from app.repositories.query_template_repository import QueryTemplateRepository

logger = structlog.get_logger()

RESPOND_MAX_TOKENS = 500

# (intent, param) -> (model, column) for the "cheap existence check".
# Hand-curated alongside the templates themselves — see docs/design.MD §5.
EXISTENCE_CHECKS: dict[tuple[str, str], tuple[type, str]] = {
    ("avg_time_to_hire_by_dept", "department"): (Job, "department"),
    ("interview_pass_rate_by_round", "job_title"): (Job, "title"),
}


class Summary(BaseModel):
    answer: str


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


class RespondNode:
    def __init__(
        self,
        llm: LLMClient,
        template_repo: QueryTemplateRepository,
        session: AsyncSession,
        settings: Settings,
    ) -> None:
        self._llm = llm
        self._template_repo = template_repo
        self._session = session
        self._settings = settings

    async def __call__(self, state: GraphState) -> dict:
        intent = state["intent"]
        params = state["params"]

        template = await self._template_repo.get_by_intent(intent) if intent else None
        if template is None:
            logger.warning("respond_unknown_template", intent=intent)
            log_node_complete("respond", intent=intent, route="clarified")
            return {
                "route": "clarified",
                "clarification": "I couldn't match that to anything I know how to answer.",
            }

        errors = validate_params(params, template.params_schema)
        errors.extend(await self._existence_errors(template.intent, params))
        if errors:
            logger.info("respond_invalid_params", intent=intent, errors=errors)
            log_node_complete("respond", intent=intent, route="clarified")
            return {
                "route": "clarified",
                "clarification": "I need a bit more detail: " + "; ".join(errors) + ".",
            }

        rows = await self._execute_template(template.sql_text, params)

        if not rows:
            answer = "No matching records found."
            logger.debug("respond_answer", intent=intent, answer=answer)
            log_node_complete("respond", intent=intent, route="answer", row_count=0)
            return {"route": "answer", "rows": rows, "answer": answer}

        answer, llm_fields = await self._summarize(state["question"], intent, rows)
        logger.debug("respond_answer", intent=intent, answer=answer)
        log_node_complete(
            "respond", intent=intent, route="answer", row_count=len(rows), **llm_fields
        )
        return {"route": "answer", "rows": rows, "answer": answer}

    async def _existence_errors(self, intent: str, params: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        for (check_intent, param_name), (model_cls, column_name) in EXISTENCE_CHECKS.items():
            if check_intent != intent or param_name not in params:
                continue
            value = params[param_name]
            column = getattr(model_cls, column_name)

            exists = (
                await self._session.execute(select(1).where(column == value).limit(1))
            ).first() is not None
            if exists:
                continue

            valid_options = (
                await self._session.execute(select(column).distinct().order_by(column))
            ).scalars().all()
            errors.append(
                f"there's no {param_name} '{value}'. Valid options: "
                + ", ".join(valid_options)
            )
        return errors

    async def _execute_template(self, sql_text: str, params: dict[str, Any]) -> list[dict]:
        # The only SQL constructed outside query_templates: a fixed,
        # non-model-influenced wrapper enforcing the row cap around
        # trusted, curated template text (DESIGN §5 — no LIMIT in
        # sql_text itself, the executor appends one).
        wrapped_sql = f"SELECT * FROM ({sql_text}) AS _capped LIMIT :__max_rows"
        bind_params = {**params, "__max_rows": self._settings.max_rows}

        # Close out whatever implicit transaction earlier reads in this
        # node opened, so the READ ONLY setting below applies cleanly to
        # a fresh top-level transaction — and closes before the request's
        # later audit-trail/llm_usage writes reuse this session.
        await self._session.commit()
        async with self._session.begin():
            await self._session.execute(text("SET TRANSACTION READ ONLY"))
            result = await self._session.execute(text(wrapped_sql), bind_params)
            return [dict(row) for row in result.mappings().all()]

    async def _summarize(
        self, question: str, intent: str, rows: list[dict]
    ) -> tuple[str, dict[str, Any]]:
        safe_rows = [{k: _json_safe(v) for k, v in row.items()} for row in rows]
        prompt = load_prompt("respond.md").format(
            question=question,
            intent=intent,
            rows=json.dumps(safe_rows, default=str),
        )
        try:
            result = await self._llm.structured(
                task="respond",
                prompt=prompt,
                schema=Summary,
                max_tokens=RESPOND_MAX_TOKENS,
            )
        except LLMParseError:
            # The query itself succeeded — rows are real and already
            # fetched — only the natural-language polish failed. Stay
            # honest rather than either inventing prose or discarding a
            # real result as "clarified".
            logger.warning("respond_malformed_output", intent=intent, row_count=len(rows))
            return f"Found {len(rows)} matching record(s), but couldn't generate a summary.", {}

        summary = result.parsed
        assert isinstance(summary, Summary)
        llm_fields = {
            "model": result.model,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "cost_usd": result.cost_usd,
            "latency_ms": result.latency_ms,
        }
        return summary.answer, llm_fields
