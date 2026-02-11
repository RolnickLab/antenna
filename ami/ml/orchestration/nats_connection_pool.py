"""
NATS connection pool for both Celery workers and Django processes.

Maintains a persistent NATS connection per process to avoid
the overhead of creating/closing connections for every operation.

The connection pool is lazily initialized on first use and shared
across all operations in the same process.
"""

import asyncio
import logging
from typing import TYPE_CHECKING

import nats
from django.conf import settings
from nats.js import JetStreamContext

if TYPE_CHECKING:
    from nats.aio.client import Client as NATSClient

logger = logging.getLogger(__name__)


class ConnectionPool:
    """
    Manages a single NATS connection per process (Celery worker or Django web worker).

    This is safe because:
    - Each process gets its own isolated connection
    - NATS connections are async-safe (can be used by multiple coroutines)
    - Works in both Celery prefork and Django WSGI/ASGI contexts
    """

    def __init__(self):
        self._nc: "NATSClient | None" = None
        self._js: JetStreamContext | None = None
        self._nats_url: str | None = None
        self._lock = asyncio.Lock()

    async def get_connection(self) -> tuple["NATSClient", JetStreamContext]:
        """
        Get or create the worker's NATS connection. Checks connection health and recreates if stale.

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
        async with self._lock:
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

    def reset(self):
        """
        Reset the connection pool (mark connection as stale).

        This should be called when a connection error is detected.
        The next call to get_connection() will create a fresh connection.
        """
        logger.warning("Resetting NATS connection pool due to connection error")
        self._nc = None
        self._js = None


# Global pool instance - one per process (Celery worker or Django process)
_connection_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    """
    Get the process-local connection pool.
    """
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = ConnectionPool()
        logger.debug("Lazily initialized NATS connection pool")
    return _connection_pool
