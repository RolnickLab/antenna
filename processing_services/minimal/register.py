"""
Register this processing service's pipelines with Antenna.

Supports two modes:

1. **API key mode** (recommended for production):
   Set ANTENNA_API_KEY to an existing key. The service authenticates
   directly and registers its pipelines.

2. **Self-provisioning mode** (for local development / docker compose):
   Set ANTENNA_USER and ANTENNA_PASSWORD (defaults to the local dev
   superuser). The service logs in, creates itself via the REST API,
   generates its own API key, and registers pipelines. The generated
   API key is written to /tmp/antenna_api_key for subsequent requests.

Environment variables:
    ANTENNA_API_URL: Base URL of the Antenna API (e.g., http://django:8000)
    ANTENNA_PROJECT_ID: Project ID to register pipelines for
    ANTENNA_API_KEY: API key for authentication (mode 1)
    ANTENNA_USER: Username for self-provisioning (mode 2)
    ANTENNA_PASSWORD: Password for self-provisioning (mode 2)
    ANTENNA_SERVICE_NAME: Name for the processing service (default: hostname)
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

# Local dev defaults (matches .envs/.local/.django)
DEFAULT_USER = "antenna@insectai.org"
DEFAULT_PASSWORD = "localadmin"


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


def login(api_url: str, email: str, password: str) -> str:
    """Log in with user credentials and return an auth token."""
    resp = requests.post(
        f"{api_url}/api/v2/auth/token/login/",
        json={"email": email, "password": password},
        timeout=10,
    )
    resp.raise_for_status()
    token = resp.json().get("auth_token")
    if not token:
        raise ValueError(f"Login succeeded but no auth_token in response: {resp.json()}")
    return token


def create_processing_service(api_url: str, token: str, project_id: str, name: str) -> dict:
    """Create a processing service via the REST API, or return an existing one."""
    headers = {"Authorization": f"Token {token}"}

    # Check if a service with this name already exists in the project
    resp = requests.get(
        f"{api_url}/api/v2/processing-services/",
        headers=headers,
        params={"project_id": project_id},
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    for svc in results:
        if svc.get("name") == name:
            logger.info(f"Found existing processing service: {name} (id={svc['id']})")
            return svc

    # Create new service (no endpoint_url = async/pull-mode)
    resp = requests.post(
        f"{api_url}/api/v2/processing-services/",
        headers=headers,
        params={"project_id": project_id},
        json={"name": name},
        timeout=10,
    )
    resp.raise_for_status()
    svc = resp.json().get("instance", resp.json())
    logger.info(f"Created processing service: {name} (id={svc['id']})")
    return svc


def generate_api_key(api_url: str, token: str, service_id: int) -> str:
    """Generate an API key for the processing service and return the plaintext key."""
    headers = {"Authorization": f"Token {token}"}
    resp = requests.post(
        f"{api_url}/api/v2/processing-services/{service_id}/generate_key/",
        headers=headers,
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["api_key"]


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


def self_provision(api_url: str, project_id: str, email: str, password: str) -> str:
    """
    Self-provision a processing service and return a usable API key.

    Logs in with user credentials, creates the processing service (or finds
    an existing one), and generates an API key. The key is also written to
    /tmp/antenna_api_key for use by subsequent requests.
    """
    service_name = os.environ.get("ANTENNA_SERVICE_NAME", socket.gethostname())

    logger.info(f"Self-provisioning as '{service_name}' (user: {email})")
    token = login(api_url, email, password)

    svc = create_processing_service(api_url, token, project_id, service_name)
    service_id = svc["id"]

    # Check if the service already has a key (from a previous run)
    existing_prefix = svc.get("api_key_prefix")
    api_key_file = "/tmp/antenna_api_key"

    # If we have a cached key from a previous self-provision, try to use it
    if existing_prefix and os.path.exists(api_key_file):
        cached_key = open(api_key_file).read().strip()
        if cached_key.startswith(existing_prefix.split(".")[0]):
            logger.info(f"Reusing cached API key (prefix: {existing_prefix})")
            return cached_key

    # Generate a new key (revokes any previous ones)
    api_key = generate_api_key(api_url, token, service_id)
    logger.info(f"Generated new API key for {service_name}")

    # Cache for subsequent requests
    with open(api_key_file, "w") as f:
        f.write(api_key)

    return api_key


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    api_url = os.environ.get("ANTENNA_API_URL")
    api_key = os.environ.get("ANTENNA_API_KEY")
    project_id = os.environ.get("ANTENNA_PROJECT_ID")

    if not api_key and not os.environ.get("ANTENNA_USER"):
        logger.info("Neither ANTENNA_API_KEY nor ANTENNA_USER set, skipping registration")
        return

    if not api_url:
        logger.error("ANTENNA_API_URL is required for registration")
        sys.exit(1)

    if not project_id:
        logger.error("ANTENNA_PROJECT_ID is required for registration")
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

    # Self-provision if no API key provided
    if not api_key:
        email = os.environ.get("ANTENNA_USER", DEFAULT_USER)
        password = os.environ.get("ANTENNA_PASSWORD", DEFAULT_PASSWORD)

        for attempt in range(MAX_RETRIES):
            try:
                api_key = self_provision(api_url, project_id, email, password)
                break
            except (requests.ConnectionError, requests.Timeout):
                pass
            except requests.HTTPError as e:
                logger.error(f"Self-provisioning failed: {e}")
                if attempt == MAX_RETRIES - 1:
                    sys.exit(1)

            if attempt < MAX_RETRIES - 1:
                logger.info(f"Retrying self-provisioning (attempt {attempt + 1}/{MAX_RETRIES})...")
                time.sleep(RETRY_DELAY)
        else:
            logger.error("Failed to self-provision after all retries")
            sys.exit(1)

    client_info = get_client_info()

    # Register pipelines with the API key
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
