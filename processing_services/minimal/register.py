"""
Register this processing service's pipelines with Antenna.

Reads configuration from environment variables:
    ANTENNA_API_URL: Base URL of the Antenna API (e.g., http://django:8000)
    ANTENNA_API_KEY: API key for authentication (Api-Key header)
    ANTENNA_PROJECT_ID: Project ID to register pipelines for

If ANTENNA_API_KEY is not set, registration is skipped (legacy push-mode behavior).
"""

import logging
import os
import platform
import socket
import sys
import time

import requests

logger = logging.getLogger(__name__)

MAX_RETRIES = 10
RETRY_DELAY = 5  # seconds


def get_client_info() -> dict:
    return {
        "hostname": socket.gethostname(),
        "software": "antenna-minimal-ps",
        "version": "0.1.0",
        "platform": platform.platform(),
    }


def get_own_pipeline_configs(port: int = 2000) -> list[dict]:
    """Fetch pipeline configs from our own /info endpoint."""
    resp = requests.get(f"http://localhost:{port}/info", timeout=5)
    resp.raise_for_status()
    info = resp.json()
    return info.get("pipelines", [])


def register_with_antenna(
    api_url: str,
    api_key: str,
    project_id: str,
    pipelines: list[dict],
    client_info: dict,
) -> bool:
    """Register pipelines with Antenna's pipeline registration endpoint."""
    url = f"{api_url}/api/v2/projects/{project_id}/pipelines/"
    headers = {"Authorization": f"Api-Key {api_key}"}
    payload = {
        "pipelines": pipelines,
        "client_info": client_info,
    }

    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    if resp.status_code == 201:
        logger.info(f"Registered {len(pipelines)} pipelines with Antenna")
        return True
    else:
        logger.error(f"Registration failed: {resp.status_code} {resp.text}")
        return False


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    api_url = os.environ.get("ANTENNA_API_URL")
    api_key = os.environ.get("ANTENNA_API_KEY")
    project_id = os.environ.get("ANTENNA_PROJECT_ID")

    if not api_key:
        logger.info("ANTENNA_API_KEY not set, skipping registration (push-mode)")
        return

    if not api_url:
        logger.error("ANTENNA_API_URL is required when ANTENNA_API_KEY is set")
        sys.exit(1)

    if not project_id:
        logger.error("ANTENNA_PROJECT_ID is required when ANTENNA_API_KEY is set")
        sys.exit(1)

    # Wait for our own FastAPI server to be ready
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get("http://localhost:2000/livez", timeout=2)
            resp.raise_for_status()
            break
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError):
            if attempt < MAX_RETRIES - 1:
                logger.info(f"Waiting for local server to start (attempt {attempt + 1}/{MAX_RETRIES})...")
                time.sleep(RETRY_DELAY)
            else:
                logger.error("Local server did not start in time")
                sys.exit(1)

    # Fetch our own pipeline configs
    try:
        pipelines = get_own_pipeline_configs()
    except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as e:
        logger.error(f"Failed to fetch pipeline configs from local server: {e}")
        sys.exit(1)
    client_info = get_client_info()

    # Register with Antenna (retry in case Antenna isn't ready yet)
    for attempt in range(MAX_RETRIES):
        try:
            if register_with_antenna(api_url, api_key, project_id, pipelines, client_info):
                return
        except (requests.ConnectionError, requests.Timeout):
            pass

        if attempt < MAX_RETRIES - 1:
            logger.info(f"Retrying registration (attempt {attempt + 1}/{MAX_RETRIES})...")
            time.sleep(RETRY_DELAY)

    logger.error("Failed to register with Antenna after all retries")
    sys.exit(1)


if __name__ == "__main__":
    main()
