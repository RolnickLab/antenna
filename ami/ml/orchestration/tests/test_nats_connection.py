"""Unit tests for nats_connection module."""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from ami.ml.orchestration.nats_connection import ConnectionPool


class TestConnectionPoolBehavior(unittest.IsolatedAsyncioTestCase):
    """Test ConnectionPool lifecycle and connection reuse."""

    @patch("ami.ml.orchestration.nats_connection.nats")
    @patch("ami.ml.orchestration.nats_connection.settings")
    async def test_get_connection_creates_connection(self, mock_settings, mock_nats):
        """Test that get_connection creates a connection on first call."""
        mock_settings.NATS_URL = "nats://test:4222"

        mock_nc = MagicMock()
        mock_nc.is_closed = False
        mock_nc.is_connected = True
        mock_nc.close = AsyncMock()
        mock_js = MagicMock()
        mock_nc.jetstream.return_value = mock_js

        mock_nats.connect = AsyncMock(return_value=mock_nc)

        pool = ConnectionPool()
        nc, js = await pool.get_connection()

        self.assertIs(nc, mock_nc)
        self.assertIs(js, mock_js)
        mock_nats.connect.assert_called_once_with("nats://test:4222")

    @patch("ami.ml.orchestration.nats_connection.nats")
    @patch("ami.ml.orchestration.nats_connection.settings")
    async def test_get_connection_reuses_existing_connection(self, mock_settings, mock_nats):
        """Test that get_connection reuses connection on subsequent calls."""
        mock_settings.NATS_URL = "nats://test:4222"

        mock_nc = MagicMock()
        mock_nc.is_closed = False
        mock_nc.is_connected = True
        mock_nc.close = AsyncMock()
        mock_js = MagicMock()
        mock_nc.jetstream.return_value = mock_js

        mock_nats.connect = AsyncMock(return_value=mock_nc)

        pool = ConnectionPool()

        # First call
        nc1, js1 = await pool.get_connection()
        # Second call
        nc2, js2 = await pool.get_connection()

        # Should only connect once
        self.assertEqual(mock_nats.connect.call_count, 1)
        self.assertIs(nc1, nc2)
        self.assertIs(js1, js2)

    @patch("ami.ml.orchestration.nats_connection.nats")
    @patch("ami.ml.orchestration.nats_connection.settings")
    async def test_get_connection_reconnects_if_closed(self, mock_settings, mock_nats):
        """Test that get_connection reconnects if the connection is closed."""
        mock_settings.NATS_URL = "nats://test:4222"

        mock_nc1 = MagicMock()
        mock_nc1.is_closed = True
        mock_nc1.is_connected = False
        mock_nc1.close = AsyncMock()

        mock_nc2 = MagicMock()
        mock_nc2.is_closed = False
        mock_nc2.is_connected = True
        mock_nc2.close = AsyncMock()
        mock_js2 = MagicMock()
        mock_nc2.jetstream.return_value = mock_js2

        mock_nats.connect = AsyncMock(side_effect=[mock_nc2])

        pool = ConnectionPool()
        pool._nc = mock_nc1
        pool._js = MagicMock()

        # This should detect the connection is closed and reconnect
        nc, js = await pool.get_connection()

        self.assertIs(nc, mock_nc2)
        self.assertIs(js, mock_js2)
        mock_nats.connect.assert_called_once()

    @patch("ami.ml.orchestration.nats_connection.nats")
    @patch("ami.ml.orchestration.nats_connection.settings")
    async def test_get_connection_raises_on_connection_error(self, mock_settings, mock_nats):
        """Test that get_connection raises RuntimeError on connection failure."""
        mock_settings.NATS_URL = "nats://test:4222"

        mock_nats.connect = AsyncMock(side_effect=ConnectionError("Connection failed"))

        pool = ConnectionPool()

        with self.assertRaises(RuntimeError) as context:
            await pool.get_connection()

        self.assertIn("Could not establish NATS connection", str(context.exception))

    @patch("ami.ml.orchestration.nats_connection.nats")
    @patch("ami.ml.orchestration.nats_connection.settings")
    async def test_close_closes_connection(self, mock_settings, mock_nats):
        """Test that close() closes the connection."""
        mock_settings.NATS_URL = "nats://test:4222"

        mock_nc = MagicMock()
        mock_nc.is_closed = False
        mock_nc.is_connected = True
        mock_nc.close = AsyncMock()
        mock_js = MagicMock()
        mock_nc.jetstream.return_value = mock_js

        mock_nats.connect = AsyncMock(return_value=mock_nc)

        pool = ConnectionPool()
        await pool.get_connection()

        await pool.close()

        mock_nc.close.assert_called_once()
        self.assertIsNone(pool._nc)
        self.assertIsNone(pool._js)

    @patch("ami.ml.orchestration.nats_connection.nats")
    @patch("ami.ml.orchestration.nats_connection.settings")
    async def test_reset_closes_and_clears_state(self, mock_settings, mock_nats):
        """Test that reset() closes connection and clears all state."""
        mock_settings.NATS_URL = "nats://test:4222"

        mock_nc = MagicMock()
        mock_nc.is_closed = False
        mock_nc.is_connected = True
        mock_nc.close = AsyncMock()
        mock_js = MagicMock()
        mock_nc.jetstream.return_value = mock_js

        mock_nats.connect = AsyncMock(return_value=mock_nc)

        pool = ConnectionPool()
        await pool.get_connection()

        # Set the lock so we can verify it gets cleared
        pool._lock = asyncio.Lock()

        await pool.reset()

        mock_nc.close.assert_called_once()
        self.assertIsNone(pool._nc)
        self.assertIsNone(pool._js)
        self.assertIsNone(pool._lock)


