"""Unit tests for TaskQueueManager."""

import json
import logging
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import nats
import nats.errors

from ami.ml.orchestration.nats_queue import ADVISORY_STREAM_NAME, TaskQueueManager
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
        nc.flush = AsyncMock()

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
        js.stream_info.side_effect = nats.js.errors.NotFoundError()
        js.consumer_info.side_effect = nats.js.errors.NotFoundError()

        with patch("ami.ml.orchestration.nats_queue.get_connection", AsyncMock(return_value=(nc, js))):
            async with TaskQueueManager() as manager:
                await manager.publish_task(456, sample_task)

                # add_stream called twice: advisory stream in __aenter__ + job stream in _ensure_stream
                self.assertEqual(js.add_stream.call_count, 2)
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
                # delete_consumer called twice: job consumer + DLQ advisory consumer
                self.assertEqual(js.delete_consumer.call_count, 2)
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

    async def test_get_dead_letter_image_ids_returns_image_ids(self):
        """Test that advisory messages are resolved to image IDs correctly."""
        nc, js = self._create_mock_nats_connection()
        js.get_msg = AsyncMock()

        def make_advisory(seq):
            m = MagicMock()
            m.data = json.dumps({"stream_seq": seq}).encode()
            m.ack = AsyncMock()
            return m

        def make_job_msg(image_id):
            m = MagicMock()
            m.data = json.dumps({"image_id": image_id}).encode()
            return m

        advisories = [make_advisory(1), make_advisory(2)]
        js.get_msg.side_effect = [make_job_msg("img-1"), make_job_msg("img-2")]

        mock_psub = MagicMock()
        mock_psub.fetch = AsyncMock(return_value=advisories)
        mock_psub.unsubscribe = AsyncMock()
        js.pull_subscribe = AsyncMock(return_value=mock_psub)

        with patch("ami.ml.orchestration.nats_queue.get_connection", AsyncMock(return_value=(nc, js))):
            async with TaskQueueManager() as manager:
                result = await manager.get_dead_letter_image_ids(123, n=10)

        self.assertEqual(result, ["img-1", "img-2"])
        js.pull_subscribe.assert_called_once_with(
            "$JS.EVENT.ADVISORY.CONSUMER.MAX_DELIVERIES.job_123.job-123-consumer",
            durable="job-123-dlq",
            stream=ADVISORY_STREAM_NAME,
        )
        mock_psub.fetch.assert_called_once_with(10, timeout=1.0)
        mock_psub.unsubscribe.assert_called_once()

    async def test_get_dead_letter_image_ids_no_messages(self):
        """Test that a fetch timeout returns an empty list and still unsubscribes."""
        nc, js = self._create_mock_nats_connection()

        mock_psub = MagicMock()
        mock_psub.fetch = AsyncMock(side_effect=nats.errors.TimeoutError)
        mock_psub.unsubscribe = AsyncMock()
        js.pull_subscribe = AsyncMock(return_value=mock_psub)

        with patch("ami.ml.orchestration.nats_queue.get_connection", AsyncMock(return_value=(nc, js))):
            async with TaskQueueManager() as manager:
                result = await manager.get_dead_letter_image_ids(123)

        self.assertEqual(result, [])
        mock_psub.unsubscribe.assert_called_once()


