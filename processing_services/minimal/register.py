"""
Self-register this processing service's pipelines with Antenna.

Modeled on the PR #1194 version (which targets API-key auth once merged). For
now this targets main, which still uses user-token auth and requires
`processing_service_name` in the registration body.

Auth priority:
  1. ANTENNA_API_KEY set → use `Api-Key <key>` (TODO: activate once PR #1194 merges)
  2. ANTENNA_API_AUTH_TOKEN set → use `Token <token>`
  3. ANTENNA_USER / ANTENNA_PASSWORD → log in, use the returned token.

Self-provisioning (option 3) matches the local-dev and CI defaults baked into
.envs/.local/.django (antenna@insectai.org / localadmin).

Environment:
  ANTENNA_API_URL          Base URL (e.g. http://django:8000)
  ANTENNA_PROJECT_ID       Project PK OR ANTENNA_DEFAULT_PROJECT_NAME to resolve to one.
  ANTENNA_DEFAULT_PROJECT_NAME  Fallback lookup by name (default: "Default Project")
  ANTENNA_SERVICE_NAME     ProcessingService name (default: minimal-worker-<hostname>)
  ANTENNA_API_KEY          Optional (future, PR #1194 path)
  ANTENNA_API_AUTH_TOKEN   Optional static token (skips login)
  ANTENNA_USER             Fallback login email (default: antenna@insectai.org)
  ANTENNA_PASSWORD         Fallback login password (default: localadmin)
"""

import logging
import os
import platform
import socket
import sys
import time

import requests

logger = logging.getLogger(__name__)

MAX_RETRIES = 20
RETRY_DELAY = 3  # seconds

DEFAULT_USER = "antenna@insectai.org"
DEFAULT_PASSWORD = "localadmin"
DEFAULT_PROJECT_NAME = "Default Project"
LOCAL_INFO_URL = "http://localhost:2000/info"
LOCAL_LIVEZ_URL = "http://localhost:2000/livez"


def get_client_info() -> dict:
    """Identity metadata sent to Antenna.

    Extra keys are allowed by the ProcessingServiceClientInfo schema (Config.extra = "allow"),
    so it's fine to add more here; main's registration endpoint currently ignores this field
    and PR #1194 reads it.
    """
    return {
        "hostname": socket.gethostname(),
        "software": "antenna-minimal-worker",
        "version": "0.1.0",
        "platform": platform.platform(),
    }


def auth_header() -> dict[str, str] | None:
    """Pick an auth header based on what env vars are set, or None to trigger login flow."""
    api_key = os.environ.get("ANTENNA_API_KEY")
    if api_key:
        # TODO(PR #1194): Api-Key auth is enabled on Antenna once #1194 merges.
        return {"Authorization": f"Api-Key {api_key}"}

    token = os.environ.get("ANTENNA_API_AUTH_TOKEN")
    if token:
        return {"Authorization": f"Token {token}"}

    return None


def login(api_url: str, email: str, password: str) -> str:
    resp = requests.post(
        f"{api_url}/api/v2/auth/token/login/",
        json={"email": email, "password": password},
        timeout=10,
    )
    resp.raise_for_status()
    token = resp.json().get("auth_token")
    if not token:
        raise ValueError(f"Login returned no auth_token: {resp.json()}")
    return token


def resolve_project_id(api_url: str, headers: dict[str, str]) -> str:
    """Return ANTENNA_PROJECT_ID if set, else look up by name via REST API."""
    explicit = os.environ.get("ANTENNA_PROJECT_ID")
    if explicit:
        return explicit

    name = os.environ.get("ANTENNA_DEFAULT_PROJECT_NAME", DEFAULT_PROJECT_NAME)
    resp = requests.get(f"{api_url}/api/v2/projects/", headers=headers, timeout=10)
    resp.raise_for_status()
    for project in resp.json().get("results", []):
        if project.get("name") == name:
            pk = str(project["id"])
            logger.info("Resolved project '%s' to id=%s", name, pk)
            return pk
    raise RuntimeError(f"No project found with name '{name}' — ensure_default_project should have created it")


