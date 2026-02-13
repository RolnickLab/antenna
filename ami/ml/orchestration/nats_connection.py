"""
NATS connection management for both Celery workers and Django processes.

Uses a persistent connection pool (one NATS connection per event loop) for all
TaskQueueManager operations. A 1000-image job generates ~1500+ NATS operations
(1 for queuing, 250-500 for task fetches, 1000 for ACKs). The pool keeps one
connection alive per event loop and reuses it for all of them.

Why keyed by event loop:
  Django views and Celery tasks use async_to_sync(), which creates a new event
  loop per thread. asyncio.Lock and nats.Client are bound to the loop they were
  created on, so sharing them across loops causes "attached to a different loop"
  errors. Keying by loop ensures isolation. WeakKeyDictionary auto-cleans when
  loops are garbage collected, so short-lived loops don't leak.

Connection lifecycle:
  - Created lazily on first use within an event loop
  - Reused for all subsequent operations on that loop
  - On connection error: retry decorator calls reset_connection() to close the
    stale connection; next operation creates a fresh one (see
    retry_on_connection_error in nats_queue.py)
  - Cleaned up automatically when the event loop is garbage collected

Archived alternative:
  ContextManagerConnection preserves the original pre-pool implementation
  (one connection per `async with` block) as a drop-in fallback.
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
    Manages a single persistent NATS connection per event loop.

    This is safe because:
    - asyncio.Lock and NATS Client are bound to the event loop they were created on
    - Each event loop gets its own isolated connection and lock
    - Works correctly with async_to_sync() which creates per-thread event loops
    - Prevents "attached to a different loop" errors in Celery tasks and Django views

    Instantiating TaskQueueManager() is cheap — multiple instances share the same
    underlying connection via this pool.
    """

    def __init__(self):
        self._nc: "NATSClient | None" = None
        self._js: JetStreamContext | None = None
        self._lock: asyncio.Lock | None = None  # Lazy-initialized when needed

    def _ensure_lock(self) -> asyncio.Lock:
        """Lazily create lock bound to current event loop."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def get_connection(self) -> tuple["NATSClient", JetStreamContext]:
        """
        Get or create the event loop's NATS connection. Checks connection health
        and recreates if stale.

        Returns:
            Tuple of (NATS connection, JetStream context)
        Raises:
            RuntimeError: If connection cannot be established
        """
        # Fast path (no lock needed): connection exists, is open, and is connected.
        # This is the hot path — most calls hit this and return immediately.
        if self._nc is not None and self._js is not None and not self._nc.is_closed and self._nc.is_connected:
            return self._nc, self._js

        # Connection is stale or doesn't exist — clear references before reconnecting
        if self._nc is not None:
            logger.warning("NATS connection is closed or disconnected, will reconnect")
            self._nc = None
            self._js = None

        # Slow path: acquire lock to prevent concurrent reconnection attempts
        lock = self._ensure_lock()
        async with lock:
            # Double-check after acquiring lock (another coroutine may have reconnected)
            if self._nc is not None and self._js is not None and not self._nc.is_closed and self._nc.is_connected:
                return self._nc, self._js

            nats_url = settings.NATS_URL
            try:
                logger.info(f"Creating NATS connection to {nats_url}")
                self._nc = await nats.connect(nats_url)
                self._js = self._nc.jetstream()
                logger.info(f"Successfully connected to NATS at {nats_url}")
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
        Close the current connection and clear all state so the next call to
        get_connection() creates a fresh one.

        Called by retry_on_connection_error when an operation hits a connection
        error (e.g. network blip, NATS restart). The lock is also cleared so it
        gets recreated bound to the current event loop.
        """
        logger.warning("Resetting NATS connection pool due to connection error")
        if self._nc is not None:
            try:
                if not self._nc.is_closed:
                    await self._nc.close()
                    logger.debug("Successfully closed existing NATS connection during reset")
            except Exception as e:
                # Swallow errors - connection may already be broken
                logger.debug(f"Error closing connection during reset (expected): {e}")
        self._nc = None
        self._js = None
        self._lock = None  # Clear lock so new one is created for fresh connection


class ContextManagerConnection:
    """
    Archived pre-pool implementation: one NATS connection per `async with` block.

    This was the original approach before the connection pool was added. It creates
    a fresh connection on get_connection() and expects the caller to close it when
    done. There is no connection reuse and no retry logic at this layer.

    Trade-offs vs ConnectionPool:
    - Simpler: no shared state, no locking, no event-loop keying
    - Expensive: ~1500 TCP connections per 1000-image job vs 1 with the pool
    - No automatic reconnection — caller must handle connection failures

    Kept as a drop-in fallback. To switch, change the class used in
    _create_pool() below from ConnectionPool to ContextManagerConnection.
    """

    async def get_connection(self) -> tuple["NATSClient", JetStreamContext]:
        """Create a fresh NATS connection."""
        nats_url = settings.NATS_URL
        try:
            logger.debug(f"Creating per-operation NATS connection to {nats_url}")
            nc = await nats.connect(nats_url)
            js = nc.jetstream()
            return nc, js
        except Exception as e:
            logger.error(f"Failed to connect to NATS: {e}")
            raise RuntimeError(f"Could not establish NATS connection: {e}") from e

    async def close(self):
        """No-op — connections are not tracked."""
        pass

    async def reset(self):
        """No-op — connections are not tracked."""
        pass


# Event-loop-keyed pools: one ConnectionPool per event loop.
# WeakKeyDictionary automatically cleans up when event loops are garbage collected.
_pools: WeakKeyDictionary[asyncio.AbstractEventLoop, ConnectionPool] = WeakKeyDictionary()
_pools_lock = threading.Lock()


def _get_pool() -> ConnectionPool:
    """Get or create the ConnectionPool for the current event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        raise RuntimeError(
            "get_connection() must be called from an async context with a running event loop. "
            "If calling from sync code, use async_to_sync() to wrap the async function."
        )

    with _pools_lock:
        if loop not in _pools:
            _pools[loop] = ConnectionPool()
            logger.debug(f"Created NATS connection pool for event loop {id(loop)}")
        return _pools[loop]


async def get_connection() -> tuple["NATSClient", JetStreamContext]:
    """
    Get or create a NATS connection for the current event loop.

    Returns:
        Tuple of (NATS connection, JetStream context)
    Raises:
        RuntimeError: If called outside of an async context (no running event loop)
    """
    pool = _get_pool()
    return await pool.get_connection()


async def reset_connection() -> None:
    """
    Reset the NATS connection for the current event loop.

    Closes the current connection and clears all state so the next call to
    get_connection() creates a fresh one.
    """
    pool = _get_pool()
    await pool.reset()
