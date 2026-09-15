"""OSINT Nexus Backend — FastAPI Application Entry Point."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api import activity, entities, entity_ai, graph, investigations, notes, reports, sse, workspace
from app.api import settings as settings_api
from app.core.config import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    yield
    # Shut down the TaskManager (cancels active tasks, awaits termination).
    from app.core.task_manager import get_task_manager

    try:
        tm = get_task_manager()
        await tm.shutdown(timeout=5.0)
    except Exception as exc:
        logger.warning("TaskManager shutdown error: %s", exc)

    # Clear EventBus subscribers.
    from app.core.event_bus import get_event_bus

    try:
        get_event_bus().clear()
    except Exception:
        pass

    from app.db.client import close_pool
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
    app.include_router(workspace.router, prefix="/api/v1", tags=["workspace"])
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

    import sys
    from pathlib import Path
    from fastapi.responses import FileResponse
    from fastapi import HTTPException

    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base_dir = Path(sys._MEIPASS)
    else:
        base_dir = Path(__file__).parent.parent.parent
        
    dist_path = base_dir / "frontend" / "dist"
    if dist_path.exists() and dist_path.is_dir():
        # Optional: mount /assets explicitly if Vite is using it to skip Python routing overhead
        from fastapi.staticfiles import StaticFiles
        assets_path = dist_path / "assets"
        if assets_path.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            if full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="API route not found")
            
            file_path = dist_path / full_path
            if file_path.is_file():
                return FileResponse(file_path)
            
            return FileResponse(dist_path / "index.html")

    return app


app = create_app()
