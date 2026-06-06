"""Neo4j driver connection management.

The driver is OPTIONAL. `probe_driver()` is called once at startup; if Neo4j is
unreachable it records unavailability and the app runs in in-memory mode. The
rest of the app must use `get_optional_driver()` (may return None) — only legacy
callers that truly require Neo4j use `get_driver()`.
"""

import asyncio
import logging

from neo4j import AsyncDriver, AsyncGraphDatabase

from explorator.config import settings

logger = logging.getLogger(__name__)

_driver: AsyncDriver | None = None
_available: bool = False
_lock = asyncio.Lock()


async def probe_driver(timeout: float = 3.0) -> AsyncDriver | None:
    """Create the driver and verify connectivity. Returns None if unreachable.

    Sets module availability state. Safe to call once at startup. On failure the
    half-open driver is closed so we don't leak sockets.
    """
    global _driver, _available
    async with _lock:
        if _driver is not None and _available:
            return _driver
        driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        try:
            await asyncio.wait_for(driver.verify_connectivity(), timeout=timeout)
        except (OSError, TimeoutError, Exception) as exc:  # noqa: BLE001
            logger.warning("Neo4j unreachable (%s) — running in in-memory mode", exc)
            await driver.close()
            _driver = None
            _available = False
            return None
        _driver = driver
        _available = True
        return _driver


async def get_optional_driver() -> AsyncDriver | None:
    """Return the live driver if Neo4j is available, else None. Never connects."""
    return _driver if _available else None


def neo4j_available() -> bool:
    """Whether the last probe found a reachable Neo4j."""
    return _available


async def get_driver() -> AsyncDriver:
    """Legacy: get-or-create the driver, raising if unreachable.

    Retained for code paths that genuinely require Neo4j (migrations, the
    Neo4j-only test fixtures). Application code should prefer get_optional_driver.
    """
    global _driver, _available
    if _driver is None:
        async with _lock:
            if _driver is None:
                _driver = AsyncGraphDatabase.driver(
                    settings.neo4j_uri,
                    auth=(settings.neo4j_user, settings.neo4j_password),
                )
                _available = True
    return _driver


async def close_driver() -> None:
    """Close the Neo4j driver and reset availability."""
    global _driver, _available
    async with _lock:
        if _driver is not None:
            await _driver.close()
            _driver = None
        _available = False
