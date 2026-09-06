"""Neo4j graph database client."""

from neo4j import AsyncDriver, AsyncGraphDatabase

from app.core.config import get_settings

_driver: AsyncDriver | None = None


async def get_driver() -> AsyncDriver:
    """Get or create the Neo4j async driver."""
    global _driver
    if _driver is None:
        settings = get_settings()
        _driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
        )
    return _driver


async def close_driver() -> None:
    """Close the Neo4j driver."""
    global _driver
    if _driver:
        await _driver.close()
        _driver = None


def reset_driver() -> None:
    """Reset the driver reference (for testing between event loops)."""
    global _driver
    _driver = None


async def verify_connectivity() -> bool:
    """Verify Neo4j connection is alive."""
    try:
        driver = await get_driver()
        await driver.verify_connectivity()
        return True
    except Exception:
        return False