class TestModuleLevelFunctions(unittest.IsolatedAsyncioTestCase):
    """Test module-level get_connection() and reset_connection() functions."""

    @patch("ami.ml.orchestration.nats_connection.nats")
    @patch("ami.ml.orchestration.nats_connection.settings")
    async def test_get_connection_returns_connection(self, mock_settings, mock_nats):
        """Test that module-level get_connection() returns a NATS connection."""
        from ami.ml.orchestration.nats_connection import _pools, get_connection

        mock_settings.NATS_URL = "nats://test:4222"
        mock_nc = MagicMock()
        mock_nc.is_closed = False
        mock_nc.is_connected = True
        mock_nc.close = AsyncMock()
        mock_js = MagicMock()
        mock_nc.jetstream.return_value = mock_js
        mock_nats.connect = AsyncMock(return_value=mock_nc)

        # Clear pools to avoid leaking state between tests
        _pools.clear()

        nc, js = await get_connection()

        self.assertIs(nc, mock_nc)
        self.assertIs(js, mock_js)

    @patch("ami.ml.orchestration.nats_connection.nats")
    @patch("ami.ml.orchestration.nats_connection.settings")
    async def test_get_connection_reuses_pool_for_same_loop(self, mock_settings, mock_nats):
        """Test that repeated calls on the same loop reuse the same pool."""
        from ami.ml.orchestration.nats_connection import _pools, get_connection

        mock_settings.NATS_URL = "nats://test:4222"
        mock_nc = MagicMock()
        mock_nc.is_closed = False
        mock_nc.is_connected = True
        mock_nc.close = AsyncMock()
        mock_js = MagicMock()
        mock_nc.jetstream.return_value = mock_js
        mock_nats.connect = AsyncMock(return_value=mock_nc)

        _pools.clear()

        await get_connection()
        await get_connection()

        # Only one TCP connection should have been created
        mock_nats.connect.assert_called_once()

    @patch("ami.ml.orchestration.nats_connection.nats")
    @patch("ami.ml.orchestration.nats_connection.settings")
    async def test_reset_connection_clears_pool(self, mock_settings, mock_nats):
        """Test that reset_connection() resets the pool for the current loop."""
        from ami.ml.orchestration.nats_connection import _pools, get_connection, reset_connection

        mock_settings.NATS_URL = "nats://test:4222"
        mock_nc = MagicMock()
        mock_nc.is_closed = False
        mock_nc.is_connected = True
        mock_nc.close = AsyncMock()
        mock_js = MagicMock()
        mock_nc.jetstream.return_value = mock_js
        mock_nats.connect = AsyncMock(return_value=mock_nc)

        _pools.clear()

        await get_connection()
        await reset_connection()

        mock_nc.close.assert_called_once()

    def test_get_connection_raises_without_event_loop(self):
        """Test that _get_pool raises RuntimeError outside async context."""
        from ami.ml.orchestration.nats_connection import _get_pool

        with self.assertRaises(RuntimeError) as context:
            _get_pool()

        self.assertIn("must be called from an async context", str(context.exception))
