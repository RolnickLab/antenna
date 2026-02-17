"""
NATS JetStream utility for task queue management in the antenna project.

This module provides a TaskQueueManager that uses NATS JetStream for distributed
task queuing with acknowledgment support via reply subjects. This allows workers
to pull tasks over HTTP and acknowledge them later without maintaining a persistent
connection to NATS.

Other queue systems were considered, such as RabbitMQ and Beanstalkd. However, they don't
support the visibility timeout semantics we want or a disconnected mode of pulling and ACKing tasks.
"""

import json
import logging

import nats
from django.conf import settings
from nats.js import JetStreamContext
from nats.js.api import AckPolicy, ConsumerConfig, DeliverPolicy

from ami.ml.schemas import PipelineProcessingTask

logger = logging.getLogger(__name__)


async def get_connection(nats_url: str):
    nc = await nats.connect(
        nats_url,
        connect_timeout=5,
        allow_reconnect=False,
        max_reconnect_attempts=0,
    )
    js = nc.jetstream()
    return nc, js


TASK_TTR = 300  # Default Time-To-Run (visibility timeout) in seconds


class TaskQueueManager:
    """
    Manager for NATS JetStream task queue operations.

    Use as an async context manager:
        async with TaskQueueManager() as manager:
            await manager.publish_task('job123', {'data': 'value'})
            task = await manager.reserve_task('job123')
            await manager.acknowledge_task(task['reply_subject'])
    """

    def __init__(self, nats_url: str | None = None):
        self.nats_url = nats_url or getattr(settings, "NATS_URL", "nats://nats:4222")
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

    async def _ensure_stream(self, job_id: int):
        """Ensure stream exists for the given job."""
        if self.js is None:
            raise RuntimeError("Connection is not open. Use TaskQueueManager as an async context manager.")

        stream_name = self._get_stream_name(job_id)
        subject = self._get_subject(job_id)

        try:
            await self.js.stream_info(stream_name)
            logger.debug(f"Stream {stream_name} already exists")
        except Exception as e:
            logger.warning(f"Stream {stream_name} does not exist: {e}")
            # Stream doesn't exist, create it
            await self.js.add_stream(
                name=stream_name,
                subjects=[subject],
                max_age=86400,  # 24 hours retention
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
            info = await self.js.consumer_info(stream_name, consumer_name)
            logger.debug(f"Consumer {consumer_name} already exists: {info}")
        except Exception:
            # Consumer doesn't exist, create it
            await self.js.add_consumer(
                stream=stream_name,
                config=ConsumerConfig(
                    durable_name=consumer_name,
                    ack_policy=AckPolicy.EXPLICIT,
                    ack_wait=TASK_TTR,  # Visibility timeout (TTR)
                    max_deliver=5,  # Max retry attempts
                    deliver_policy=DeliverPolicy.ALL,
                    max_ack_pending=100,  # Max unacked messages
                    filter_subject=subject,
                ),
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
            ack = await self.js.publish(subject, task_data.encode())

            logger.info(f"Published task to stream for job '{job_id}', sequence {ack.seq}")
            return True

        except Exception as e:
            logger.error(f"Failed to publish task to stream for job '{job_id}': {e}")
            return False

    async def reserve_task(self, job_id: int, timeout: float | None = None) -> PipelineProcessingTask | None:
        """
        Reserve a task from the specified stream.

        Args:
            job_id: The job ID (integer primary key) to pull tasks from
            timeout: Timeout in seconds for reservation (default: 5 seconds)

        Returns:
            PipelineProcessingTask with reply_subject set for acknowledgment, or None if no task available
        """
        if self.js is None:
            raise RuntimeError("Connection is not open. Use TaskQueueManager as an async context manager.")

        if timeout is None:
            timeout = 5

        try:
            # Ensure stream and consumer exist
            await self._ensure_stream(job_id)
            await self._ensure_consumer(job_id)

            consumer_name = self._get_consumer_name(job_id)
            subject = self._get_subject(job_id)

            # Create ephemeral subscription for this pull
            psub = await self.js.pull_subscribe(subject, consumer_name)

            try:
                # Fetch a single message
                msgs = await psub.fetch(1, timeout=timeout)

                if msgs:
                    msg = msgs[0]
                    task_data = json.loads(msg.data.decode())
                    metadata = msg.metadata

                    # Parse the task data into PipelineProcessingTask
                    task = PipelineProcessingTask(**task_data)
                    # Set the reply_subject for acknowledgment
                    task.reply_subject = msg.reply

                    logger.debug(f"Reserved task from stream for job '{job_id}', sequence {metadata.sequence.stream}")
                    return task

            except nats.errors.TimeoutError:
                # No messages available
                logger.debug(f"No tasks available in stream for job '{job_id}'")
                return None
            finally:
                # Always unsubscribe
                await psub.unsubscribe()

        except Exception as e:
            logger.error(f"Failed to reserve task from stream for job '{job_id}': {e}")
            return None

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

            await self.js.delete_consumer(stream_name, consumer_name)
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

            await self.js.delete_stream(stream_name)
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
