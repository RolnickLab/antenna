"""Unit tests for TaskQueueManager."""

import unittest
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

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

        with patch("ami.ml.orchestration.nats_connection_pool.get_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_pool.get_connection = AsyncMock(return_value=(nc, js))
            mock_get_pool.return_value = mock_pool
            yield nc, js, mock_pool

    async def test_publish_task_creates_stream_and_consumer(self):
        """Test that publish_task ensures stream and consumer exist."""
        sample_task = self._create_sample_task()

        with self._mock_nats_setup() as (_, js, _):
            js.stream_info.side_effect = Exception("Not found")
            js.consumer_info.side_effect = Exception("Not found")

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
