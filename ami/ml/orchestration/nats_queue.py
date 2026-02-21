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
import json
import logging

import nats
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


class TaskQueueManager:
    """
    Manager for NATS JetStream task queue operations.

    Args:
        nats_url: NATS server URL. Falls back to settings.NATS_URL, then "nats://nats:4222".
        max_ack_pending: Max unacknowledged messages per consumer. Falls back to
            settings.NATS_MAX_ACK_PENDING, then 100.

    Use as an async context manager:
        async with TaskQueueManager() as manager:
            await manager.publish_task(123, {'data': 'value'})
            tasks = await manager.reserve_tasks(123, count=64)
            await manager.acknowledge_task(tasks[0].reply_subject)
    """

    def __init__(self, nats_url: str | None = None, max_ack_pending: int | None = None):
        self.nats_url = nats_url or getattr(settings, "NATS_URL", "nats://nats:4222")
        self.max_ack_pending = (
            max_ack_pending if max_ack_pending is not None else getattr(settings, "NATS_MAX_ACK_PENDING", 100)
        )
        self.nc: nats.NATS | None = None
        self.js: JetStreamContext | None = None

    async def __aenter__(self):
        """Create connection on enter."""
        self.nc, self.js = await get_connection(self.nats_url)
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

    async def _stream_exists(self, job_id: int) -> bool:
        """Check if stream exists for the given job."""
        if self.js is None:
            raise RuntimeError("Connection is not open. Use TaskQueueManager as an async context manager.")

        stream_name = self._get_stream_name(job_id)
        try:
            await asyncio.wait_for(self.js.stream_info(stream_name), timeout=NATS_JETSTREAM_TIMEOUT)
            logger.debug(f"Stream {stream_name} already exists")
            return True
        except asyncio.TimeoutError:
            raise  # NATS unreachable — let caller handle it rather than creating a stream blindly
        except Exception:
            return False

    async def _ensure_stream(self, job_id: int):
        """Ensure stream exists for the given job."""
        if self.js is None:
            raise RuntimeError("Connection is not open. Use TaskQueueManager as an async context manager.")

        if not await self._stream_exists(job_id):
            stream_name = self._get_stream_name(job_id)
            subject = self._get_subject(job_id)

            logger.warning(f"Stream {stream_name} does not exist")
            # Stream doesn't exist, create it
            await asyncio.wait_for(
                self.js.add_stream(
                    name=stream_name,
                    subjects=[subject],
                    max_age=86400,  # 24 hours retention
                ),
                timeout=NATS_JETSTREAM_TIMEOUT,
            )
            logger.info(f"Created stream {stream_name}")

    async def _ensure_consumer(self, job_id: int):
        """Ensure consumer exists for the given job."""
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
            logger.debug(f"Consumer {consumer_name} already exists: {info}")
        except asyncio.TimeoutError:
            raise  # NATS unreachable — let caller handle it
        except Exception:
            # Consumer doesn't exist, create it
            await asyncio.wait_for(
                self.js.add_consumer(
                    stream=stream_name,
                    config=ConsumerConfig(
                        durable_name=consumer_name,
                        ack_policy=AckPolicy.EXPLICIT,
                        ack_wait=TASK_TTR,  # Visibility timeout (TTR)
                        max_deliver=5,  # Max retry attempts
                        deliver_policy=DeliverPolicy.ALL,
                        max_ack_pending=self.max_ack_pending,
                        filter_subject=subject,
                    ),
                ),
                timeout=NATS_JETSTREAM_TIMEOUT,
            )
            logger.info(f"Created consumer {consumer_name}")

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
            logger.error(f"Failed to publish task to stream for job '{job_id}': {e}")
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
            if not await self._stream_exists(job_id):
                logger.debug(f"Stream for job '{job_id}' does not exist when reserving task")
                return []

            await self._ensure_consumer(job_id)

            consumer_name = self._get_consumer_name(job_id)
            subject = self._get_subject(job_id)

            psub = await self.js.pull_subscribe(subject, consumer_name)

            try:
                msgs = await psub.fetch(count, timeout=timeout)
            except nats.errors.TimeoutError:
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

        except asyncio.TimeoutError:
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
            logger.debug(f"Acknowledged task with reply subject {reply_subject}")
            return True
        except Exception as e:
            logger.error(f"Failed to acknowledge task: {e}")
            return False

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
            logger.info(f"Deleted consumer {consumer_name} for job '{job_id}'")
            return True
        except Exception as e:
            logger.error(f"Failed to delete consumer for job '{job_id}': {e}")
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
            logger.info(f"Deleted stream {stream_name} for job '{job_id}'")
            return True
        except Exception as e:
            logger.error(f"Failed to delete stream for job '{job_id}': {e}")
            return False

    async def cleanup_job_resources(self, job_id: int) -> bool:
        """
        Clean up all NATS resources (consumer and stream) for a job.

        This should be called when a job completes or is cancelled.

        Args:
            job_id: The job ID (integer primary key)

        Returns:
            bool: True if successful, False otherwise
        """
        # Delete consumer first, then stream
        consumer_deleted = await self.delete_consumer(job_id)
        stream_deleted = await self.delete_stream(job_id)

        return consumer_deleted and stream_deleted
