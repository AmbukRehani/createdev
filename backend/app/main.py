"""App factory: config, logging, tracing, CORS, error handlers, DB lifespan,
and the liveness/readiness endpoints."""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin import router as admin_router
from app.api.v1.query import router as query_router
from app.api.v1.traces import router as traces_router
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.tracing import TracingMiddleware
from app.db.session import dispose_engine, get_db

logger = structlog.get_logger()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        yield
        await dispose_engine()

    app = FastAPI(title="NL Query Assistant", lifespan=lifespan)

    app.add_middleware(TracingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(query_router, prefix="/api/v1", tags=["query"])
    app.include_router(traces_router, prefix="/api/v1", tags=["traces"])
    app.include_router(admin_router, prefix="/api/v1", tags=["admin"])

    @app.get("/healthz")
    async def healthz() -> dict:
        """Liveness: the process is up. No dependencies checked."""
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz(db: AsyncSession = Depends(get_db)) -> JSONResponse:
        """Readiness: the process can actually serve traffic."""
        try:
            await db.execute(text("SELECT 1"))
        except Exception:
            logger.error("readiness_check_failed", exc_info=True)
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "error", "db": "error"},
            )
        return JSONResponse(content={"status": "ok", "db": "ok"})

    return app


app = create_app()
