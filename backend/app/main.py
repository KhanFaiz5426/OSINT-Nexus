"""OSINT Nexus Backend — FastAPI Application Entry Point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import activity, entities, graph, investigations, reports
from app.core.config import get_settings


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
        # Neo4j may not be available in dev/test; log and continue.
        import logging
        logging.getLogger(__name__).warning(
            "Could not initialize Neo4j schema (Neo4j may be unavailable)"
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    # Initialize Neo4j schema constraints on startup.
    await _init_neo4j_schema()
    yield
    # Shutdown: close connections.
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

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(investigations.router, prefix="/api/v1", tags=["investigations"])
    app.include_router(entities.router, prefix="/api/v1", tags=["entities"])
    app.include_router(graph.router, prefix="/api/v1", tags=["graph"])
    app.include_router(activity.router, prefix="/api/v1", tags=["activity"])
    app.include_router(reports.router, prefix="/api/v1", tags=["reports"])

    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "version": settings.APP_VERSION}

    return app


app = create_app()
