"""Domain exception base + handlers producing the error envelope from
DESIGN §6:

    {"trace_id": "uuid", "route": "error", "error": {"code": "string", "message": "string"}}

Every handler here reads trace_id from `request.state.trace_id` (set by
TracingMiddleware) rather than the tracing contextvar — see
app.core.tracing's module docstring for why: an exception that propagates
out of that middleware resets the contextvar before these handlers ever
run, but `request.state` survives. Each handler also sets the
`X-Trace-Id` response header itself, since for a genuinely raised (not
returned) exception, TracingMiddleware never gets a chance to touch the
resulting response.
"""
import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.tracing import TRACE_ID_HEADER, get_trace_id

logger = structlog.get_logger()


class AppError(Exception):
    """Base for all domain exceptions. Raise a subclass (or this directly)
    anywhere in the app; the handler below turns it into the §6 envelope."""

    code: str = "app_error"
    message: str = "An application error occurred."
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(self, message: str | None = None, code: str | None = None) -> None:
        if message is not None:
            self.message = message
        if code is not None:
            self.code = code
        super().__init__(self.message)


class NotFoundError(AppError):
    code = "not_found"
    message = "Resource not found."
    status_code = status.HTTP_404_NOT_FOUND


def _trace_id_for(request: Request) -> str | None:
    return getattr(request.state, "trace_id", None) or get_trace_id()


def _error_response(request: Request, status_code: int, code: str, message: str) -> JSONResponse:
    trace_id = _trace_id_for(request)
    return JSONResponse(
        status_code=status_code,
        content={"trace_id": trace_id, "route": "error", "error": {"code": code, "message": message}},
        headers={TRACE_ID_HEADER: trace_id} if trace_id else None,
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        logger.warning("app_error", code=exc.code, message=exc.message)
        return _error_response(request, exc.status_code, exc.code, exc.message)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        # Covers unmatched routes and any plain `raise HTTPException(...)`
        # so every response — not just AppError subclasses — gets the §6
        # envelope.
        logger.warning("http_exception", status_code=exc.status_code, detail=exc.detail)
        return _error_response(
            request, exc.status_code, f"http_{exc.status_code}", str(exc.detail)
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.warning("validation_error", errors=exc.errors())
        return _error_response(
            request,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "validation_error",
            "Invalid request body.",
        )

    @app.exception_handler(Exception)
    async def handle_unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_error", exc_info=True)
        return _error_response(
            request,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "internal_error",
            "An internal error occurred.",
        )
