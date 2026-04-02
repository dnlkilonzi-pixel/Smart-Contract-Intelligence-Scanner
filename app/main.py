"""Smart Contract Intelligence Scanner — FastAPI application."""
from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import router as v1_router
from app.config import get_settings
from app.models.database import init_db
from app.utils.logging import configure_logging

settings = get_settings()
configure_logging(debug=settings.app_debug)
log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("starting_up", env=settings.app_env)
    await init_db()
    yield
    log.info("shutting_down")


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title="Smart Contract Intelligence Scanner",
        description=(
            "Production-grade Web3 security & analytics platform that scans "
            "smart contracts, detects vulnerabilities, profiles behaviour, "
            "and assigns dynamic risk scores."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS — tighten in production
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Versioned API router
    app.include_router(v1_router, prefix="/api/v1")

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_error", path=str(request.url), error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    @app.get("/health", tags=["health"])
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
    )
