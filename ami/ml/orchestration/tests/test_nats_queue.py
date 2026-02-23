"""Unit tests for TaskQueueManager."""

import unittest
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

    def _create_mock_nats_connection(self):
        """Helper to create mock NATS connection and JetStream context."""
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

        return nc, js

    async def test_context_manager_lifecycle(self):
        """Test that context manager properly opens and closes connections."""
        nc, js = self._create_mock_nats_connection()

        with patch("ami.ml.orchestration.nats_queue.get_connection", AsyncMock(return_value=(nc, js))):
            async with TaskQueueManager("nats://test:4222") as manager:
                self.assertIsNotNone(manager.nc)
                self.assertIsNotNone(manager.js)

            nc.close.assert_called_once()

    async def test_publish_task_creates_stream_and_consumer(self):
        """Test that publish_task ensures stream and consumer exist."""
        nc, js = self._create_mock_nats_connection()
        sample_task = self._create_sample_task()
        js.stream_info.side_effect = Exception("Not found")
        js.consumer_info.side_effect = Exception("Not found")

        with patch("ami.ml.orchestration.nats_queue.get_connection", AsyncMock(return_value=(nc, js))):
            async with TaskQueueManager() as manager:
                await manager.publish_task(456, sample_task)

                js.add_stream.assert_called_once()
                self.assertIn("job_456", str(js.add_stream.call_args))
                js.add_consumer.assert_called_once()

    async def test_reserve_tasks_success(self):
        """Test successful batch task reservation."""
        nc, js = self._create_mock_nats_connection()
        sample_task = self._create_sample_task()

        # Mock messages with task data
        mock_msg1 = MagicMock()
        mock_msg1.data = sample_task.json().encode()
        mock_msg1.reply = "reply.subject.1"

        mock_msg2 = MagicMock()
        mock_msg2.data = sample_task.json().encode()
        mock_msg2.reply = "reply.subject.2"

        mock_psub = MagicMock()
        mock_psub.fetch = AsyncMock(return_value=[mock_msg1, mock_msg2])
        mock_psub.unsubscribe = AsyncMock()
        js.pull_subscribe = AsyncMock(return_value=mock_psub)

        with patch("ami.ml.orchestration.nats_queue.get_connection", AsyncMock(return_value=(nc, js))):
            async with TaskQueueManager() as manager:
                tasks = await manager.reserve_tasks(123, count=5)

                self.assertEqual(len(tasks), 2)
                self.assertEqual(tasks[0].id, sample_task.id)
                self.assertEqual(tasks[0].reply_subject, "reply.subject.1")
                self.assertEqual(tasks[1].reply_subject, "reply.subject.2")
                mock_psub.fetch.assert_called_once_with(5, timeout=5)
                mock_psub.unsubscribe.assert_called_once()

    async def test_reserve_tasks_no_messages(self):
        """Test reserve_tasks when no messages are available (timeout)."""
        nc, js = self._create_mock_nats_connection()
        import nats.errors

        mock_psub = MagicMock()
        mock_psub.fetch = AsyncMock(side_effect=nats.errors.TimeoutError)
        mock_psub.unsubscribe = AsyncMock()
        js.pull_subscribe = AsyncMock(return_value=mock_psub)

        with patch("ami.ml.orchestration.nats_queue.get_connection", AsyncMock(return_value=(nc, js))):
            async with TaskQueueManager() as manager:
                tasks = await manager.reserve_tasks(123, count=5)

                self.assertEqual(tasks, [])
                mock_psub.unsubscribe.assert_called_once()

    async def test_reserve_tasks_single(self):
        """Test reserving a single task."""
        nc, js = self._create_mock_nats_connection()
        sample_task = self._create_sample_task()

        mock_msg = MagicMock()
        mock_msg.data = sample_task.json().encode()
        mock_msg.reply = "reply.subject.123"

        mock_psub = MagicMock()
        mock_psub.fetch = AsyncMock(return_value=[mock_msg])
        mock_psub.unsubscribe = AsyncMock()
        js.pull_subscribe = AsyncMock(return_value=mock_psub)

        with patch("ami.ml.orchestration.nats_queue.get_connection", AsyncMock(return_value=(nc, js))):
            async with TaskQueueManager() as manager:
                tasks = await manager.reserve_tasks(123, count=1)

                self.assertEqual(len(tasks), 1)
                self.assertEqual(tasks[0].reply_subject, "reply.subject.123")

    async def test_acknowledge_task_success(self):
        """Test successful task acknowledgment."""
        nc, js = self._create_mock_nats_connection()
        nc.publish = AsyncMock()

        with patch("ami.ml.orchestration.nats_queue.get_connection", AsyncMock(return_value=(nc, js))):
            async with TaskQueueManager() as manager:
                result = await manager.acknowledge_task("reply.subject.123")

                self.assertTrue(result)
                nc.publish.assert_called_once_with("reply.subject.123", b"+ACK")

    async def test_cleanup_job_resources(self):
        """Test cleanup of job resources (consumer and stream)."""
        nc, js = self._create_mock_nats_connection()

        with patch("ami.ml.orchestration.nats_queue.get_connection", AsyncMock(return_value=(nc, js))):
            async with TaskQueueManager() as manager:
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

    async def test_operations_without_connection_raise_error(self):
        """Test that operations without connection raise RuntimeError."""
        manager = TaskQueueManager()
        sample_task = self._create_sample_task()

        with self.assertRaisesRegex(RuntimeError, "Connection is not open"):
            await manager.publish_task(123, sample_task)

        with self.assertRaisesRegex(RuntimeError, "Connection is not open"):
            await manager.reserve_tasks(123, count=1)

        with self.assertRaisesRegex(RuntimeError, "Connection is not open"):
            await manager.delete_stream(123)
