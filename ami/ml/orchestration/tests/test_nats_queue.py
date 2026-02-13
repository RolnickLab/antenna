"""Unit tests for TaskQueueManager."""

import unittest
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from nats.js.errors import NotFoundError

from ami.ml.orchestration.nats_queue import TaskQueueManager
from ami.ml.schemas import PipelineProcessingTask


class TestTaskQueueManager(unittest.IsolatedAsyncioTestCase):
    """Test suite for TaskQueueManager."""

    def _create_sample_task(self):
        """Helper to create a sample PipelineProcessingTask."""
        return PipelineProcessingTask(
            id="task-123",
            image_id="img-456",
            image_url="https://example.com/image.jpg",
        )

    @contextmanager
    def _mock_nats_setup(self):
        """Helper to create and mock NATS connection with connection pool.

        Yields:
            tuple: (nc, js, mock_pool) - NATS connection, JetStream context, and mock pool
        """
        nc = MagicMock()
        nc.is_closed = False
        nc.close = AsyncMock()

        js = MagicMock()
        js.stream_info = AsyncMock()
        js.add_stream = AsyncMock()
        js.add_consumer = AsyncMock()
        js.consumer_info = AsyncMock()
        js.publish = AsyncMock(return_value=MagicMock(seq=1))
        js.pull_subscribe = AsyncMock()
        js.delete_consumer = AsyncMock()
        js.delete_stream = AsyncMock()

        with patch("ami.ml.orchestration.nats_connection.get_connection", new_callable=AsyncMock) as mock_get_conn:
            mock_get_conn.return_value = (nc, js)
            yield nc, js, mock_get_conn

    async def test_publish_task_creates_stream_and_consumer(self):
        """Test that publish_task ensures stream and consumer exist."""
        sample_task = self._create_sample_task()

        with self._mock_nats_setup() as (_, js, _):
            js.stream_info.side_effect = NotFoundError
            js.consumer_info.side_effect = NotFoundError

            manager = TaskQueueManager()
            await manager.publish_task(456, sample_task)

            js.add_stream.assert_called_once()
            self.assertIn("job_456", str(js.add_stream.call_args))
            js.add_consumer.assert_called_once()

    async def test_reserve_task_success(self):
        """Test successful task reservation."""
        sample_task = self._create_sample_task()

        # Mock message with task data
        mock_msg = MagicMock()
        mock_msg.data = sample_task.json().encode()
        mock_msg.reply = "reply.subject.123"
        mock_msg.metadata = MagicMock(sequence=MagicMock(stream=1))

        with self._mock_nats_setup() as (_, js, _):
            mock_psub = MagicMock()
            mock_psub.fetch = AsyncMock(return_value=[mock_msg])
            mock_psub.unsubscribe = AsyncMock()
            js.pull_subscribe = AsyncMock(return_value=mock_psub)

            manager = TaskQueueManager()
            task = await manager.reserve_task(123)

            self.assertIsNotNone(task)
            self.assertEqual(task.id, sample_task.id)
            self.assertEqual(task.reply_subject, "reply.subject.123")
            mock_psub.unsubscribe.assert_called_once()

    async def test_reserve_task_no_messages(self):
        """Test reserve_task when no messages are available."""
        with self._mock_nats_setup() as (_, js, _):
            mock_psub = MagicMock()
            mock_psub.fetch = AsyncMock(return_value=[])
            mock_psub.unsubscribe = AsyncMock()
            js.pull_subscribe = AsyncMock(return_value=mock_psub)

            manager = TaskQueueManager()
            task = await manager.reserve_task(123)

            self.assertIsNone(task)
            mock_psub.unsubscribe.assert_called_once()

    async def test_acknowledge_task_success(self):
        """Test successful task acknowledgment."""
        with self._mock_nats_setup() as (nc, _, _):
            nc.publish = AsyncMock()
            nc.flush = AsyncMock()

            manager = TaskQueueManager()
            result = await manager.acknowledge_task("reply.subject.123")

            self.assertTrue(result)
            nc.publish.assert_called_once_with("reply.subject.123", b"+ACK")
            nc.flush.assert_called_once()

    async def test_cleanup_job_resources(self):
        """Test cleanup of job resources (consumer and stream)."""
        with self._mock_nats_setup() as (_, js, _):
            manager = TaskQueueManager()
            result = await manager.cleanup_job_resources(123)

            self.assertTrue(result)
            js.delete_consumer.assert_called_once()
            js.delete_stream.assert_called_once()

    async def test_naming_conventions(self):
        """Test stream, subject, and consumer naming conventions."""
        manager = TaskQueueManager()

        self.assertEqual(manager._get_stream_name(123), "job_123")
        self.assertEqual(manager._get_subject(123), "job.123.tasks")
        self.assertEqual(manager._get_consumer_name(123), "job-123-consumer")


