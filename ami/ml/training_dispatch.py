"""
Hand a training request to a processing service.

Antenna sends a URL, not the rows. See ami/ml/training_dataset.py for why.
"""

import logging
import typing
from urllib.parse import urljoin

from django.conf import settings
from django.core import signing
from django.urls import reverse

from ami.utils.requests import create_session, extract_error_message_from_response

logger = logging.getLogger(__name__)

# How long to wait for the service to acknowledge the request. This is not how long
# training takes: a service that answers within this window returns its result inline,
# and one that does not is expected to report back through the job's result endpoint.
DISPATCH_TIMEOUT_SECONDS = 600


# A processing service has no Antenna account, so the callback is authorised by a signed
# token instead. Nothing is stored: the signature carries the job id and Django's secret
# key proves Antenna issued it.
CALLBACK_SALT = "ami.ml.training.callback"
CALLBACK_MAX_AGE_SECONDS = 60 * 60 * 24


def make_callback_token(job) -> str:
    """A token only Antenna could have produced, tied to this one job."""
    return signing.dumps({"job_id": job.pk}, salt=CALLBACK_SALT)


def verify_callback_token(token: str, job) -> bool:
    """True when the token is Antenna's, unexpired, and for this job."""
    if not token:
        return False
    try:
        payload = signing.loads(token, salt=CALLBACK_SALT, max_age=CALLBACK_MAX_AGE_SECONDS)
    except signing.BadSignature:
        return False
    return payload.get("job_id") == job.pk


def _callback_base(job) -> str:
    """Where the service can reach this Antenna."""
    base = (job.params or {}).get("media_base_url") or getattr(settings, "EXTERNAL_BASE_URL", "")
    if not base:
        raise ValueError(
            "No base URL is configured, so the processing service has no way to report back. "
            "Set EXTERNAL_BASE_URL, or pass media_base_url in the job params."
        )
    return base


def callback_url_for(job) -> str:
    """Where the service should post its result when training finishes."""
    # reverse(), so the path follows the router rather than a copy of it here.
    path = reverse("api:job-training-result", args=[job.pk])
    return urljoin(_callback_base(job).rstrip("/") + "/", path.lstrip("/"))


def head_upload_url_for(job) -> str:
    """Where the service should upload the head it produced, so Antenna keeps a copy."""
    path = reverse("api:job-training-head", args=[job.pk])
    return urljoin(_callback_base(job).rstrip("/") + "/", path.lstrip("/"))


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
    params = job.params or {}
    config = algorithm.training_config
    payload: dict[str, typing.Any] = {
        "dataset_url": absolute_media_url(dataset["url"], params.get("media_base_url")),
        "algorithm_key": algorithm.key,
        "job_id": job.pk,
        "name": f"{algorithm.key}-job-{job.pk}",
        "min_per_species": params.get("min_per_species", config.min_per_species),
        # The fitting settings the service published, so an admin can tune them in Antenna
        # without redeploying the service.
        "min_improvement": params.get("min_improvement", config.min_improvement),
        "head_type": params.get("head_type", config.head_type),
        "epochs": params.get("epochs", config.epochs),
        "learning_rate": params.get("learning_rate", config.learning_rate),
        "weight_decay": params.get("weight_decay", config.weight_decay),
    }

    # Always sent: a service that finishes after the request times out reports back here
    # instead, which is the only way a real training set can work.
    payload["callback_url"] = (job.params or {}).get("callback_url") or callback_url_for(job)
    payload["callback_token"] = make_callback_token(job)
    # The head itself comes back here. A service that does not support the upload simply
    # ignores this, and the version is registered without a stored copy as before.
    payload["head_upload_url"] = head_upload_url_for(job)

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