def fetch_own_pipelines() -> list[dict]:
    resp = requests.get(LOCAL_INFO_URL, timeout=5)
    resp.raise_for_status()
    return resp.json().get("pipelines", [])


def wait_for_local_server() -> None:
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(LOCAL_LIVEZ_URL, timeout=2)
            if r.status_code == 200:
                return
        except (requests.ConnectionError, requests.Timeout):
            pass
        logger.info("Waiting for local FastAPI server (%d/%d)", attempt + 1, MAX_RETRIES)
        time.sleep(RETRY_DELAY)
    raise RuntimeError("Local FastAPI server did not come up in time")


def register(api_url: str, project_id: str, headers: dict[str, str], pipelines: list[dict]) -> None:
    """POST pipelines to the project registration endpoint.

    Body shape for main:
        {"processing_service_name": str, "pipelines": [...], "client_info": {...}}
    PR #1194 drops `processing_service_name`. Sending both now is safe because
    main's serializer ignores unknown fields and #1194's serializer ignores
    `processing_service_name`.
    """
    service_name = os.environ.get("ANTENNA_SERVICE_NAME", f"minimal-worker-{socket.gethostname()}")
    payload = {
        "processing_service_name": service_name,
        "pipelines": pipelines,
        "client_info": get_client_info(),
    }
    url = f"{api_url}/api/v2/projects/{project_id}/pipelines/"
    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    if resp.status_code in (200, 201):
        logger.info("Registered %d pipelines as '%s' (project=%s)", len(pipelines), service_name, project_id)
        return
    raise RuntimeError(f"Registration failed: {resp.status_code} {resp.text}")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    api_url = os.environ.get("ANTENNA_API_URL")
    if not api_url:
        logger.error("ANTENNA_API_URL not set; skipping registration")
        return 0

    wait_for_local_server()
    pipelines = fetch_own_pipelines()
    if not pipelines:
        logger.warning("No pipelines found from local /info; nothing to register")
        return 0

    # Auth: use explicit header if provided, else log in.
    headers = auth_header()
    if headers is None:
        email = os.environ.get("ANTENNA_USER", DEFAULT_USER)
        password = os.environ.get("ANTENNA_PASSWORD", DEFAULT_PASSWORD)
        # Retry login so we tolerate "Django not up yet".
        for attempt in range(MAX_RETRIES):
            try:
                token = login(api_url, email, password)
                headers = {"Authorization": f"Token {token}"}
                break
            except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as e:
                logger.info("Login retry (%d/%d): %s", attempt + 1, MAX_RETRIES, e)
                time.sleep(RETRY_DELAY)
        else:
            logger.error("Could not authenticate after %d attempts", MAX_RETRIES)
            return 1

    # Resolve project id (may also need to wait for ensure_default_project to run).
    project_id = None
    for attempt in range(MAX_RETRIES):
        try:
            project_id = resolve_project_id(api_url, headers)
            break
        except (requests.ConnectionError, requests.Timeout, RuntimeError) as e:
            logger.info("Project lookup retry (%d/%d): %s", attempt + 1, MAX_RETRIES, e)
            time.sleep(RETRY_DELAY)
    if project_id is None:
        logger.error("Could not resolve project after %d attempts", MAX_RETRIES)
        return 1

    # Cache the resolved id and auth header for worker_main.py to reuse.
    os.environ["ANTENNA_PROJECT_ID"] = project_id
    with open("/tmp/antenna_auth_header", "w") as f:
        f.write(next(iter(headers.values())))

    for attempt in range(MAX_RETRIES):
        try:
            register(api_url, project_id, headers, pipelines)
            return 0
        except (requests.ConnectionError, requests.Timeout) as e:
            logger.info("Registration retry (%d/%d): %s", attempt + 1, MAX_RETRIES, e)
            time.sleep(RETRY_DELAY)
        except RuntimeError as e:
            logger.error("%s", e)
            return 1

    logger.error("Registration failed after %d attempts", MAX_RETRIES)
    return 1


if __name__ == "__main__":
    sys.exit(main())
