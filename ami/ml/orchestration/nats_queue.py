"""
NATS JetStream utility for task queue management in the antenna project.

This module provides a TaskQueueManager that uses NATS JetStream for distributed
task queuing with acknowledgment support via reply subjects. This allows workers
to pull tasks over HTTP and acknowledge them later without maintaining a persistent
connection to NATS.

Other queue systems were considered, such as RabbitMQ and Beanstalkd. However, they don't
support the visibility timeout semantics we want or a disconnected mode of pulling and ACKing tasks.
"""

import asyncio
import datetime
import json
import logging
import re

import nats
from asgiref.sync import sync_to_async
from django.conf import settings
from nats.js import JetStreamContext
from nats.js.api import AckPolicy, ConsumerConfig, DeliverPolicy

from ami.ml.schemas import PipelineProcessingTask

logger = logging.getLogger(__name__)

# Timeout for individual JetStream metadata operations (create/check stream and consumer).
# These are lightweight NATS server operations that complete in milliseconds under normal
# conditions. stream_info() and add_stream() don't accept a native timeout parameter, so
# we use asyncio.wait_for() uniformly for all operations. Without these timeouts, a hung
# NATS connection blocks the caller's thread indefinitely — and when that caller is a
# Django worker (via async_to_sync), it makes the entire server unresponsive.
NATS_JETSTREAM_TIMEOUT = 10  # seconds


async def get_connection(nats_url: str) -> tuple[nats.NATS, JetStreamContext]:
    nc = await nats.connect(
        nats_url,
        connect_timeout=5,
        allow_reconnect=False,
    )
    js = nc.jetstream()
    return nc, js


TASK_TTR = getattr(settings, "NATS_TASK_TTR", 30)  # Visibility timeout in seconds (configurable)

# Max delivery attempts per NATS message (1 original + N-1 retries).
# A processing service that consistently fails (e.g. returns results referencing
# an algorithm that the pipeline doesn't declare) will burn ADC + worker time on
# every retry; one retry covers a transient blip and is the right tradeoff.
# Override per environment via settings.NATS_MAX_DELIVER if that balance needs
# to change (e.g. a deployment with a flakier network may want a higher value).
NATS_MAX_DELIVER = getattr(settings, "NATS_MAX_DELIVER", 2)

ADVISORY_STREAM_NAME = "advisories"  # Shared stream for max delivery advisories across all jobs


def _parse_nats_timestamp(raw: str) -> datetime.datetime:
    """Parse an RFC3339-ish NATS timestamp, tolerating sub-microsecond precision.

    NATS servers emit nanoseconds (``...20494325Z``); Python's ``fromisoformat``
    rejects anything beyond 6 fractional digits, so we truncate before parsing.
    Returns a naive datetime in local time to match the rest of the codebase
    (``settings.USE_TZ = False``).
    """
    cleaned = raw.rstrip("Z")
    if "." in cleaned:
        head, frac = cleaned.split(".", 1)
        cleaned = f"{head}.{frac[:6]}"
    parsed = datetime.datetime.fromisoformat(cleaned)
    # NATS emits UTC; attach UTC tzinfo if none is present, then convert to the
    # local zone and drop tzinfo to match the naive-local datetimes used
    # throughout the codebase (``settings.USE_TZ = False``).
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone().replace(tzinfo=None)


