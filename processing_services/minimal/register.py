"""
Self-register this processing service's pipelines with Antenna.

What this does, in order:
  1. Resolve an Authorization header (env var or fallback login).
  2. Resolve the target project id (env var, else look up by name).
  3. Fetch our own /info to get the list of pipelines this container serves.
  4. POST that list to `/api/v2/projects/{id}/pipelines/` so Antenna knows which
     async pipelines this ProcessingService can handle.

About identity: on main, the server looks up / creates a `ProcessingService`
record by the `processing_service_name` field in the request body, and grants
write access based on the Authorization header's user. PR #1194 changes that
to use API keys — the PS record is derived from the key itself and
`processing_service_name` is no longer sent. We tolerate both by sending
`processing_service_name` now; #1194-enabled Antenna will ignore the field and
pick the PS from the key.

Env vars are read via `os.environ[...]` without fallbacks — the .env file is
expected to provide them. See `processing_services/.env.example`.
"""

import logging
import os
import sys
import time

import requests
from api.api import pipelines as pipeline_classes  # type: ignore[import-not-found]
from api.schemas import PipelineConfigResponse  # type: ignore[import-not-found]
from worker.schemas import (  # type: ignore[import-not-found]
    AsyncPipelineRegistrationRequest,
    ProcessingServiceClientInfo,
)

logger = logging.getLogger(__name__)

MAX_RETRIES = 20
RETRY_DELAY = 3  # seconds

CACHED_AUTH_HEADER_PATH = "/tmp/antenna_auth_header"


def get_client_info() -> ProcessingServiceClientInfo:
    """Identity metadata sent to Antenna in the registration body.

    `ProcessingServiceClientInfo` has `extra="allow"`, so any keys here are
    forwarded verbatim. On main the registration serializer ignores unknown
    fields; PR #1194 consumes this field.
    """
    import platform
    import socket

    return ProcessingServiceClientInfo.model_validate(
        {
            "hostname": socket.gethostname(),
            "software": "antenna-minimal-worker",
            "version": "0.1.0",
            "platform": platform.platform(),
        }
    )


def auth_header() -> dict[str, str] | None:
    """Pick an auth header based on what env vars are set, or None to trigger login flow."""
    api_key = os.environ.get("ANTENNA_API_KEY")
    if api_key:
        # PR #1194 path. Harmless on main — main ignores unknown auth schemes
        # and falls through to the next header, which we don't send.
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

    name = os.environ["ANTENNA_DEFAULT_PROJECT_NAME"]
    resp = requests.get(f"{api_url}/api/v2/projects/", headers=headers, timeout=10)
    resp.raise_for_status()
    for project in resp.json().get("results", []):
        if project.get("name") == name:
            pk = str(project["id"])
            logger.info("Resolved project '%s' to id=%s", name, pk)
            return pk
    raise RuntimeError(f"No project found with name '{name}' — ensure_default_project should have created it")


def fetch_own_pipelines() -> list[PipelineConfigResponse]:
    """Return the pipeline configs this container serves.

    Imported directly from the api module rather than fetched over HTTP from
    the co-located FastAPI service — register.py runs in the same container,
    and importing avoids having to wait for FastAPI to be up (which it isn't
    in MODE=worker).
    """
    return [p.config for p in pipeline_classes]


def register(
    api_url: str,
    project_id: str,
    headers: dict[str, str],
    pipelines: list[PipelineConfigResponse],
) -> None:
    """POST pipelines to the project registration endpoint.

    Sends the schema-defined `AsyncPipelineRegistrationRequest` body. We also
    attach a `client_info` field, which is ignored on main (unknown field) and
    read by PR #1194.
    """
    service_name = os.environ["ANTENNA_SERVICE_NAME"]
    body = AsyncPipelineRegistrationRequest(
        processing_service_name=service_name,
        pipelines=pipelines,
    ).model_dump(mode="json")
    body["client_info"] = get_client_info().model_dump(mode="json")

    url = f"{api_url}/api/v2/projects/{project_id}/pipelines/"
    resp = requests.post(url, json=body, headers=headers, timeout=30)
    if resp.status_code in (200, 201):
        logger.info(
            "Registered %d pipelines as '%s' (project=%s)",
            len(pipelines),
            service_name,
            project_id,
        )
        return
    raise RuntimeError(f"Registration failed: {resp.status_code} {resp.text}")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    api_url = os.environ["ANTENNA_API_URL"]

    pipelines = fetch_own_pipelines()
    if not pipelines:
        logger.warning("No pipelines found from local /info; nothing to register")
        return 0

    # Auth: use explicit header if provided, else log in.
    headers = auth_header()
    if headers is None:
        email = os.environ["ANTENNA_USER"]
        password = os.environ["ANTENNA_PASSWORD"]
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
    with open(CACHED_AUTH_HEADER_PATH, "w") as f:
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
