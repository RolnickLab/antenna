"""
NATS connection pool for both Celery workers and Django processes.

Maintains a persistent NATS connection per event loop to avoid
the overhead of creating/closing connections for every operation.

The connection pool is lazily initialized on first use and keyed by event loop
to prevent "attached to a different loop" errors when using async_to_sync().
"""

import asyncio
import logging
import threading
from typing import TYPE_CHECKING
from weakref import WeakKeyDictionary

import nats
from django.conf import settings
from nats.js import JetStreamContext

if TYPE_CHECKING:
    from nats.aio.client import Client as NATSClient

logger = logging.getLogger(__name__)


class ConnectionPool:
    """
    Manages a single NATS connection per event loop.

    This is safe because:
    - asyncio.Lock and NATS Client are bound to the event loop they were created on
    - Each event loop gets its own isolated connection and lock
    - Works correctly with async_to_sync() which creates per-thread event loops
    - Prevents "attached to a different loop" errors in Celery tasks and Django views
    """

    def __init__(self):
        self._nc: "NATSClient | None" = None
        self._js: JetStreamContext | None = None
        self._nats_url: str | None = None
        self._lock: asyncio.Lock | None = None  # Lazy-initialized when needed

    def _ensure_lock(self) -> asyncio.Lock:
        """Lazily create lock bound to current event loop."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def get_connection(self) -> tuple["NATSClient", JetStreamContext]:
        """
        Get or create the event loop's NATS connection. Checks connection health and recreates if stale.

        Returns:
            Tuple of (NATS connection, JetStream context)
        Raises:
            RuntimeError: If connection cannot be established
        """
        # Fast path: connection exists, is open, and is connected
        if self._nc is not None and not self._nc.is_closed and self._nc.is_connected:
            return self._nc, self._js  # type: ignore

        # Connection is stale or doesn't exist
        if self._nc is not None:
            logger.warning("NATS connection is closed or disconnected, will reconnect")
            self._nc = None
            self._js = None

        # Slow path: need to create/recreate connection
        lock = self._ensure_lock()
        async with lock:
            # Double-check after acquiring lock
            if self._nc is not None and not self._nc.is_closed and self._nc.is_connected:
                return self._nc, self._js  # type: ignore

            # Get NATS URL from settings
            if self._nats_url is None:
                self._nats_url = getattr(settings, "NATS_URL", "nats://nats:4222")

            try:
                logger.info(f"Creating NATS connection to {self._nats_url}")
                self._nc = await nats.connect(self._nats_url)
                self._js = self._nc.jetstream()
                logger.info(f"Successfully connected to NATS at {self._nats_url}")
                return self._nc, self._js
            except Exception as e:
                logger.error(f"Failed to connect to NATS: {e}")
                raise RuntimeError(f"Could not establish NATS connection: {e}") from e

    async def close(self):
        """Close the NATS connection if it exists."""
        if self._nc is not None and not self._nc.is_closed:
            logger.info("Closing NATS connection")
            await self._nc.close()
            self._nc = None
            self._js = None

    async def reset(self):
        """
        Async version of reset that properly closes the connection before clearing references.

        This should be called when a connection error is detected from an async context.
        The next call to get_connection() will create a fresh connection.
        """
        logger.warning("Resetting NATS connection pool due to connection error")
        if self._nc is not None:
            try:
                # Attempt to close the connection gracefully
                if not self._nc.is_closed:
                    await self._nc.close()
                    logger.debug("Successfully closed existing NATS connection during reset")
            except Exception as e:
                # Swallow errors - connection may already be broken
                logger.debug(f"Error closing connection during reset (expected): {e}")
        self._nc = None
        self._js = None
        self._lock = None  # Clear lock so new one is created for fresh connection


# Event-loop-keyed pools: one ConnectionPool per event loop
# WeakKeyDictionary automatically cleans up when event loops are garbage collected
_pools: WeakKeyDictionary[asyncio.AbstractEventLoop, ConnectionPool] = WeakKeyDictionary()
_pools_lock = threading.Lock()


def get_pool() -> ConnectionPool:
    """
    Get or create the connection pool for the current event loop.

    Each event loop gets its own ConnectionPool to prevent "attached to a different loop" errors.
    This is critical when using async_to_sync() in Celery tasks or Django views, as each call
    may run on a different event loop.

    Returns:
        ConnectionPool bound to the current event loop

    Raises:
        RuntimeError: If called outside of an async context (no running event loop)
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        raise RuntimeError(
            "get_pool() must be called from an async context with a running event loop. "
            "If calling from sync code, use async_to_sync() to wrap the async function."
        )

    # Thread-safe lookup/creation of pool for this event loop
    with _pools_lock:
        if loop not in _pools:
            _pools[loop] = ConnectionPool()
            logger.debug(f"Created NATS connection pool for event loop {id(loop)}")
        return _pools[loop]
