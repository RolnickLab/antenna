"""
Hand a training request to a processing service.

Antenna sends a URL, not the rows. See ami/ml/training_dataset.py for why.
"""

import logging
import typing
from urllib.parse import urljoin

from django.conf import settings

from ami.utils.requests import create_session, extract_error_message_from_response

logger = logging.getLogger(__name__)

# How long to wait for the service to acknowledge the request. This is not how long
# training takes: a service that answers within this window returns its result inline,
# and one that does not is expected to report back through the job's result endpoint.
DISPATCH_TIMEOUT_SECONDS = 600


def absolute_media_url(url: str, base_url: str | None = None) -> str:
    """
    Turn a stored file's URL into one a processing service can fetch.

    In production MEDIA_URL is already an absolute S3 URL and this is a no-op. Locally it is
    the relative /media/ path, so it needs a base in front. EXTERNAL_BASE_URL points at the
    UI, which is not always where media is served from, so a job may override it.
    """
    if url.startswith("http://") or url.startswith("https://"):
        return url
    base = base_url or getattr(settings, "EXTERNAL_BASE_URL", "")
    if not base:
        raise ValueError(
            "The training set is stored at a relative URL and no base URL is configured, so the "
            "processing service has no way to download it. Set EXTERNAL_BASE_URL, or pass "
            "media_base_url in the job params."
        )
    return urljoin(base.rstrip("/") + "/", url.lstrip("/"))


def send_training_request(job, service, algorithm, dataset: dict) -> dict | None:
    """
    Ask a processing service to retrain a head.

    Returns the service's result if it answered inline, or None if it accepted the work and
    will report back later. Raises if the service refused the request.
    """
    endpoint = urljoin(service.endpoint_url.rstrip("/") + "/", "train")
    payload: dict[str, typing.Any] = {
        "dataset_url": absolute_media_url(dataset["url"], (job.params or {}).get("media_base_url")),
        "algorithm_key": algorithm.key,
        "job_id": job.pk,
        "name": f"{algorithm.key}-job-{job.pk}",
        "min_per_species": (job.params or {}).get("min_per_species", 2),
    }

    callback = (job.params or {}).get("callback_url")
    if callback:
        payload["callback_url"] = callback
        payload["callback_token"] = (job.params or {}).get("callback_token")

    job.logger.info(f"Sending training request to {endpoint} for {algorithm.key}")
    session = create_session()
    response = session.post(endpoint, json=payload, timeout=DISPATCH_TIMEOUT_SECONDS)

    if not response.ok:
        message = extract_error_message_from_response(response)
        raise ValueError(f"The processing service refused the training request: {message}")

    try:
        return response.json()
    except ValueError:
        # Accepted, but nothing useful in the body. The service will report back.
        return None