class TaskQueueManager:
    """
    Manager for NATS JetStream task queue operations.

    Args:
        nats_url: NATS server URL. Falls back to settings.NATS_URL, then "nats://nats:4222".
        max_ack_pending: Max unacknowledged messages per consumer. Falls back to
            settings.NATS_MAX_ACK_PENDING, then 1000.
        job_logger: Optional per-job logger. When set, lifecycle events (stream /
            consumer create or reuse, cleanup stats, publish failures) are mirrored
            to this logger in addition to the module logger, so they appear in the
            job's own log stream as seen from the UI. Per-message and per-poll
            events stay on the module logger only to avoid drowning large jobs.

    Use as an async context manager:
        async with TaskQueueManager(job_logger=job.logger) as manager:
            await manager.publish_task(123, {'data': 'value'})
            tasks = await manager.reserve_tasks(123, count=64)
            await manager.acknowledge_task(tasks[0].reply_subject)
    """

    def __init__(
        self,
        nats_url: str | None = None,
        max_ack_pending: int | None = None,
        job_logger: logging.Logger | None = None,
    ):
        self.nats_url = nats_url or getattr(settings, "NATS_URL", "nats://nats:4222")
        self.max_ack_pending = (
            max_ack_pending if max_ack_pending is not None else getattr(settings, "NATS_MAX_ACK_PENDING", 1000)
        )
        self.job_logger = job_logger
        self.nc: nats.NATS | None = None
        self.js: JetStreamContext | None = None
        # Dedupe lifecycle log lines per manager session so a job that publishes
        # hundreds of tasks doesn't emit hundreds of "reusing stream" messages.
        self._streams_logged: set[int] = set()
        self._consumers_logged: set[int] = set()

    async def log_async(self, level: int, msg: str, *, exc_info: bool = False) -> None:
        """Log to both the module logger and the job logger (if set).

        Named ``log_async`` (not ``log``) to flag at every call site that this
        is the async fan-out helper, distinct from stdlib ``Logger.log`` —
        callers must ``await`` it. Use this from any async context where the
        line should appear in both ops dashboards and the job's UI log.

        Module logger fires synchronously (ops dashboards / stdout / New Relic
        are unaffected). The job logger call is bridged through
        ``sync_to_async`` because Django's ``JobLogHandler`` does an ORM
        ``refresh_from_db`` + ``save`` on every emit — calling that directly
        from the event loop raises ``SynchronousOnlyOperation`` and the log
        line is silently dropped. The bridge offloads the handler work to a
        thread so the line actually lands in ``job.logs.stdout``.

        Pass ``exc_info=True`` inside an ``except`` block to capture the
        traceback on both loggers (same semantics as stdlib ``Logger.log``).

        Exceptions from the job logger are swallowed so logging a lifecycle
        event never breaks the actual NATS operation.

        Gated by ``isEnabledFor`` up front so a disabled level returns
        immediately without paying for the ``sync_to_async`` round-trip.
        Matters most at DEBUG during large queues — stdlib ``Logger.log``
        does the same level check internally before formatting a message;
        we have to do it explicitly here because the job-logger mirror
        happens through ``sync_to_async`` (ThreadPoolExecutor submit), which
        would otherwise fire once per image even when the handler is about
        to drop the record.

        FUTURE: this currently mirrors granular per-job lifecycle (stream /
        consumer create+reuse, per-image debug, forensic stats) to BOTH the
        module logger and the job logger. The longer-term preference is to
        route — granular lifecycle stays on ``job.logger`` only (matching
        ``ami.jobs.tasks.save_results`` and friends, where ``job.logger`` has
        ``propagate=False`` and never reaches stdout / NR), with the module
        logger reserved for true ops signals (connection failures, NATS-side
        errors). Kept symmetric for now because async ML processing is still
        being stabilized and the extra stdout visibility is helping us
        debug. Once we trust the per-job UI log as the canonical place to
        inspect a job, switch ``log_async`` to route-not-mirror at INFO/DEBUG
        and only auto-mirror at WARNING+ (so true error signals still always
        reach ops dashboards).
        """
        module_enabled = logger.isEnabledFor(level)
        job_enabled = (
            self.job_logger is not None and self.job_logger is not logger and self.job_logger.isEnabledFor(level)
        )
        if not module_enabled and not job_enabled:
            return
        if module_enabled:
            logger.log(level, msg, exc_info=exc_info)
        if job_enabled:
            try:
                await sync_to_async(self.job_logger.log)(level, msg, exc_info=exc_info)
            except Exception as e:
                logger.warning(f"Failed to mirror log to job logger: {e}")

    @staticmethod
    def _format_consumer_config(info) -> str:
        """Format ConsumerInfo config into a compact creation-time string.

        Reads the actual config from the ConsumerInfo returned by
        ``add_consumer`` or ``consumer_info``, so the log always reflects
        what the server accepted rather than what we requested.
        """
        cfg = info.config
        if cfg is None:
            return "config=?"

        def _val(v):
            """Unwrap enum .value if present, pass through scalars."""
            return v.value if hasattr(v, "value") else v

        return (
            f"max_deliver={_val(cfg.max_deliver) if cfg.max_deliver is not None else '?'}, "
            f"ack_wait={_val(cfg.ack_wait) if cfg.ack_wait is not None else '?'}s, "
            f"max_ack_pending={_val(cfg.max_ack_pending) if cfg.max_ack_pending is not None else '?'}, "
            f"deliver_policy={_val(cfg.deliver_policy) if cfg.deliver_policy is not None else '?'}, "
            f"ack_policy={_val(cfg.ack_policy) if cfg.ack_policy is not None else '?'}"
        )

    @staticmethod
    def _format_consumer_stats(info) -> str:
        """Format ConsumerInfo into a compact runtime stats string.

        All nats-py ConsumerInfo fields are Optional, so defensive access is
        required: this method renders missing values as '?'. Used for both
        reuse-announcements and forensic cleanup lines.
        """
        delivered = info.delivered.consumer_seq if info.delivered is not None else "?"
        ack_floor = info.ack_floor.consumer_seq if info.ack_floor is not None else "?"
        return (
            f"delivered={delivered} "
            f"ack_floor={ack_floor} "
            f"num_pending={info.num_pending if info.num_pending is not None else '?'} "
            f"num_ack_pending={info.num_ack_pending if info.num_ack_pending is not None else '?'} "
            f"num_redelivered={info.num_redelivered if info.num_redelivered is not None else '?'}"
        )

    async def __aenter__(self):
        """Create connection on enter."""
        self.nc, self.js = await get_connection(self.nats_url)

        try:
            await self._setup_advisory_stream()
        except BaseException:
            if self.nc and not self.nc.is_closed:
                await self.nc.close()
            self.nc = None
            self.js = None
            raise
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.js:
            self.js = None
        if self.nc and not self.nc.is_closed:
            await self.nc.close()
            self.nc = None

        return False

    def _get_stream_name(self, job_id: int) -> str:
        """Get stream name from job_id."""
        return f"job_{job_id}"

    def _get_subject(self, job_id: int) -> str:
        """Get subject name from job_id."""
        return f"job.{job_id}.tasks"

    def _get_consumer_name(self, job_id: int) -> str:
        """Get consumer name from job_id."""
        return f"job-{job_id}-consumer"

    async def _job_stream_exists(self, job_id: int) -> bool:
        """Check if stream exists for the given job.

        Only catches NotFoundError (→ False). TimeoutError propagates deliberately
        so callers treat an unreachable NATS server as a hard failure rather than
        a missing stream.
        """
        if self.js is None:
            raise RuntimeError("Connection is not open. Use TaskQueueManager as an async context manager.")

        stream_name = self._get_stream_name(job_id)
        return await self._stream_exists(stream_name)

    async def _stream_exists(self, stream_name: str) -> bool:
        """Check if a stream with the given name exists."""
        try:
            await asyncio.wait_for(self.js.stream_info(stream_name), timeout=NATS_JETSTREAM_TIMEOUT)
            return True
        except nats.js.errors.NotFoundError:
            return False

    async def _ensure_stream(self, job_id: int):
        """Ensure stream exists for the given job.

        Logs a lifecycle line to both the module and job logger the first time it
        sees a given job in this manager session (creation or reuse). Subsequent
        calls in the same session skip the NATS round-trip entirely via the
        ``_streams_logged`` set.

        Concurrency note: ``Job.cancel()`` can trigger ``cleanup_async_job_resources``
        in the request thread while this manager is still in its publish loop in
        the Celery worker, so the stream *can* be deleted mid-flight from a
        different manager session. The early-return is still safe in that case —
        subsequent ``publish_task`` calls will fail loudly (``self.js.publish``
        returns an error, caught and logged by ``publish_task``) rather than
        silently recreating the stream without a consumer. Failing loud on a
        cancel race is the correct behavior.
        """
        if job_id in self._streams_logged:
            return
        if self.js is None:
            raise RuntimeError("Connection is not open. Use TaskQueueManager as an async context manager.")

        stream_name = self._get_stream_name(job_id)
        subject = self._get_subject(job_id)

        try:
            info = await asyncio.wait_for(self.js.stream_info(stream_name), timeout=NATS_JETSTREAM_TIMEOUT)
            state = info.state
            messages = state.messages if state is not None else "?"
            last_seq = state.last_seq if state is not None else "?"
            await self.log_async(
                logging.INFO,
                f"Reusing NATS stream {stream_name} (messages={messages}, last_seq={last_seq})",
            )
            self._streams_logged.add(job_id)
            return
        except nats.js.errors.NotFoundError:
            pass

        await asyncio.wait_for(
            self.js.add_stream(
                name=stream_name,
                subjects=[subject],
                max_age=86400,  # 24 hours retention
            ),
            timeout=NATS_JETSTREAM_TIMEOUT,
        )
        await self.log_async(logging.INFO, f"Created NATS stream {stream_name}")
        self._streams_logged.add(job_id)

    async def _ensure_consumer(self, job_id: int):
        """Ensure consumer exists for the given job.

        On first sight in this manager session (creation or reuse), emits a line
        to both the module and job logger. On creation the line includes the
        config snapshot (max_deliver, ack_wait, max_ack_pending, deliver_policy,
        ack_policy) so forensic readers can see exactly what delivery semantics
        were in effect. Subsequent calls skip the NATS round-trip via the
        ``_consumers_logged`` set.

        Same concurrency caveat as ``_ensure_stream``: a concurrent cancel can
        delete the consumer mid-flight. The early-return stays safe because
        downstream ``publish_task`` fails loudly rather than silently recreating
        an orphan consumer.
        """
        if job_id in self._consumers_logged:
            return
        if self.js is None:
            raise RuntimeError("Connection is not open. Use TaskQueueManager as an async context manager.")

        stream_name = self._get_stream_name(job_id)
        consumer_name = self._get_consumer_name(job_id)
        subject = self._get_subject(job_id)

        try:
            info = await asyncio.wait_for(
                self.js.consumer_info(stream_name, consumer_name),
                timeout=NATS_JETSTREAM_TIMEOUT,
            )
            await self.log_async(
                logging.INFO,
                f"Reusing NATS consumer {consumer_name} ({self._format_consumer_stats(info)})",
            )
            self._consumers_logged.add(job_id)
            return
        except nats.js.errors.NotFoundError:
            # Consumer doesn't exist, fall through to create it. Other
            # JetStream errors (auth, API, transient) and asyncio.TimeoutError
            # propagate naturally — we don't want to mask them as "missing
            # consumer" and emit misleading creation logs.
            pass

        info = await asyncio.wait_for(
            self.js.add_consumer(
                stream=stream_name,
                config=ConsumerConfig(
                    durable_name=consumer_name,
                    ack_policy=AckPolicy.EXPLICIT,
                    ack_wait=TASK_TTR,  # Visibility timeout (TTR)
                    max_deliver=NATS_MAX_DELIVER,
                    deliver_policy=DeliverPolicy.ALL,
                    max_ack_pending=self.max_ack_pending,
                    filter_subject=subject,
                ),
            ),
            timeout=NATS_JETSTREAM_TIMEOUT,
        )
        await self.log_async(
            logging.INFO,
            f"Created NATS consumer {consumer_name} ({self._format_consumer_config(info)})",
        )
        self._consumers_logged.add(job_id)

    async def publish_task(self, job_id: int, data: PipelineProcessingTask) -> bool:
        """
        Publish a task to it's job queue.

        Args:
            job_id: The job ID (integer primary key)
            data: PipelineProcessingTask object to be published

        Returns:
            bool: True if successful, False otherwise
        """
        if self.js is None:
            raise RuntimeError("Connection is not open. Use TaskQueueManager as an async context manager.")

        try:
            # Ensure stream and consumer exist
            await self._ensure_stream(job_id)
            await self._ensure_consumer(job_id)

            subject = self._get_subject(job_id)
            # Convert Pydantic model to JSON
            task_data = json.dumps(data.dict())

            # Publish to JetStream
            ack = await self.js.publish(subject, task_data.encode(), timeout=NATS_JETSTREAM_TIMEOUT)

            logger.info(f"Published task to stream for job '{job_id}', sequence {ack.seq}")
            return True

        except Exception as e:
            # Per-message success logs stay at module level (noise in 10k-image
            # jobs), but a failure on even a single publish deserves to surface
            # in the job log — otherwise the failure path is invisible to users.
            await self.log_async(logging.ERROR, f"Failed to publish task to stream for job '{job_id}': {e}")
            return False

    async def reserve_tasks(self, job_id: int, count: int, timeout: float = 5) -> list[PipelineProcessingTask]:
        """
        Reserve up to `count` tasks from the specified stream in a single NATS fetch.

        Args:
            job_id: The job ID (integer primary key) to pull tasks from
            count: Maximum number of tasks to reserve
            timeout: Timeout in seconds waiting for messages (default: 5 seconds)

        Returns:
            List of PipelineProcessingTask objects with reply_subject set for acknowledgment.
            May return fewer than `count` if the queue has fewer messages available.
        """
        if self.js is None:
            raise RuntimeError("Connection is not open. Use TaskQueueManager as an async context manager.")

        try:
            if not await self._job_stream_exists(job_id):
                logger.debug(f"Stream for job '{job_id}' does not exist when reserving task")
                return []

            await self._ensure_consumer(job_id)

            consumer_name = self._get_consumer_name(job_id)
            subject = self._get_subject(job_id)

            psub = await self.js.pull_subscribe(subject, consumer_name)

            try:
                msgs = await psub.fetch(count, timeout=timeout)
            except (asyncio.TimeoutError, nats.errors.TimeoutError):
                logger.debug(f"No tasks available in stream for job '{job_id}'")
                return []
            finally:
                await psub.unsubscribe()

            tasks = []
            for msg in msgs:
                task_data = json.loads(msg.data.decode())
                task = PipelineProcessingTask(**task_data)
                task.reply_subject = msg.reply
                tasks.append(task)

            if tasks:
                logger.info(f"Reserved {len(tasks)} tasks from stream for job '{job_id}'")
            else:
                logger.debug(f"No tasks reserved from stream for job '{job_id}'")
            return tasks

        except (asyncio.TimeoutError, nats.errors.TimeoutError):
            raise  # NATS unreachable — propagate so the view can return an appropriate error
        except Exception as e:
            logger.error(f"Failed to reserve tasks from stream for job '{job_id}': {e}")
            return []

    async def acknowledge_task(self, reply_subject: str) -> bool:
        """
        Acknowledge (delete) a completed task using its reply subject.

        Args:
            reply_subject: The reply subject from reserve_task

        Returns:
            bool: True if successful
        """
        if self.nc is None:
            raise RuntimeError("Connection is not open. Use TaskQueueManager as an async context manager.")

        try:
            await self.nc.publish(reply_subject, b"+ACK")
            await self.nc.flush()
            logger.debug(f"Acknowledged task with reply subject {reply_subject}")
            return True
        except Exception as e:
            logger.error(f"Failed to acknowledge task: {e}")
            return False

    async def _log_final_consumer_stats(self, job_id: int) -> None:
        """Log one forensic line about the consumer state before deletion.

        This is the single most useful line in a post-mortem: it tells you how
        many messages were delivered, how many were acked, and how many were
        redelivered before the consumer vanished. Failures here must NOT block
        cleanup — if the consumer or stream is already gone, just skip it.
        """
        await self._log_consumer_stats(job_id, prefix="Finalizing NATS consumer", suffix="before deletion")

    async def log_consumer_stats_snapshot(self, job_id: int) -> None:
        """Log a mid-flight snapshot of the consumer state for a running job.

        Called by the ``running_job_snapshots`` sub-check of the periodic
        ``jobs_health_check`` beat task so operators can see deliver/ack/pending
        counts without waiting for the job to finish. Tolerant of missing
        stream/consumer like the cleanup-time variant.
        """
        await self._log_consumer_stats(job_id, prefix="NATS consumer status")

    async def _log_consumer_stats(self, job_id: int, *, prefix: str, suffix: str = "") -> None:
        if self.js is None:
            return
        stream_name = self._get_stream_name(job_id)
        consumer_name = self._get_consumer_name(job_id)
        try:
            info = await asyncio.wait_for(
                self.js.consumer_info(stream_name, consumer_name),
                timeout=NATS_JETSTREAM_TIMEOUT,
            )
        except Exception as e:
            # Broad catch is intentional: if the consumer or stream is gone we
            # just skip — callers (cleanup, periodic snapshot) should never fail
            # because we couldn't read stats.
            logger.debug(f"Could not fetch consumer info for {consumer_name}: {e}")
            return
        tail = f" {suffix}" if suffix else ""
        await self.log_async(
            logging.INFO,
            f"{prefix} {consumer_name}{tail} ({self._format_consumer_stats(info)})",
        )

    async def delete_consumer(self, job_id: int) -> bool:
        """
        Delete the consumer for a job.

        Args:
            job_id: The job ID (integer primary key)

        Returns:
            bool: True if successful, False otherwise
        """
        if self.js is None:
            raise RuntimeError("Connection is not open. Use TaskQueueManager as an async context manager.")

        try:
            stream_name = self._get_stream_name(job_id)
            consumer_name = self._get_consumer_name(job_id)

            await asyncio.wait_for(
                self.js.delete_consumer(stream_name, consumer_name),
                timeout=NATS_JETSTREAM_TIMEOUT,
            )
            await self.log_async(logging.INFO, f"Deleted NATS consumer {consumer_name} for job '{job_id}'")
            return True
        except Exception as e:
            await self.log_async(logging.ERROR, f"Failed to delete NATS consumer for job '{job_id}': {e}")
            return False

    async def delete_stream(self, job_id: int) -> bool:
        """
        Delete the stream for a job.

        Args:
            job_id: The job ID (integer primary key)

        Returns:
            bool: True if successful, False otherwise
        """
        if self.js is None:
            raise RuntimeError("Connection is not open. Use TaskQueueManager as an async context manager.")

        try:
            stream_name = self._get_stream_name(job_id)

            await asyncio.wait_for(
                self.js.delete_stream(stream_name),
                timeout=NATS_JETSTREAM_TIMEOUT,
            )
            await self.log_async(logging.INFO, f"Deleted NATS stream {stream_name} for job '{job_id}'")
            return True
        except Exception as e:
            await self.log_async(logging.ERROR, f"Failed to delete NATS stream for job '{job_id}': {e}")
            return False

    async def list_job_stream_snapshots(self) -> list[dict]:
        """Return a snapshot of every ``job_{N}`` stream currently in JetStream.

        Each entry: ``{"job_id": int, "stream_name": str, "created": datetime,
        "messages": int, "num_redelivered": int | None}``. ``num_redelivered``
        is pulled from the matching consumer when present and is ``None`` when
        the consumer has already been removed (stream-only zombies are still
        worth reporting).

        Uses the raw ``$JS.API.STREAM.LIST`` endpoint because
        ``JetStreamContext.streams_info`` in the currently pinned nats.py drops
        the server-side ``created`` timestamp from :class:`StreamInfo` — we need
        it here to age zombies out with a safety margin.
        """
        if self.nc is None or self.js is None:
            raise RuntimeError("Connection is not open. Use TaskQueueManager as an async context manager.")

        snapshots: list[dict] = []
        offset = 0
        # $JS.API.STREAM.LIST pages at 256 streams per response; loop so a
        # deployment with a long tail of zombies is still fully enumerated.
        while True:
            resp = await asyncio.wait_for(
                self.nc.request("$JS.API.STREAM.LIST", json.dumps({"offset": offset}).encode()),
                timeout=NATS_JETSTREAM_TIMEOUT,
            )
            payload = json.loads(resp.data)
            streams = payload.get("streams") or []
            if not streams:
                break
            for stream in streams:
                config = stream.get("config") or {}
                name = config.get("name") or ""
                match = re.match(r"^job_(\d+)$", name)
                if not match:
                    continue
                job_id = int(match.group(1))
                created_raw = stream.get("created")
                try:
                    created = _parse_nats_timestamp(created_raw) if created_raw else None
                except ValueError:
                    created = None
                state = stream.get("state") or {}
                snapshots.append(
                    {
                        "job_id": job_id,
                        "stream_name": name,
                        "created": created,
                        "messages": int(state.get("messages") or 0),
                        "num_redelivered": await self._consumer_redelivered_count(job_id),
                    }
                )
            total = int(payload.get("total") or 0)
            offset += len(streams)
            if offset >= total:
                break
        return snapshots

    async def _consumer_redelivered_count(self, job_id: int) -> int | None:
        """Return ``num_redelivered`` from the job's consumer, or ``None`` if gone."""
        if self.js is None:
            return None
        stream_name = self._get_stream_name(job_id)
        consumer_name = self._get_consumer_name(job_id)
        try:
            info = await asyncio.wait_for(
                self.js.consumer_info(stream_name, consumer_name),
                timeout=NATS_JETSTREAM_TIMEOUT,
            )
        except Exception:
            return None
        return getattr(info, "num_redelivered", None)

    async def _setup_advisory_stream(self):
        """Ensure the shared advisory stream exists to capture max-delivery events.

        Called on every __aenter__ so that advisories are captured from the moment
        any TaskQueueManager connection is opened, not just when the DLQ is first read.
        """
        if not await self._stream_exists(ADVISORY_STREAM_NAME):
            await asyncio.wait_for(
                self.js.add_stream(
                    name=ADVISORY_STREAM_NAME,
                    subjects=["$JS.EVENT.ADVISORY.>"],
                    max_age=3600,  # Keep advisories for 1 hour
                ),
                timeout=NATS_JETSTREAM_TIMEOUT,
            )
            logger.info("Advisory stream created")

    def _get_dlq_consumer_name(self, job_id: int) -> str:
        """Get the durable consumer name for dead letter queue advisory tracking."""
        return f"job-{job_id}-dlq"

    async def get_dead_letter_image_ids(self, job_id: int, n: int = 10) -> list[str]:
        """
        Get image IDs from dead letter queue (messages that exceeded max delivery attempts).

        Pulls from persistent advisory stream to find failed messages, then looks up image IDs.
        Uses a durable consumer so acknowledged advisories are not re-delivered on subsequent calls.

        Args:
            job_id: The job ID (integer primary key)
            n: Maximum number of image IDs to return (default: 10)

        Returns:
            List of image IDs that failed to process after max retry attempts
        """
        if self.nc is None or self.js is None:
            raise RuntimeError("Connection is not open. Use TaskQueueManager as an async context manager.")

        stream_name = self._get_stream_name(job_id)
        consumer_name = self._get_consumer_name(job_id)
        dlq_consumer_name = self._get_dlq_consumer_name(job_id)
        dead_letter_ids = []

        subject_filter = f"$JS.EVENT.ADVISORY.CONSUMER.MAX_DELIVERIES.{stream_name}.{consumer_name}"

        # Use a durable consumer so ACKs persist across calls — ephemeral consumers
        # are deleted on unsubscribe, discarding all ACK tracking and causing every
        # advisory to be re-delivered on the next call.
        psub = await self.js.pull_subscribe(subject_filter, durable=dlq_consumer_name, stream=ADVISORY_STREAM_NAME)

        try:
            msgs = await psub.fetch(n, timeout=1.0)

            for msg in msgs:
                advisory_data = json.loads(msg.data.decode())

                # Get the stream sequence of the failed message
                if "stream_seq" in advisory_data:
                    stream_seq = advisory_data["stream_seq"]

                    # Look up the actual message by sequence to get task ID
                    try:
                        job_msg = await self.js.get_msg(stream_name, stream_seq)

                        if job_msg and job_msg.data:
                            task_data = json.loads(job_msg.data.decode())

                            if "image_id" in task_data:
                                dead_letter_ids.append(str(task_data["image_id"]))
                            else:
                                logger.warning(f"No image_id found in task data: {task_data}")
                    except Exception as e:
                        logger.warning(f"Could not retrieve message {stream_seq} from {stream_name}: {e}")
                        # The message might have been discarded after max_deliver exceeded
                else:
                    logger.warning(f"No stream_seq in advisory data: {advisory_data}")

                # Acknowledge even if we couldn't find the stream_seq or image_id so it doesn't get re-delivered
                # it shouldn't happen since stream_seq is part of the `io.nats.jetstream.advisory.v1.max_deliver`
                # schema and all our messages have an image_id
                await msg.ack()
                logger.info(
                    f"Acknowledged advisory message for stream_seq {advisory_data.get('stream_seq', 'unknown')}"
                )

            # Flush to ensure all ACKs are written to the socket before unsubscribing.
            # msg.ack() only queues a publish in the client buffer; without flush() the
            # ACKs can be silently dropped when the subscription is torn down.
            await self.nc.flush()

        except (asyncio.TimeoutError, nats.errors.TimeoutError):
            logger.info(f"No advisory messages found for job {job_id}")
        finally:
            await psub.unsubscribe()

        return dead_letter_ids[:n]

    async def delete_dlq_consumer(self, job_id: int) -> bool:
        """
        Delete the durable DLQ advisory consumer for a job.

        Args:
            job_id: The job ID (integer primary key)

        Returns:
            bool: True if successful, False otherwise
        """
        if self.js is None:
            raise RuntimeError("Connection is not open. Use TaskQueueManager as an async context manager.")

        dlq_consumer_name = self._get_dlq_consumer_name(job_id)
        try:
            await asyncio.wait_for(
                self.js.delete_consumer(ADVISORY_STREAM_NAME, dlq_consumer_name),
                timeout=NATS_JETSTREAM_TIMEOUT,
            )
            logger.info(f"Deleted DLQ consumer {dlq_consumer_name} for job '{job_id}'")
            return True
        except nats.js.errors.NotFoundError:
            logger.debug(f"DLQ consumer {dlq_consumer_name} for job '{job_id}' not found when attempting to delete")
            return True  # Consider it a success if the consumer is already gone
        except Exception as e:
            logger.warning(f"Failed to delete DLQ consumer for job '{job_id}': {e}")
            return False

    async def cleanup_job_resources(self, job_id: int) -> bool:
        """
        Clean up all NATS resources (consumer, stream, and DLQ advisory consumer) for a job.

        This should be called when a job completes or is cancelled.

        Args:
            job_id: The job ID (integer primary key)

        Returns:
            bool: True if successful, False otherwise
        """
        # Log a forensic snapshot of the consumer state BEFORE we destroy it.
        # This is the highest-leverage line for post-mortem investigations.
        await self._log_final_consumer_stats(job_id)

        # Delete consumer first, then stream, then the durable DLQ advisory consumer
        consumer_deleted = await self.delete_consumer(job_id)
        stream_deleted = await self.delete_stream(job_id)
        dlq_consumer_deleted = await self.delete_dlq_consumer(job_id)

        return consumer_deleted and stream_deleted and dlq_consumer_deleted
