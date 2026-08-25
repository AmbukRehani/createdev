"""Request-scoped trace_id propagation (DESIGN §7).

One trace_id per request: taken from the `X-Request-ID` header if the
caller supplied one, otherwise minted as a fresh uuid4. It is bound to a
contextvar (so structlog can pick it up without it being threaded through
every function signature) AND stashed on `request.state.trace_id`.

Both are needed: when an unhandled exception propagates out of this
middleware's `call_next()`, the `finally` block below resets the
contextvar before FastAPI's own exception-handling middleware — which
sits OUTSIDE this one — ever gets to build the error response. At that
point `get_trace_id()` would read as None. `request.state.trace_id`
survives that, since the same `Request` object is passed straight to the
registered exception handlers; app.core.errors reads it from there.
"""
from contextvars import ContextVar, Token
from uuid import uuid4

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"
TRACE_ID_HEADER = "X-Trace-Id"

_trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)


def get_trace_id() -> str | None:
    """Current request's trace_id, or None outside a request context.
    Prefer reading `request.state.trace_id` directly in exception
    handlers — see the module docstring for why."""
    return _trace_id_var.get()


class TracingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        trace_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid4())
        request.state.trace_id = trace_id

        token: Token = _trace_id_var.set(trace_id)
        structlog.contextvars.bind_contextvars(trace_id=trace_id)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.unbind_contextvars("trace_id")
            _trace_id_var.reset(token)

        response.headers[TRACE_ID_HEADER] = trace_id
        return response
