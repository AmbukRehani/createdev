"""Shared node-boundary logging (observability requirement 1).

One "node_complete" INFO log per node invocation, with a consistent field
set across understand/respond/clarify: node name, the key decision
(intent, confidence, route, row count), model, prompt_tokens,
completion_tokens, cost_usd, latency_ms. Fields that don't apply to a
given invocation (e.g. no LLM call happened) are simply omitted, never
fabricated.

Question text and generated answers must never appear here — see each
node's own logger.debug() calls for those, gated to DEBUG only.
"""
import structlog

logger = structlog.get_logger()


def log_node_complete(node: str, **fields) -> None:
    logger.info("node_complete", node=node, **fields)
