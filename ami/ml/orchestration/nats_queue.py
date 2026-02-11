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
import functools
import json
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, TypeVar

from nats import errors as nats_errors
from nats.js import JetStreamContext
from nats.js.api import AckPolicy, ConsumerConfig, DeliverPolicy

from ami.ml.schemas import PipelineProcessingTask

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from nats.aio.client import Client as NATSClient

logger = logging.getLogger(__name__)


TASK_TTR = 300  # Default Time-To-Run (visibility timeout) in seconds

T = TypeVar("T")


def retry_on_connection_error(max_retries: int = 2, backoff_seconds: float = 0.5):
    """
    Decorator that retries NATS operations on connection errors. When a connection error is detected:
    1. Resets the event-loop-local connection pool (clears stale connection and lock)
    2. Waits with exponential backoff
    3. Retries the operation (which will get a fresh connection from the same event loop)

    This works correctly with async_to_sync() because the pool is keyed by event loop,
    ensuring each retry uses the connection bound to the current loop.

    Args:
        max_retries: Maximum number of retry attempts (default: 2)
        backoff_seconds: Initial backoff time in seconds (default: 0.5)
    Returns:
        Decorated async function with retry logic
    """

    def decorator(func: Callable[..., "Awaitable[T]"]) -> Callable[..., "Awaitable[T]"]:
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs) -> T:
            last_error = None
            assert max_retries >= 0, "max_retries must be non-negative"

            for attempt in range(max_retries + 1):
                try:
                    return await func(self, *args, **kwargs)
                except (
                    nats_errors.ConnectionClosedError,
                    nats_errors.NoServersError,
                    nats_errors.TimeoutError,
                    nats_errors.ConnectionReconnectingError,
                    OSError,  # Network errors
                ) as e:
                    last_error = e
                    # Don't retry on last attempt
                    if attempt == max_retries:
                        logger.error(
                            f"{func.__name__} failed after {max_retries + 1} attempts: {e}",
                            exc_info=True,
                        )
                        break
                    # Reset the connection pool so next attempt gets a fresh connection
                    from ami.ml.orchestration.nats_connection_pool import get_pool

                    pool = get_pool()
                    await pool.reset()
                    # Exponential backoff
                    wait_time = backoff_seconds * (2**attempt)
                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
            # If we exhausted retries, raise the last error, guaranteed to be not None here
            assert last_error is not None, "last_error should not be None if we exhausted retries"
            raise last_error  # type: ignore

        return wrapper

    return decorator


