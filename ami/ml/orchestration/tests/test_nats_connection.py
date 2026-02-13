"""Unit tests for nats_connection module."""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from ami.ml.orchestration.nats_connection import ConnectionPool, PerOperationConnection, _create_provider


class TestCreateProvider(unittest.TestCase):
    """Test _create_provider() returns the correct strategy based on settings."""

    @patch("ami.ml.orchestration.nats_connection.settings")
    def test_default_strategy_returns_connection_pool(self, mock_settings):
        """Test that default (unspecified) strategy returns ConnectionPool."""
        mock_settings.NATS_CONNECTION_STRATEGY = "pool"
        provider = _create_provider()
        self.assertIsInstance(provider, ConnectionPool)

    @patch("ami.ml.orchestration.nats_connection.settings")
    def test_per_operation_strategy_returns_per_operation_connection(self, mock_settings):
        """Test that per_operation strategy returns PerOperationConnection."""
        mock_settings.NATS_CONNECTION_STRATEGY = "per_operation"
        provider = _create_provider()
        self.assertIsInstance(provider, PerOperationConnection)

    @patch("ami.ml.orchestration.nats_connection.settings")
    def test_unknown_strategy_falls_back_to_pool(self, mock_settings):
        """Test that unknown strategy falls back to ConnectionPool."""
        mock_settings.NATS_CONNECTION_STRATEGY = "unknown_value"
        provider = _create_provider()
        self.assertIsInstance(provider, ConnectionPool)

    @patch("ami.ml.orchestration.nats_connection.settings")
    def test_empty_string_strategy_falls_back_to_pool(self, mock_settings):
        """Test that empty string strategy falls back to ConnectionPool."""
        mock_settings.NATS_CONNECTION_STRATEGY = ""
        provider = _create_provider()
        self.assertIsInstance(provider, ConnectionPool)


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


class TestPerOperationConnectionBehavior(unittest.IsolatedAsyncioTestCase):
    """Test PerOperationConnection lifecycle behavior."""

    @patch("ami.ml.orchestration.nats_connection.nats")
    @patch("ami.ml.orchestration.nats_connection.settings")
    async def test_get_connection_creates_connection(self, mock_settings, mock_nats):
        """Test that get_connection creates a fresh connection."""
        mock_settings.NATS_URL = "nats://test:4222"

        mock_nc = MagicMock()
        mock_nc.is_closed = False
        mock_nc.close = AsyncMock()
        mock_js = MagicMock()
        mock_nc.jetstream.return_value = mock_js

        mock_nats.connect = AsyncMock(return_value=mock_nc)

        conn = PerOperationConnection()
        nc, js = await conn.get_connection()

        self.assertIs(nc, mock_nc)
        self.assertIs(js, mock_js)
        mock_nats.connect.assert_called_once_with("nats://test:4222")

    @patch("ami.ml.orchestration.nats_connection.nats")
    @patch("ami.ml.orchestration.nats_connection.settings")
    async def test_get_connection_closes_previous(self, mock_settings, mock_nats):
        """Test that each get_connection() call closes the previous connection."""
        mock_settings.NATS_URL = "nats://test:4222"

        # Create two mock connections (MagicMock because jetstream() is sync)
        mock_nc1 = MagicMock()
        mock_nc1.is_closed = False
        mock_nc1.close = AsyncMock()
        mock_nc1.jetstream.return_value = MagicMock()

        mock_nc2 = MagicMock()
        mock_nc2.is_closed = False
        mock_nc2.close = AsyncMock()
        mock_nc2.jetstream.return_value = MagicMock()

        mock_nats.connect = AsyncMock(side_effect=[mock_nc1, mock_nc2])

        conn = PerOperationConnection()

        # First call
        nc1, _ = await conn.get_connection()
        self.assertIs(nc1, mock_nc1)

        # Second call should close the first connection
        nc2, _ = await conn.get_connection()
        self.assertIs(nc2, mock_nc2)

        # Verify first connection was closed
        mock_nc1.close.assert_called_once()

    @patch("ami.ml.orchestration.nats_connection.nats")
    @patch("ami.ml.orchestration.nats_connection.settings")
    async def test_get_connection_handles_close_errors(self, mock_settings, mock_nats):
        """Test that get_connection handles errors when closing previous connection."""
        mock_settings.NATS_URL = "nats://test:4222"

        # First connection throws error on close
        mock_nc1 = MagicMock()
        mock_nc1.is_closed = False
        mock_nc1.close = AsyncMock(side_effect=RuntimeError("Close error"))
        mock_nc1.jetstream.return_value = MagicMock()

        # Second connection succeeds
        mock_nc2 = MagicMock()
        mock_nc2.is_closed = False
        mock_nc2.close = AsyncMock()
        mock_nc2.jetstream.return_value = MagicMock()

        mock_nats.connect = AsyncMock(side_effect=[mock_nc1, mock_nc2])

        conn = PerOperationConnection()

        # First call
        await conn.get_connection()

        # Second call should not raise even though closing first connection fails
        nc2, _ = await conn.get_connection()
        self.assertIs(nc2, mock_nc2)

    @patch("ami.ml.orchestration.nats_connection.nats")
    @patch("ami.ml.orchestration.nats_connection.settings")
    async def test_reset_closes_connection(self, mock_settings, mock_nats):
        """Test that reset() closes the current connection."""
        mock_settings.NATS_URL = "nats://test:4222"

        mock_nc = MagicMock()
        mock_nc.is_closed = False
        mock_nc.close = AsyncMock()
        mock_nc.jetstream.return_value = MagicMock()

        mock_nats.connect = AsyncMock(return_value=mock_nc)

        conn = PerOperationConnection()
        await conn.get_connection()

        await conn.reset()

        mock_nc.close.assert_called_once()
        # After reset, internal state should be cleared
        self.assertIsNone(conn._nc)
        self.assertIsNone(conn._js)

    @patch("ami.ml.orchestration.nats_connection.nats")
    @patch("ami.ml.orchestration.nats_connection.settings")
    async def test_close_closes_connection(self, mock_settings, mock_nats):
        """Test that close() closes the connection."""
        mock_settings.NATS_URL = "nats://test:4222"

        mock_nc = MagicMock()
        mock_nc.is_closed = False
        mock_nc.close = AsyncMock()
        mock_nc.jetstream.return_value = MagicMock()

        mock_nats.connect = AsyncMock(return_value=mock_nc)

        conn = PerOperationConnection()
        await conn.get_connection()

        await conn.close()

        mock_nc.close.assert_called_once()
        self.assertIsNone(conn._nc)
        self.assertIsNone(conn._js)

    @patch("ami.ml.orchestration.nats_connection.nats")
    @patch("ami.ml.orchestration.nats_connection.settings")
    async def test_get_connection_raises_on_connection_error(self, mock_settings, mock_nats):
        """Test that get_connection raises RuntimeError on connection failure."""
        mock_settings.NATS_URL = "nats://test:4222"

        mock_nats.connect = AsyncMock(side_effect=ConnectionError("Connection failed"))

        conn = PerOperationConnection()

        with self.assertRaises(RuntimeError) as context:
            await conn.get_connection()

        self.assertIn("Could not establish NATS connection", str(context.exception))