class TestRetryOnConnectionError(unittest.IsolatedAsyncioTestCase):
    """Test retry_on_connection_error decorator behavior."""

    def _create_sample_task(self):
        """Helper to create a sample PipelineProcessingTask."""
        return PipelineProcessingTask(
            id="task-retry-test",
            image_id="img-retry",
            image_url="https://example.com/retry.jpg",
        )

    async def test_retry_resets_connection_on_error(self):
        """On connection error, the decorator should call reset_connection() before retrying."""
        from nats.errors import ConnectionClosedError

        nc = MagicMock()
        nc.is_closed = False
        js = MagicMock()
        js.stream_info = AsyncMock()
        js.add_stream = AsyncMock()
        js.consumer_info = AsyncMock()
        js.add_consumer = AsyncMock()
        # First publish fails with connection error, second succeeds
        js.publish = AsyncMock(side_effect=[ConnectionClosedError(), MagicMock(seq=1)])
        js.pull_subscribe = AsyncMock()

        with (
            patch(
                "ami.ml.orchestration.nats_connection.get_connection",
                new_callable=AsyncMock,
                return_value=(nc, js),
            ),
            patch(
                "ami.ml.orchestration.nats_connection.reset_connection",
                new_callable=AsyncMock,
            ) as mock_reset,
        ):
            manager = TaskQueueManager()
            sample_task = self._create_sample_task()

            # Should succeed after retry
            with patch("ami.ml.orchestration.nats_queue.asyncio.sleep", new_callable=AsyncMock):
                result = await manager.publish_task(456, sample_task)

            self.assertTrue(result)
            # reset_connection() should have been called once (after first failure)
            mock_reset.assert_called_once()

    async def test_retry_raises_after_max_retries(self):
        """After exhausting retries, the last error should be raised."""
        from nats.errors import ConnectionClosedError

        nc = MagicMock()
        nc.is_closed = False
        js = MagicMock()
        js.stream_info = AsyncMock()
        js.add_stream = AsyncMock()
        js.consumer_info = AsyncMock()
        js.add_consumer = AsyncMock()
        # All attempts fail
        js.publish = AsyncMock(side_effect=ConnectionClosedError())

        with (
            patch(
                "ami.ml.orchestration.nats_connection.get_connection",
                new_callable=AsyncMock,
                return_value=(nc, js),
            ),
            patch(
                "ami.ml.orchestration.nats_connection.reset_connection",
                new_callable=AsyncMock,
            ) as mock_reset,
        ):
            manager = TaskQueueManager()
            sample_task = self._create_sample_task()

            with patch("ami.ml.orchestration.nats_queue.asyncio.sleep", new_callable=AsyncMock):
                with self.assertRaises(ConnectionClosedError):
                    await manager.publish_task(456, sample_task)

            # reset_connection() called twice (max_retries=2, so 2 retries means 2 resets)
            self.assertEqual(mock_reset.call_count, 2)

    async def test_non_connection_errors_are_not_retried(self):
        """Non-connection errors (e.g. ValueError) should propagate immediately without retry."""
        nc = MagicMock()
        nc.is_closed = False
        js = MagicMock()
        js.stream_info = AsyncMock()
        js.add_stream = AsyncMock()
        js.consumer_info = AsyncMock()
        js.add_consumer = AsyncMock()
        js.publish = AsyncMock(side_effect=ValueError("bad data"))

        with (
            patch(
                "ami.ml.orchestration.nats_connection.get_connection",
                new_callable=AsyncMock,
                return_value=(nc, js),
            ),
            patch(
                "ami.ml.orchestration.nats_connection.reset_connection",
                new_callable=AsyncMock,
            ) as mock_reset,
        ):
            manager = TaskQueueManager()
            sample_task = self._create_sample_task()

            with self.assertRaises(ValueError):
                await manager.publish_task(456, sample_task)

            # reset_connection() should NOT have been called
            mock_reset.assert_not_called()
