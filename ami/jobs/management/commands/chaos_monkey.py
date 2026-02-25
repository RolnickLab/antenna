"""
Fault injection utility for manual chaos testing of ML async jobs.

Use alongside `test_ml_job_e2e` to verify job behaviour when Redis or NATS
becomes unavailable or loses state mid-processing.

Usage examples:

    # Flush all Redis state immediately (simulates FLUSHDB mid-job)
    python manage.py chaos_monkey flush redis

    # Flush all NATS JetStream streams (simulates broker state loss)
    python manage.py chaos_monkey flush nats

    # Pause Redis for 15 seconds then restore (simulates transient outage)
    python manage.py chaos_monkey pause redis

    # Pause NATS for 30 seconds then restore
    python manage.py chaos_monkey pause nats --duration 30
"""

import subprocess
import time

from asgiref.sync import async_to_sync
from django.core.management.base import BaseCommand, CommandError
from django_redis import get_redis_connection

REDIS_CONTAINER = "ami_local_redis"
NATS_CONTAINER = "ami_local_nats"
NATS_URL = "nats://ami_local_nats:4222"


class Command(BaseCommand):
    help = "Inject faults into Redis or NATS for chaos/resilience testing"

    def add_arguments(self, parser):
        parser.add_argument(
            "action",
            choices=["flush", "pause"],
            help="flush: wipe all state. pause: stop the service temporarily then restore it.",
        )
        parser.add_argument(
            "service",
            choices=["redis", "nats"],
            help="Target service to fault.",
        )
        parser.add_argument(
            "--duration",
            type=int,
            default=15,
            metavar="SECONDS",
            help="How long to keep the service paused before restoring (pause only, default: 15).",
        )

    def handle(self, *args, **options):
        action = options["action"]
        service = options["service"]
        duration = options["duration"]

        if action == "flush" and service == "redis":
            self._flush_redis()
        elif action == "flush" and service == "nats":
            self._flush_nats()
        elif action == "pause" and service == "redis":
            self._pause_container(REDIS_CONTAINER, duration)
        elif action == "pause" and service == "nats":
            self._pause_container(NATS_CONTAINER, duration)

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

    # ------------------------------------------------------------------
    # Container pause/unpause (works for both redis and nats)
    # ------------------------------------------------------------------

    def _pause_container(self, container: str, duration: int):
        self.stdout.write(f"Pausing container '{container}' for {duration}s...")
        self._docker("pause", container)
        self.stdout.write(self.style.WARNING(f"Container paused. Waiting {duration}s..."))

        for remaining in range(duration, 0, -1):
            self.stdout.write(f"\r  {remaining}s remaining...", ending="")
            self.stdout.flush()
            time.sleep(1)

        self.stdout.write("")  # newline after countdown
        self._docker("unpause", container)
        self.stdout.write(self.style.SUCCESS(f"Container '{container}' restored."))

    def _docker(self, subcommand: str, container: str):
        result = subprocess.run(
            ["docker", subcommand, container],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise CommandError(f"`docker {subcommand} {container}` failed:\n{result.stderr.strip()}")