class TestTaskQueueManagerJobLogger(unittest.IsolatedAsyncioTestCase):
    """Tests covering the job_logger lifecycle-mirroring behavior (#1220)."""

    def _create_sample_task(self):
        return PipelineProcessingTask(
            id="task-1",
            image_id="img-1",
            image_url="https://example.com/image.jpg",
        )

    def _create_mock_nats_connection(self):
        """Duplicate of the sibling helper — kept local so the two test classes
        can evolve independently."""
        nc = MagicMock()
        nc.is_closed = False
        nc.close = AsyncMock()
        nc.flush = AsyncMock()

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

    def _make_consumer_info(
        self,
        delivered=10,
        ack_floor=8,
        num_pending=2,
        num_ack_pending=2,
        num_redelivered=1,
        max_deliver=5,
        ack_wait=30,
        max_ack_pending=1000,
        deliver_policy="all",
        ack_policy="explicit",
    ):
        """Build a ConsumerInfo-like MagicMock with nested SequenceInfo stubs
        and a config sub-object for creation-time logging."""
        info = MagicMock()
        info.delivered = MagicMock(consumer_seq=delivered)
        info.ack_floor = MagicMock(consumer_seq=ack_floor)
        info.num_pending = num_pending
        info.num_ack_pending = num_ack_pending
        info.num_redelivered = num_redelivered
        info.config = MagicMock(
            max_deliver=max_deliver,
            ack_wait=ack_wait,
            max_ack_pending=max_ack_pending,
            deliver_policy=deliver_policy,
            ack_policy=ack_policy,
        )
        return info

    def _make_stream_info(self, messages=5, last_seq=5):
        info = MagicMock()
        info.state = MagicMock(messages=messages, last_seq=last_seq)
        return info

    def _make_captured_logger(self) -> logging.Logger:
        """A real Logger that captures to a list — better than MagicMock.log
        because it exercises the actual `logger.log(level, msg)` dispatch and
        surfaces any type surprises in the call site."""
        log_logger = logging.getLogger(f"test.job_logger.{id(self)}")
        log_logger.handlers.clear()
        log_logger.setLevel(logging.DEBUG)

        captured = []

        class CaptureHandler(logging.Handler):
            def emit(self, record):
                captured.append((record.levelno, record.getMessage()))

        log_logger.addHandler(CaptureHandler())
        log_logger._captured = captured  # type: ignore[attr-defined]
        return log_logger

    async def test_create_stream_and_consumer_logs_to_job_logger(self):
        """First publish on a brand-new job should log stream/consumer creation
        to both the module logger and the passed-in job_logger."""
        nc, js = self._create_mock_nats_connection()
        js.stream_info.side_effect = nats.js.errors.NotFoundError()
        js.consumer_info.side_effect = nats.js.errors.NotFoundError()
        js.add_consumer = AsyncMock(return_value=self._make_consumer_info(delivered=0, ack_floor=0))

        job_logger = self._make_captured_logger()
        captured = job_logger._captured  # type: ignore[attr-defined]

        with patch("ami.ml.orchestration.nats_queue.get_connection", AsyncMock(return_value=(nc, js))):
            async with TaskQueueManager(job_logger=job_logger) as manager:
                await manager.publish_task(42, self._create_sample_task())

        messages = [m for _, m in captured]
        self.assertTrue(
            any("Created NATS stream job_42" in m for m in messages),
            f"expected stream-create log on job_logger, got {messages}",
        )
        self.assertTrue(
            any("Created NATS consumer job-42-consumer" in m for m in messages),
            f"expected consumer-create log on job_logger, got {messages}",
        )
        # Config snapshot should appear on the creation line.
        self.assertTrue(
            any("max_deliver=5" in m and "ack_policy=" in m for m in messages),
            f"expected consumer config snapshot in log, got {messages}",
        )

    async def test_publish_success_does_not_spam_job_logger(self):
        """After the first publish, subsequent publishes in the same session
        must NOT emit new setup lines — per-message logging is forbidden for
        10k-image jobs."""
        nc, js = self._create_mock_nats_connection()
        # First call hits NotFound (create path), subsequent calls succeed (reuse path)
        js.stream_info.side_effect = [nats.js.errors.NotFoundError(), self._make_stream_info()]
        js.consumer_info.side_effect = [nats.js.errors.NotFoundError(), self._make_consumer_info()]
        js.add_consumer = AsyncMock(return_value=self._make_consumer_info(delivered=0, ack_floor=0))

        job_logger = self._make_captured_logger()
        captured = job_logger._captured  # type: ignore[attr-defined]

        with patch("ami.ml.orchestration.nats_queue.get_connection", AsyncMock(return_value=(nc, js))):
            async with TaskQueueManager(job_logger=job_logger) as manager:
                await manager.publish_task(42, self._create_sample_task())
                captured_after_first = list(captured)
                await manager.publish_task(42, self._create_sample_task())

        new_messages = captured[len(captured_after_first) :]
        # The second publish should not add any lifecycle log lines — dedup set
        # should swallow them after the first publish for this job_id.
        lifecycle_terms = ("Created NATS", "Reusing NATS")
        for _, m in new_messages:
            self.assertFalse(
                any(term in m for term in lifecycle_terms),
                f"unexpected lifecycle log on second publish: {m}",
            )

    async def test_reuse_stream_and_consumer_logs_with_stats(self):
        """When stream and consumer already exist, the reuse line should include
        a summary of current consumer state so forensic readers can tell whether
        the queue is empty, backed up, or mid-redelivery."""
        nc, js = self._create_mock_nats_connection()
        js.stream_info.return_value = self._make_stream_info(messages=17, last_seq=17)
        js.consumer_info.return_value = self._make_consumer_info(
            delivered=12, ack_floor=10, num_pending=5, num_ack_pending=2, num_redelivered=3
        )

        job_logger = self._make_captured_logger()
        captured = job_logger._captured  # type: ignore[attr-defined]

        with patch("ami.ml.orchestration.nats_queue.get_connection", AsyncMock(return_value=(nc, js))):
            async with TaskQueueManager(job_logger=job_logger) as manager:
                await manager.publish_task(99, self._create_sample_task())

        messages = [m for _, m in captured]
        self.assertTrue(
            any("Reusing NATS stream job_99" in m and "messages=17" in m and "last_seq=17" in m for m in messages),
            f"expected reuse-stream log with state, got {messages}",
        )
        self.assertTrue(
            any(
                "Reusing NATS consumer job-99-consumer" in m
                and "delivered=12" in m
                and "ack_floor=10" in m
                and "num_pending=5" in m
                and "num_redelivered=3" in m
                for m in messages
            ),
            f"expected reuse-consumer log with stats, got {messages}",
        )

    async def test_cleanup_logs_final_consumer_stats_before_delete(self):
        """cleanup_job_resources must emit a forensic snapshot of the consumer
        state BEFORE the delete calls land. This is the single most useful line
        for a post-mortem — without it, the consumer is already gone by the
        time anyone investigates."""
        nc, js = self._create_mock_nats_connection()
        final_info = self._make_consumer_info(
            delivered=434, ack_floor=420, num_pending=0, num_ack_pending=14, num_redelivered=5
        )
        js.consumer_info.return_value = final_info

        job_logger = self._make_captured_logger()
        captured = job_logger._captured  # type: ignore[attr-defined]

        with patch("ami.ml.orchestration.nats_queue.get_connection", AsyncMock(return_value=(nc, js))):
            async with TaskQueueManager(job_logger=job_logger) as manager:
                await manager.cleanup_job_resources(123)

        messages = [m for _, m in captured]
        finalizing_idx = None
        delete_idx = None
        for i, m in enumerate(messages):
            if "Finalizing NATS consumer job-123-consumer" in m:
                finalizing_idx = i
            if delete_idx is None and "Deleted NATS consumer job-123-consumer" in m:
                delete_idx = i

        self.assertIsNotNone(finalizing_idx, f"expected forensic finalize-log, got {messages}")
        self.assertIsNotNone(delete_idx, f"expected delete-log, got {messages}")
        self.assertLess(
            finalizing_idx,  # type: ignore[arg-type]
            delete_idx,  # type: ignore[arg-type]
            "finalize snapshot must log BEFORE the delete",
        )
        # The stats themselves should make it into the line.
        final_line = messages[finalizing_idx]  # type: ignore[index]
        for expected in ("delivered=434", "ack_floor=420", "num_redelivered=5"):
            self.assertIn(expected, final_line)

    async def test_cleanup_tolerates_missing_consumer(self):
        """If the consumer is already gone when cleanup runs, the pre-delete
        stats call must NOT raise or block — cleanup is called in failure
        paths where the consumer may have already been deleted."""
        nc, js = self._create_mock_nats_connection()
        js.consumer_info.side_effect = nats.js.errors.NotFoundError()

        job_logger = self._make_captured_logger()

        with patch("ami.ml.orchestration.nats_queue.get_connection", AsyncMock(return_value=(nc, js))):
            async with TaskQueueManager(job_logger=job_logger) as manager:
                # Must not raise.
                result = await manager.cleanup_job_resources(77)

        # delete_consumer / delete_stream are still called on the mock and
        # return truthy, so overall cleanup is reported successful.
        self.assertTrue(result)

    async def test_publish_failure_surfaces_on_job_logger(self):
        """A failed publish (which today only logs to the module logger) must
        now also land on the job_logger so users see the failure in the UI."""
        nc, js = self._create_mock_nats_connection()
        js.stream_info.return_value = self._make_stream_info()
        js.consumer_info.return_value = self._make_consumer_info()
        js.publish = AsyncMock(side_effect=RuntimeError("simulated nats outage"))

        job_logger = self._make_captured_logger()
        captured = job_logger._captured  # type: ignore[attr-defined]

        with patch("ami.ml.orchestration.nats_queue.get_connection", AsyncMock(return_value=(nc, js))):
            async with TaskQueueManager(job_logger=job_logger) as manager:
                result = await manager.publish_task(55, self._create_sample_task())

        self.assertFalse(result)
        messages = [m for level, m in captured if level >= logging.ERROR]
        self.assertTrue(
            any("Failed to publish task" in m and "simulated nats outage" in m for m in messages),
            f"expected publish failure on job_logger, got {messages}",
        )

    async def test_log_consumer_stats_snapshot_writes_current_stats(self):
        """The periodic snapshot helper logs delivered/ack/pending WITHOUT
        deleting the consumer — it's a mid-flight observability hook."""
        nc, js = self._create_mock_nats_connection()
        js.consumer_info.return_value = self._make_consumer_info(
            delivered=50, ack_floor=40, num_pending=10, num_ack_pending=10, num_redelivered=2
        )

        job_logger = self._make_captured_logger()
        captured = job_logger._captured  # type: ignore[attr-defined]

        with patch("ami.ml.orchestration.nats_queue.get_connection", AsyncMock(return_value=(nc, js))):
            async with TaskQueueManager(job_logger=job_logger) as manager:
                await manager.log_consumer_stats_snapshot(9)

        messages = [m for _, m in captured]
        self.assertTrue(
            any("NATS consumer status job-9-consumer" in m for m in messages),
            f"expected snapshot line on job_logger, got {messages}",
        )
        snapshot_line = next(m for m in messages if "NATS consumer status" in m)
        for expected in ("delivered=50", "ack_floor=40", "num_redelivered=2"):
            self.assertIn(expected, snapshot_line)
        # Must NOT have triggered a delete — this is read-only observability.
        js.delete_consumer.assert_not_called()
        js.delete_stream.assert_not_called()

    async def test_log_consumer_stats_snapshot_tolerates_missing_consumer(self):
        """If the consumer is already gone, the snapshot helper just no-ops."""
        nc, js = self._create_mock_nats_connection()
        js.consumer_info.side_effect = nats.js.errors.NotFoundError()

        job_logger = self._make_captured_logger()

        with patch("ami.ml.orchestration.nats_queue.get_connection", AsyncMock(return_value=(nc, js))):
            async with TaskQueueManager(job_logger=job_logger) as manager:
                await manager.log_consumer_stats_snapshot(99)  # must not raise

    async def test_no_job_logger_falls_back_to_module_logger_only(self):
        """When job_logger is None (e.g., module-level uses like advisory
        listener), lifecycle logs must still be emitted to the module logger
        without crashing on a None attribute access."""
        nc, js = self._create_mock_nats_connection()
        js.stream_info.side_effect = nats.js.errors.NotFoundError()
        js.consumer_info.side_effect = nats.js.errors.NotFoundError()
        js.add_consumer = AsyncMock(return_value=self._make_consumer_info(delivered=0, ack_floor=0))

        with patch("ami.ml.orchestration.nats_queue.get_connection", AsyncMock(return_value=(nc, js))):
            async with TaskQueueManager() as manager:  # no job_logger passed
                # Must not raise.
                await manager.publish_task(1, self._create_sample_task())

    async def test_list_job_stream_snapshots_raises_on_nats_error_payload(self):
        """list_job_stream_snapshots must raise nats.errors.Error when the NATS
        server returns an error payload instead of a stream list.

        Returning [] in this case would mask an outage — the caller would
        silently interpret "zero zombies" while NATS is actually unavailable.
        """
        nc, js = self._create_mock_nats_connection()

        error_payload = json.dumps(
            {"error": {"code": 503, "description": "no responders available for request"}}
        ).encode()
        mock_response = MagicMock()
        mock_response.data = error_payload
        nc.request = AsyncMock(return_value=mock_response)

        with patch("ami.ml.orchestration.nats_queue.get_connection", AsyncMock(return_value=(nc, js))):
            async with TaskQueueManager() as manager:
                with self.assertRaises(nats.errors.Error):
                    await manager.list_job_stream_snapshots()

    async def test_list_job_stream_snapshots_returns_none_for_num_redelivered(self):
        """list_job_stream_snapshots returns num_redelivered=None for all snapshots.

        Per-consumer info is deferred to populate_redelivered_counts() so that
        the O(N) fetch only runs for drain candidates, not every stream.
        """
        nc, js = self._create_mock_nats_connection()

        stream_payload = json.dumps(
            {
                "total": 1,
                "streams": [
                    {
                        "config": {"name": "job_42"},
                        "created": "2024-01-01T00:00:00Z",
                        "state": {"messages": 0},
                    }
                ],
            }
        ).encode()
        mock_response = MagicMock()
        mock_response.data = stream_payload
        nc.request = AsyncMock(return_value=mock_response)

        with patch("ami.ml.orchestration.nats_queue.get_connection", AsyncMock(return_value=(nc, js))):
            async with TaskQueueManager() as manager:
                snapshots = await manager.list_job_stream_snapshots()

        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0]["job_id"], 42)
        self.assertIsNone(snapshots[0]["num_redelivered"])
        # consumer_info must NOT have been called — no redelivered fetch during list
        js.consumer_info.assert_not_called()
