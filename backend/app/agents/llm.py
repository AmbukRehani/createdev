"""The only module in this repo allowed to import a provider SDK
(langchain_openai / langchain_core). Everything else — services, agents,
routers — goes through LLMClient.

Verified against the installed langchain-openai 1.6.0: ChatOpenAI's token
limit field aliases to `max_completion_tokens` (this SDK follows OpenAI's
reasoning-model API, not the older `max_tokens` param name), and
AIMessage.usage_metadata carries input_tokens/output_tokens.
"""
import json
import time
from dataclasses import dataclass
from typing import Any, Literal

import structlog
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ValidationError

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.observability.cost import RequestBudget

logger = structlog.get_logger()

Task = Literal["understand", "respond"]

# $/1M tokens (input, output). PLACEHOLDER: awaiting confirmed pricing —
# both rates are 0.0 until then, so cost_usd computes to 0.0 rather than a
# fabricated number.
PRICING: dict[str, tuple[float, float]] = {
    "gpt-5-mini": (0.0, 0.0),  # TODO: real rate
    "gpt-5": (0.0, 0.0),  # TODO: real rate
}


def TASK_MODELS(settings: Settings) -> dict[Task, str]:
    """'understand' -> settings.model_understand, 'respond' ->
    settings.model_respond. A function, not a frozen module-level dict,
    so it always reflects the live Settings rather than whatever was
    loaded the moment this module was first imported."""
    return {
        "understand": settings.model_understand,
        "respond": settings.model_respond,
    }


class LLMParseError(AppError):
    code = "llm_parse_error"
    message = "The model failed to produce valid structured output."
    status_code = 500


@dataclass
class LLMResult:
    parsed: BaseModel
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    latency_ms: int


def _cost_usd(model_id: str, prompt_tokens: int, completion_tokens: int) -> float:
    rates = PRICING.get(model_id)
    if rates is None:
        logger.warning("unknown_model_pricing", model=model_id)
        return 0.0
    input_rate, output_rate = rates
    cost = (prompt_tokens / 1_000_000) * input_rate + (completion_tokens / 1_000_000) * output_rate
    return round(cost, 6)


def _extract_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[len("json") :]
        text = text.strip()
    return json.loads(text)


class LLMClient:
    def __init__(self, budget: RequestBudget) -> None:
        self._budget = budget
        self._settings = get_settings()

    async def structured(
        self,
        task: Task,
        prompt: str,
        schema: type[BaseModel],
        max_tokens: int,
        temperature: float = 0.0,
    ) -> LLMResult:
        model_id = TASK_MODELS(self._settings)[task]

        messages: list[BaseMessage] = [
            SystemMessage(
                content=(
                    "Respond with ONLY a single JSON object matching this JSON "
                    "Schema. No prose, no markdown code fences, no extra keys.\n\n"
                    f"{json.dumps(schema.model_json_schema())}"
                )
            ),
            HumanMessage(content=prompt),
        ]

        last_error: Exception | None = None
        for attempt in range(2):  # initial call + one corrective retry
            self._budget.assert_within_budget()

            chat = ChatOpenAI(
                model=model_id,
                api_key=self._settings.openai_api_key,
                max_completion_tokens=max_tokens,
                temperature=temperature,
            )
            start = time.monotonic()
            response = await chat.ainvoke(messages)
            latency_ms = int((time.monotonic() - start) * 1000)

            usage = response.usage_metadata or {}
            prompt_tokens = usage.get("input_tokens", 0)
            completion_tokens = usage.get("output_tokens", 0)
            cost_usd = _cost_usd(model_id, prompt_tokens, completion_tokens)

            # A failed-parse attempt still cost real money — record every
            # physical call, not just the one that eventually succeeds.
            self._budget.add(
                node=task,
                model=model_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
            )

            raw_content = (
                response.content if isinstance(response.content, str) else str(response.content)
            )

            try:
                parsed = schema.model_validate(_extract_json(raw_content))
            except (json.JSONDecodeError, ValidationError) as exc:
                last_error = exc
                if attempt == 0:
                    messages.append(AIMessage(content=raw_content))
                    messages.append(
                        HumanMessage(
                            content=(
                                "That was not valid JSON matching the schema. "
                                f"Error: {exc}\n\n"
                                "Respond again with ONLY the corrected JSON object."
                            )
                        )
                    )
                continue

            return LLMResult(
                parsed=parsed,
                model=model_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
            )

        raise LLMParseError(
            f"Model {model_id!r} failed to produce valid {schema.__name__} "
            f"JSON after one retry: {last_error}"
        )
