"""
Fault injection utility for manual chaos testing of ML async jobs.

Use alongside `test_ml_job_e2e` to verify job behaviour when Redis or NATS
becomes unavailable or loses state mid-processing.

Usage examples:

    # Flush all Redis state immediately (simulates FLUSHDB mid-job)
    python manage.py chaos_monkey flush redis

    # Flush all NATS JetStream streams (simulates broker state loss)
    python manage.py chaos_monkey flush nats
"""

from asgiref.sync import async_to_sync
from django.core.management.base import BaseCommand, CommandError
from django_redis import get_redis_connection

NATS_URL = "nats://ami_local_nats:4222"


class Command(BaseCommand):
    help = "Inject faults into Redis or NATS for chaos/resilience testing"

    def add_arguments(self, parser):
        parser.add_argument(
            "action",
            choices=["flush"],
            help="flush: wipe all state.",
        )
        parser.add_argument(
            "service",
            choices=["redis", "nats"],
            help="Target service to fault.",
        )

    def handle(self, *args, **options):
        action = options["action"]
        service = options["service"]

        if action == "flush" and service == "redis":
            self._flush_redis()
        elif action == "flush" and service == "nats":
            self._flush_nats()

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