class TaskQueueManager:
    """
    Manager for NATS JetStream task queue operations.
    Always uses the event-loop-local connection pool for efficiency.

    Note: The connection pool is keyed by event loop, so each event loop gets its own
    connection. This prevents "attached to a different loop" errors when using async_to_sync()
    in Celery tasks or Django views. There's no overhead creating multiple TaskQueueManager
    instances as they all share the same event-loop-keyed pool.
    """

    async def _get_connection(self) -> tuple["NATSClient", JetStreamContext]:
        """Get connection from the event-loop-local pool."""
        from ami.ml.orchestration.nats_connection_pool import get_pool

        pool = get_pool()
        return await pool.get_connection()

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
        _, js = await self._get_connection()

        stream_name = self._get_stream_name(job_id)
        subject = self._get_subject(job_id)

        try:
            await js.stream_info(stream_name)
            logger.debug(f"Stream {stream_name} already exists")
        except Exception as e:
            logger.warning(f"Stream {stream_name} does not exist: {e}")
            # Stream doesn't exist, create it
            await js.add_stream(
                name=stream_name,
                subjects=[subject],
                max_age=86400,  # 24 hours retention
            )
            logger.info(f"Created stream {stream_name}")

    async def _ensure_consumer(self, job_id: int):
        """Ensure consumer exists for the given job."""
        _, js = await self._get_connection()

        stream_name = self._get_stream_name(job_id)
        consumer_name = self._get_consumer_name(job_id)
        subject = self._get_subject(job_id)

        try:
            info = await js.consumer_info(stream_name, consumer_name)
            logger.debug(f"Consumer {consumer_name} already exists: {info}")
        except Exception:
            # Consumer doesn't exist, create it
            await js.add_consumer(
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

    @retry_on_connection_error(max_retries=2, backoff_seconds=0.5)
    async def publish_task(self, job_id: int, data: PipelineProcessingTask) -> bool:
        """
        Publish a task to it's job queue.
        Automatically retries on connection errors with exponential backoff.
        Args:
            job_id: The job ID (integer primary key)
            data: PipelineProcessingTask object to be published
        Returns:
            bool: True if successful, False otherwise
        Raises:
            Connection errors are retried by decorator, other errors are raised
        """
        _, js = await self._get_connection()

        # Ensure stream and consumer exist
        await self._ensure_stream(job_id)
        await self._ensure_consumer(job_id)

        subject = self._get_subject(job_id)
        # Convert Pydantic model to JSON
        task_data = json.dumps(data.dict())

        # Publish to JetStream
        # Note: JetStream publish() waits for PubAck, so it's implicitly flushed
        ack = await js.publish(subject, task_data.encode())

        logger.info(f"Published task to stream for job '{job_id}', sequence {ack.seq}")
        return True

    @retry_on_connection_error(max_retries=2, backoff_seconds=0.5)
    async def reserve_task(self, job_id: int, timeout: float | None = None) -> PipelineProcessingTask | None:
        """
        Reserve a task from the specified stream.
        Automatically retries on connection errors with exponential backoff.
        Note: TimeoutError from fetch() (no messages) is NOT retried - only connection errors.
        Args:
            job_id: The job ID (integer primary key) to pull tasks from
            timeout: Timeout in seconds for reservation (default: 5 seconds)
        Returns:
            PipelineProcessingTask with reply_subject set for acknowledgment, or None if no task available
        """
        _, js = await self._get_connection()

        if timeout is None:
            timeout = 5

        # Ensure stream and consumer exist (let connection errors escape for retry)
        await self._ensure_stream(job_id)
        await self._ensure_consumer(job_id)

        consumer_name = self._get_consumer_name(job_id)
        subject = self._get_subject(job_id)

        # Create ephemeral subscription for this pull
        psub = await js.pull_subscribe(subject, consumer_name)

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

        except nats_errors.TimeoutError:
            # No messages available (expected behavior)
            logger.debug(f"No tasks available in stream for job '{job_id}'")
            return None
        finally:
            # Always unsubscribe
            await psub.unsubscribe()

    @retry_on_connection_error(max_retries=2, backoff_seconds=0.5)
    async def acknowledge_task(self, reply_subject: str) -> bool:
        """
        Acknowledge (delete) a completed task using its reply subject.
        Automatically retries on connection errors with exponential backoff.
        Args:
            reply_subject: The reply subject from reserve_task
        Returns:
            bool: True if successful
        Raises:
            Connection errors are retried by decorator, other errors are logged
        """
        nc, _ = await self._get_connection()

        # Don't catch connection errors - let retry decorator handle them
        await nc.publish(reply_subject, b"+ACK")

        # CRITICAL: Flush to ensure ACK is sent immediately
        # Without flush, ACKs may be buffered and not sent to NATS server
        try:
            await nc.flush(timeout=2)
        except asyncio.TimeoutError as e:
            # Flush timeout likely means connection is stale - re-raise to trigger retry
            logger.warning(f"Flush timeout for ACK {reply_subject}, connection may be stale: {e}")
            raise nats_errors.TimeoutError("Flush timeout") from e

        logger.debug(f"Acknowledged task with reply subject {reply_subject}")
        return True

    @retry_on_connection_error(max_retries=2, backoff_seconds=0.5)
    async def delete_consumer(self, job_id: int) -> bool:
        """
        Delete the consumer for a job.
        Automatically retries on connection errors with exponential backoff.
        Args:
            job_id: The job ID (integer primary key)
        Returns:
            bool: True if successful
        Raises:
            Connection errors are retried by decorator, other errors are raised
        """
        _, js = await self._get_connection()

        stream_name = self._get_stream_name(job_id)
        consumer_name = self._get_consumer_name(job_id)

        await js.delete_consumer(stream_name, consumer_name)
        logger.info(f"Deleted consumer {consumer_name} for job '{job_id}'")
        return True

    @retry_on_connection_error(max_retries=2, backoff_seconds=0.5)
    async def delete_stream(self, job_id: int) -> bool:
        """
        Delete the stream for a job.
        Automatically retries on connection errors with exponential backoff.
        Args:
            job_id: The job ID (integer primary key)
        Returns:
            bool: True if successful
        Raises:
            Connection errors are retried by decorator, other errors are raised
        """
        _, js = await self._get_connection()

        stream_name = self._get_stream_name(job_id)

        await js.delete_stream(stream_name)
        logger.info(f"Deleted stream {stream_name} for job'{job_id}'")
        return True

    async def cleanup_job_resources(self, job_id: int) -> bool:
        """
        Clean up all NATS resources (consumer and stream) for a job.
        This should be called when a job completes or is cancelled.
        Best-effort cleanup - logs errors but doesn't fail if cleanup fails.
        Args:
            job_id: The job ID (integer primary key)
        Returns:
            bool: True if both cleanup operations succeeded, False otherwise
        """
        consumer_deleted = False
        stream_deleted = False

        # Delete consumer first, then stream (best-effort)
        try:
            await self.delete_consumer(job_id)
            consumer_deleted = True
        except Exception as e:
            logger.warning(f"Failed to delete consumer for job {job_id} after retries: {e}")

        try:
            await self.delete_stream(job_id)
            stream_deleted = True
        except Exception as e:
            logger.warning(f"Failed to delete stream for job {job_id} after retries: {e}")

        return consumer_deleted and stream_deleted
