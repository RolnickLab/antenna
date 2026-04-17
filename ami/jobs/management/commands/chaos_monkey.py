"""
Fault injection utility for manual chaos testing of ML async jobs.

Use alongside `test_ml_job_e2e` to verify job behaviour when Redis or NATS
becomes unavailable or loses state mid-processing.

Usage examples:

    # Flush all Redis state immediately (simulates FLUSHDB mid-job)
    python manage.py chaos_monkey flush redis

    # Flush all NATS JetStream streams (simulates broker state loss)
    python manage.py chaos_monkey flush nats

    # Exhaust NATS max_deliver for a job without ADC: publishes test payloads,
    # pulls them without ACK, waits ack_wait, repeats until max_deliver hits.
    # Leaves the consumer in (num_pending=0, num_ack_pending>0, num_redelivered>0)
    # — the shape `mark_lost_images_failed` is designed to reconcile.
    python manage.py chaos_monkey exhaust_max_deliver --job-id 999999 \\
        --image-ids img-a,img-b,img-c
"""

import asyncio
import logging

from asgiref.sync import async_to_sync
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django_redis import get_redis_connection

NATS_URL = getattr(settings, "NATS_URL", "nats://nats:4222")

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Inject faults into Redis or NATS for chaos/resilience testing"

    def add_arguments(self, parser):
        parser.add_argument(
            "action",
            choices=["flush", "exhaust_max_deliver"],
            help=(
                "flush: wipe all state (requires service). "
                "exhaust_max_deliver: drive a job's NATS consumer past max_deliver "
                "without ADC (requires --job-id)."
            ),
        )
        parser.add_argument(
            "service",
            nargs="?",
            choices=["redis", "nats"],
            default=None,
            help="Target service for 'flush'. Ignored for other actions.",
        )
        parser.add_argument(
            "--job-id",
            type=int,
            help="Job id for 'exhaust_max_deliver'. The stream/consumer must already "
            "exist (created by run_job); pass a dispatched job's id, or use "
            "--ensure-stream to let this command create the stream itself.",
        )
        parser.add_argument(
            "--image-ids",
            default="img-a,img-b,img-c",
            help="Comma-separated fake image ids to publish as payloads (default 3 ids).",
        )
        parser.add_argument(
            "--ensure-stream",
            action="store_true",
            help="Create the stream+consumer if missing. Useful for standalone "
            "reconciler tests against a fake job_id.",
        )

    def handle(self, *args, **options):
        action = options["action"]

        if action == "flush":
            service = options["service"]
            if service is None:
                raise CommandError("'flush' requires a service argument (redis|nats)")
            if service == "redis":
                self._flush_redis()
            elif service == "nats":
                self._flush_nats()
            return

        if action == "exhaust_max_deliver":
            job_id = options["job_id"]
            if job_id is None:
                raise CommandError("'exhaust_max_deliver' requires --job-id")
            image_ids = [s.strip() for s in options["image_ids"].split(",") if s.strip()]
            self._exhaust_max_deliver(job_id, image_ids, ensure_stream=options["ensure_stream"])
            return

    # ------------------------------------------------------------------
    # Redis
    # ------------------------------------------------------------------

    def _flush_redis(self):
        self.stdout.write("Flushing Redis database (FLUSHDB)...")
        try:
            redis = get_redis_connection("default")
            redis.flushdb()
            self.stdout.write(self.style.SUCCESS("Redis flushed."))
        except Exception as e:
            raise CommandError(f"Failed to flush Redis: {e}") from e

    # ------------------------------------------------------------------
    # NATS
    # ------------------------------------------------------------------

    def _flush_nats(self):
        """Delete all JetStream streams via the NATS Python client."""
        self.stdout.write("Flushing all NATS JetStream streams...")

        async def _delete_all_streams():
            import nats

            nc = await nats.connect(NATS_URL, connect_timeout=5, allow_reconnect=False)
            js = nc.jetstream()
            try:
                streams = await js.streams_info()
                if not streams:
                    return []
                deleted = []
                for stream in streams:
                    name = stream.config.name
                    await js.delete_stream(name)
                    deleted.append(name)
                return deleted
            finally:
                await nc.close()

        try:
            deleted = async_to_sync(_delete_all_streams)()
        except Exception as e:
            raise CommandError(f"Failed to flush NATS: {e}") from e

        if deleted:
            for name in deleted:
                self.stdout.write(f"  Deleted stream: {name}")
            self.stdout.write(self.style.SUCCESS(f"Deleted {len(deleted)} stream(s)."))
        else:
            self.stdout.write("No streams found — NATS already empty.")

    def _exhaust_max_deliver(self, job_id: int, image_ids: list[str], ensure_stream: bool = False):
        """Drive a job's consumer past NATS_MAX_DELIVER without running ADC.

        Publishes one payload per image id on the job's subject, then pulls
        without ACK and waits ack_wait (TASK_TTR) — repeating NATS_MAX_DELIVER
        times so each message hits its delivery budget. After this the consumer
        sits in (num_pending=0, num_ack_pending=len(image_ids), num_redelivered>0),
        which empirically is the post-exhaustion resting state — JetStream does
        not clear num_ack_pending for messages that hit max_deliver.

        This is the shape `mark_lost_images_failed` is designed to reconcile.
        The pending_images Redis sets for this job are NOT touched here; seed
        them separately via AsyncJobStateManager.initialize_job() if you want
        the reconciler to find work.
        """
        from ami.ml.orchestration.nats_queue import NATS_MAX_DELIVER, TASK_TTR, TaskQueueManager

        self.stdout.write(
            f"Exhausting max_deliver for job {job_id}: "
            f"publishing {len(image_ids)} message(s), "
            f"pulling {NATS_MAX_DELIVER}× without ACK, "
            f"waiting {TASK_TTR}s between pulls. "
            f"Expected total: ~{NATS_MAX_DELIVER * (TASK_TTR + 3)}s."
        )

        async def _run():
            async with TaskQueueManager() as m:
                if ensure_stream:
                    await m._ensure_stream(job_id)
                    await m._ensure_consumer(job_id)
                    self.stdout.write("  Ensured stream+consumer exist.")

                state = await m.get_consumer_state(job_id)
                if state is None:
                    raise CommandError(
                        f"No NATS consumer for job {job_id}. Dispatch the job first, "
                        "or pass --ensure-stream to create one."
                    )

                subject = m._get_subject(job_id)
                for iid in image_ids:
                    await m.js.publish(subject, f"chaos-payload-{iid}".encode())
                self.stdout.write(f"  Published {len(image_ids)} payload(s).")

                stream = m._get_stream_name(job_id)
                consumer = m._get_consumer_name(job_id)
                for attempt in range(1, NATS_MAX_DELIVER + 1):
                    self.stdout.write(f"  Attempt {attempt}/{NATS_MAX_DELIVER}: pulling (no ACK)...")
                    psub = await m.js.pull_subscribe_bind(consumer=consumer, stream=stream)
                    try:
                        msgs = await psub.fetch(batch=len(image_ids), timeout=5)
                        self.stdout.write(f"    Pulled {len(msgs)} message(s).")
                    except Exception as e:
                        self.stdout.write(f"    Pull returned no messages: {e}")
                    await psub.unsubscribe()

                    if attempt < NATS_MAX_DELIVER:
                        self.stdout.write(f"    Sleeping {TASK_TTR + 3}s (ack_wait + buffer)...")
                        await asyncio.sleep(TASK_TTR + 3)

                self.stdout.write(f"  Final wait {TASK_TTR + 3}s for max_deliver state to settle.")
                await asyncio.sleep(TASK_TTR + 3)

                state = await m.get_consumer_state(job_id)
                return state

        try:
            final_state = async_to_sync(_run)()
        except CommandError:
            raise
        except Exception as e:
            raise CommandError(f"exhaust_max_deliver failed: {e}") from e

        self.stdout.write(
            self.style.SUCCESS(
                f"Post-exhaustion ConsumerState: "
                f"num_pending={final_state.num_pending} "
                f"num_ack_pending={final_state.num_ack_pending} "
                f"num_redelivered={final_state.num_redelivered}"
            )
        )
