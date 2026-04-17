"""
Entry point for MODE=worker and for the worker child in MODE=api+worker.

Expects register.py to have run first and written the resolved auth token to
/tmp/antenna_auth_header. If the file is absent (e.g. someone runs the worker
without registration), we fall back to the same env-var-based auth flow.
"""

from __future__ import annotations

import logging
import os
import platform
import socket
import sys
import time

import requests

LOG = logging.getLogger(__name__)


def _load_auth_header() -> str:
    cached = "/tmp/antenna_auth_header"
    if os.path.exists(cached):
        raw = open(cached).read().strip()
        if raw:
            return raw

    api_key = os.environ.get("ANTENNA_API_KEY")
    if api_key:
        return f"Api-Key {api_key}"

    token = os.environ.get("ANTENNA_API_AUTH_TOKEN")
    if token:
        return f"Token {token}"

    email = os.environ.get("ANTENNA_USER", "antenna@insectai.org")
    password = os.environ.get("ANTENNA_PASSWORD", "localadmin")
    api_url = os.environ["ANTENNA_API_URL"]
    for attempt in range(20):
        try:
            r = requests.post(
                f"{api_url}/api/v2/auth/token/login/",
                json={"email": email, "password": password},
                timeout=10,
            )
            r.raise_for_status()
            return f"Token {r.json()['auth_token']}"
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as e:
            LOG.info("Worker login retry %d/20: %s", attempt + 1, e)
            time.sleep(3)
    raise RuntimeError("Worker could not authenticate with Antenna")


def _client_info() -> dict:
    return {
        "hostname": socket.gethostname(),
        "software": "antenna-minimal-worker",
        "version": "0.1.0",
        "platform": platform.platform(),
    }


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    api_url = os.environ.get("ANTENNA_API_URL")
    if not api_url:
        LOG.error("ANTENNA_API_URL is required")
        return 2

    auth = _load_auth_header()

    # Late import so tests can run without the worker-side api deps on the path.
    from worker.client import AntennaClient
    from worker.loop import Loop

    client = AntennaClient(api_url, auth, timeout=float(os.environ.get("WORKER_REQUEST_TIMEOUT_SECONDS", "30")))
    loop = Loop(client, _client_info())
    loop.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
