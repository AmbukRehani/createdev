"""DESIGN §3a: classify intent, fill typed param slots, always produce a
typed output. Returns the state delta only — no DB writes beyond the read
of enabled templates, no HTTP.
"""
import json
from typing import Any

import structlog
from pydantic import BaseModel, Field

from app.agents.llm import LLMClient, LLMParseError
from app.agents.logging import log_node_complete
from app.agents.prompt_loader import load_prompt
from app.agents.state import GraphState
from app.models.query_template import QueryTemplate
from app.repositories.query_template_repository import QueryTemplateRepository

logger = structlog.get_logger()

UNDERSTAND_MAX_TOKENS = 500


class Understanding(BaseModel):
    intent: str
    params: dict[str, Any] = Field(default_factory=dict)
    confidence: float


def _format_templates(templates: list[QueryTemplate]) -> str:
    lines = []
    for t in templates:
        lines.append(
            f"### {t.intent}\n{t.description}\n\nparams_schema:\n"
            f"```json\n{json.dumps(t.params_schema)}\n```"
        )
    return "\n\n".join(lines)


class UnderstandNode:
    def __init__(self, llm: LLMClient, template_repo: QueryTemplateRepository) -> None:
        self._llm = llm
        self._template_repo = template_repo

    async def __call__(self, state: GraphState) -> dict:
        templates = await self._template_repo.list_enabled()
        enabled_intents = {t.intent for t in templates}

        prompt = load_prompt("understand.md").format(
            templates=_format_templates(templates),
            question=state["question"],
        )
        # Question text: DEBUG only, never INFO.
        logger.debug("understand_question", question=state["question"])

        try:
            result = await self._llm.structured(
                task="understand",
                prompt=prompt,
                schema=Understanding,
                max_tokens=UNDERSTAND_MAX_TOKENS,
            )
        except LLMParseError:
            # llm.structured() already retried once internally and still
            # couldn't get valid output. Degrade to clarify rather than
            # letting this propagate as a 500 — same mechanism as the
            # unknown-intent case below: zero confidence, let the gate
            # route it.
            logger.warning("understand_malformed_output")
            log_node_complete("understand", intent=None, confidence=0.0)
            return {"intent": None, "params": {}, "confidence": 0.0}

        understanding = result.parsed
        assert isinstance(understanding, Understanding)

        confidence = understanding.confidence
        if understanding.intent not in enabled_intents:
            # The model returned syntactically valid output, but an intent
            # we never offered it — schema validation can't catch this.
            # Zero the confidence so the existing gate routes to clarify,
            # rather than inventing a second routing decision here.
            logger.warning(
                "understand_unknown_intent",
                intent=understanding.intent,
                enabled_intents=sorted(enabled_intents),
            )
            confidence = 0.0

        # Params often echo fragments of the user's raw text (e.g. a
        # typo'd department name) — DEBUG only, same reasoning as question.
        logger.debug("understand_params", params=understanding.params)

        log_node_complete(
            "understand",
            intent=understanding.intent,
            confidence=confidence,
            model=result.model,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            cost_usd=result.cost_usd,
            latency_ms=result.latency_ms,
        )

        return {
            "intent": understanding.intent,
            "params": understanding.params,
            "confidence": confidence,
        }
