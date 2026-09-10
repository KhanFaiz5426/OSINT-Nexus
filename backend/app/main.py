"""OSINT Nexus Backend — FastAPI Application Entry Point."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api import activity, entities, entity_ai, graph, investigations, notes, reports, sse
from app.api import settings as settings_api
from app.core.config import get_settings

logger = logging.getLogger(__name__)


async def _init_neo4j_schema() -> None:
    """Create Neo4j constraints and indexes if the database is reachable."""
    try:
        from app.graph.client import get_driver
        from app.graph.models import CONSTRAINTS_CYPHER, INVESTIGATION_INDEX_CYPHER

        driver = await get_driver()
        async with driver.session() as session:
            for cypher in CONSTRAINTS_CYPHER:
                await session.run(cypher)
            for cypher in INVESTIGATION_INDEX_CYPHER:
                await session.run(cypher)
    except Exception:
        logger.warning("Could not initialize Neo4j schema (Neo4j may be unavailable)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    await _init_neo4j_schema()
    yield
    from app.db.client import close_pool
    from app.graph.client import close_driver

    await close_driver()
    await close_pool()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="AI-Assisted OSINT Investigation and Correlation Framework",
        lifespan=lifespan,
    )

    # CORS — restrictive in production
    if settings.DEBUG:
        allow_origins = settings.CORS_ORIGINS
        allow_methods = ["*"]
        allow_headers = ["*"]
    else:
        allow_origins = settings.CORS_ORIGINS
        allow_methods = ["GET", "POST", "PUT", "DELETE"]
        allow_headers = ["Authorization", "Content-Type"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=allow_methods,
        allow_headers=allow_headers,
    )

    # Security headers middleware
    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if not settings.DEBUG:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    # Request timing middleware (audit logging)
    @app.middleware("http")
    async def timing_middleware(request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        elapsed_ms = (time.monotonic() - start) * 1000
        logger.info(
            "%s %s %d %.1fms",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response

    # Include routers
    app.include_router(investigations.router, prefix="/api/v1", tags=["investigations"])
    app.include_router(entity_ai.router, prefix="/api/v1", tags=["entity-ai"])
    app.include_router(entities.router, prefix="/api/v1", tags=["entities"])
    app.include_router(graph.router, prefix="/api/v1", tags=["graph"])
    app.include_router(activity.router, prefix="/api/v1", tags=["activity"])
    app.include_router(reports.router, prefix="/api/v1", tags=["reports"])
    app.include_router(sse.router, prefix="/api/v1", tags=["sse"])
    app.include_router(notes.router, prefix="/api/v1", tags=["notes"])
    app.include_router(settings_api.router, prefix="/api/v1", tags=["settings"])

    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "version": settings.APP_VERSION}

    return app


app = create_app()
