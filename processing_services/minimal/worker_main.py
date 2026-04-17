"""
Entry point for MODE=worker and for the worker child in MODE=api+worker.

Expects register.py to have run first and written the resolved auth token to
/tmp/antenna_auth_header. If the file is absent (e.g. someone runs the worker
without registration), we fall back to the same env-var-based auth flow.
All env vars required for auth must be provided via the .env file — this
module does not hard-code dev defaults.
"""

from __future__ import annotations

import logging
import os
import platform
import socket
import sys
import time

import requests
from api.schemas import ProcessingServiceClientInfo  # type: ignore[import-not-found]

LOG = logging.getLogger(__name__)

CACHED_AUTH_HEADER_PATH = "/tmp/antenna_auth_header"
MAX_LOGIN_ATTEMPTS = 20
LOGIN_RETRY_DELAY = 3  # seconds


def _load_auth_header() -> str:
    if os.path.exists(CACHED_AUTH_HEADER_PATH):
        with open(CACHED_AUTH_HEADER_PATH) as f:
            raw = f.read().strip()
        if raw:
            return raw

    api_key = os.environ.get("ANTENNA_API_KEY")
    if api_key:
        return f"Api-Key {api_key}"

    token = os.environ.get("ANTENNA_API_AUTH_TOKEN")
    if token:
        return f"Token {token}"

    # No cached header, no API key, no static token → log in with user/password.
    email = os.environ["ANTENNA_USER"]
    password = os.environ["ANTENNA_PASSWORD"]
    api_url = os.environ["ANTENNA_API_URL"]
    for attempt in range(MAX_LOGIN_ATTEMPTS):
        try:
            r = requests.post(
                f"{api_url}/api/v2/auth/token/login/",
                json={"email": email, "password": password},
                timeout=10,
            )
            r.raise_for_status()
            return f"Token {r.json()['auth_token']}"
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as e:
            LOG.info("Worker login retry %d/%d: %s", attempt + 1, MAX_LOGIN_ATTEMPTS, e)
            time.sleep(LOGIN_RETRY_DELAY)
    raise RuntimeError("Worker could not authenticate with Antenna")


def _client_info() -> ProcessingServiceClientInfo:
    """Metadata sent alongside each task/result request.

    `ProcessingServiceClientInfo` has `extra="allow"`, so any fields here are
    forwarded to Antenna verbatim.
    """
    return ProcessingServiceClientInfo.model_validate(
        {
            "hostname": socket.gethostname(),
            "software": "antenna-minimal-worker",
            "version": "0.1.0",
            "platform": platform.platform(),
        }
    )


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    api_url = os.environ["ANTENNA_API_URL"]

    auth = _load_auth_header()

    # Late import so tests can run without the worker-side api deps on the path.
    from worker.client import AntennaClient
    from worker.loop import Loop

    client = AntennaClient(api_url, auth, timeout=float(os.environ["WORKER_REQUEST_TIMEOUT_SECONDS"]))
    loop = Loop(client, _client_info())
    loop.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
