"""
NATS connection management for both Celery workers and Django processes.

Provides two connection strategies, selectable via NATS_CONNECTION_STRATEGY setting:

  "pool" (default):
    Maintains a persistent NATS connection per event loop and reuses it across
    all TaskQueueManager operations. A 1000-image job generates ~1500+ NATS
    operations (1 for queuing, 250-500 for task fetches, 1000 for ACKs). The
    pool keeps one connection alive per event loop and reuses it for all of them.

  "per_operation":
    Creates a fresh TCP connection for every get_connection() call. Simple but
    expensive — the same 1000-image job opens ~1500 TCP connections. Use this
    only for debugging connection issues or when pooling causes problems.

Why keyed by event loop (pool strategy):
  Django views and Celery tasks use async_to_sync(), which creates a new event
  loop per thread. asyncio.Lock and nats.Client are bound to the loop they were
  created on, so sharing them across loops causes "attached to a different loop"
  errors. Keying by loop ensures isolation. WeakKeyDictionary auto-cleans when
  loops are garbage collected, so short-lived loops don't leak.

Connection lifecycle (pool strategy):
  - Created lazily on first use within an event loop
  - Reused for all subsequent operations on that loop
  - On connection error: retry decorator calls pool.reset() to close the stale
    connection; next operation creates a fresh one (see retry_on_connection_error
    in nats_queue.py)
  - Cleaned up automatically when the event loop is garbage collected

Both strategies implement the same interface (get_connection, reset, close) so
TaskQueueManager is agnostic to which one is active.
"""

import asyncio
import logging
import threading
import typing
from typing import TYPE_CHECKING
from weakref import WeakKeyDictionary

import nats
from django.conf import settings
from nats.js import JetStreamContext

if TYPE_CHECKING:
    from nats.aio.client import Client as NATSClient

logger = logging.getLogger(__name__)


class ConnectionProvider(typing.Protocol):
    """Interface that all NATS connection strategies must implement."""

    async def get_connection(self) -> tuple["NATSClient", JetStreamContext]:
        ...

    async def reset(self) -> None:
        ...

    async def close(self) -> None:
        ...


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


class PerOperationConnection:
    """
    Creates a fresh NATS connection on every get_connection() call.

    Each call closes the previous connection (if any) and opens a new one.
    This avoids any shared state but is expensive: ~1500 TCP round-trips per
    1000-image job vs. 1 with the pool strategy.

    Use for debugging connection lifecycle issues or when the pool causes
    problems (e.g. event loop mismatch edge cases).
    """

    def __init__(self):
        self._nc: "NATSClient | None" = None
        self._js: JetStreamContext | None = None

    async def get_connection(self) -> tuple["NATSClient", JetStreamContext]:
        """Create a fresh NATS connection, closing any previous one."""
        # Close previous connection if it exists
        await self.close()

        nats_url = settings.NATS_URL
        try:
            logger.debug(f"Creating transient NATS connection to {nats_url}")
            self._nc = await nats.connect(nats_url)
            self._js = self._nc.jetstream()
            return self._nc, self._js
        except Exception as e:
            logger.error(f"Failed to connect to NATS: {e}")
            raise RuntimeError(f"Could not establish NATS connection: {e}") from e

    async def close(self):
        """Close the current connection if it exists."""
        if self._nc is not None and not self._nc.is_closed:
            try:
                await self._nc.close()
            except Exception as e:
                logger.debug(f"Error closing transient connection (expected): {e}")
        self._nc = None
        self._js = None

    async def reset(self):
        """Close and clear — next get_connection() creates a fresh one."""
        await self.close()


# Event-loop-keyed providers: one per event loop.
# WeakKeyDictionary automatically cleans up when event loops are garbage collected.
_providers: WeakKeyDictionary[asyncio.AbstractEventLoop, ConnectionProvider] = WeakKeyDictionary()
_providers_lock = threading.Lock()


def _create_provider() -> ConnectionProvider:
    """Create a connection provider based on the NATS_CONNECTION_STRATEGY setting."""
    strategy = settings.NATS_CONNECTION_STRATEGY
    if strategy == "per_operation":
        logger.info("Using NATS connection strategy: per_operation")
        return PerOperationConnection()
    logger.info("Using NATS connection strategy: pool (persistent)")
    return ConnectionPool()


def get_provider() -> ConnectionProvider:
    """
    Get or create the connection provider for the current event loop.

    Each event loop gets its own provider to prevent "attached to a different loop"
    errors. The provider type is determined by the NATS_CONNECTION_STRATEGY setting:
    - "pool" (default): persistent connection reuse via ConnectionPool
    - "per_operation": fresh connection each time via PerOperationConnection

    Returns:
        ConnectionProvider bound to the current event loop

    Raises:
        RuntimeError: If called outside of an async context (no running event loop)
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        raise RuntimeError(
            "get_provider() must be called from an async context with a running event loop. "
            "If calling from sync code, use async_to_sync() to wrap the async function."
        )

    with _providers_lock:
        if loop not in _providers:
            _providers[loop] = _create_provider()
            logger.debug(f"Created NATS connection provider for event loop {id(loop)}")
        return _providers[loop]
