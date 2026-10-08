"""
Hand a training request to a processing service, and keep what it sends back.

Outward: a URL to the dataset rather than the rows (see ``dataset``), plus a signed token
the service reports back with.

Inward: the service uploads the finished head through Antenna rather than to storage. It
holds no storage credentials, and a presigned upload would only work on S3, not against the
local filesystem. A head is one small matrix, so passing it through costs little.
"""

import logging
import typing
from typing import TYPE_CHECKING
from urllib.parse import urljoin

from django.conf import settings
from django.core import signing
from django.core.files.storage import default_storage
from django.urls import reverse
from django.utils.text import slugify

from ami.ml.schemas import AlgorithmTrainingConfig
from ami.utils.requests import create_session, extract_error_message_from_response

if TYPE_CHECKING:
    from ami.jobs.models import Job
    from ami.ml.models import Algorithm, ProcessingService

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


def make_callback_token(job: "Job") -> str:
    """A token only Antenna could have produced, tied to this one job."""
    return signing.dumps({"job_id": job.pk}, salt=CALLBACK_SALT)


def verify_callback_token(token: str, job: "Job") -> bool:
    """True when the token is Antenna's, unexpired, and for this job."""
    if not token:
        return False
    try:
        payload = signing.loads(token, salt=CALLBACK_SALT, max_age=CALLBACK_MAX_AGE_SECONDS)
    except signing.BadSignature:
        return False
    return payload.get("job_id") == job.pk


def _callback_base(job: "Job") -> str:
    """
    Where the service can reach this Antenna.

    Deliberately not taken from the job's params. Params are free JSON that any member who
    can create a job may set, and this base decides where the signed callback token is
    sent -- a token that also unlocks the head upload. A per-deployment override belongs
    in settings, not in a request body.
    """
    base = getattr(settings, "EXTERNAL_BASE_URL", "")
    if not base:
        raise ValueError(
            "No base URL is configured, so the processing service has no way to report back. " "Set EXTERNAL_BASE_URL."
        )
    return base


def callback_url_for(job: "Job") -> str:
    """Where the service should post its result when training finishes."""
    # reverse(), so the path follows the router rather than a copy of it here.
    path = reverse("api:job-training-result", args=[job.pk])
    return urljoin(_callback_base(job).rstrip("/") + "/", path.lstrip("/"))


def head_upload_url_for(job: "Job") -> str:
    """Where the service should upload the head it produced, so Antenna keeps a copy."""
    path = reverse("api:job-training-head", args=[job.pk])
    return urljoin(_callback_base(job).rstrip("/") + "/", path.lstrip("/"))


def absolute_media_url(url: str, base_url: str | None = None) -> str:
    """
    Turn a stored file's URL into one a processing service can fetch.

    In production MEDIA_URL is already an absolute S3 URL and this is a no-op. Locally it is
    the relative /media/ path, so it needs a base in front.
    """
    if url.startswith("http://") or url.startswith("https://"):
        return url
    base = base_url or getattr(settings, "EXTERNAL_BASE_URL", "")
    if not base:
        raise ValueError(
            "The training set is stored at a relative URL and no base URL is configured, so the "
            "processing service has no way to download it. Set EXTERNAL_BASE_URL."
        )
    return urljoin(base.rstrip("/") + "/", url.lstrip("/"))


def send_training_request(
    job: "Job", service: "ProcessingService", algorithm: "Algorithm", dataset: dict
) -> dict | None:
    """
    Ask a processing service to retrain a head.

    Returns the service's result if it answered inline, or None if it accepted the work and
    will report back later. Raises if the service refused the request.
    """
    endpoint = urljoin(service.endpoint_url.rstrip("/") + "/", "train")
    # The same merge the job validated before it built the dataset, so the service is told
    # the settings the training set was actually made under. Reading job.params again here
    # would let the two drift, and would send values nothing had checked.
    config = AlgorithmTrainingConfig.for_run(algorithm.training_config, job.params or {})
    payload: dict[str, typing.Any] = {
        "dataset_url": absolute_media_url(dataset["url"]),
        "algorithm_key": algorithm.key,
        "job_id": job.pk,
        "name": f"{algorithm.key}-job-{job.pk}",
        "min_per_species": config.min_per_species,
        # The fitting settings the service published, so an admin can tune them in Antenna
        # without redeploying the service.
        "min_improvement": config.min_improvement,
        "head_type": config.head_type,
        "epochs": config.epochs,
        "learning_rate": config.learning_rate,
        "weight_decay": config.weight_decay,
    }

    # Always sent: a service that finishes after the request times out reports back here
    # instead, which is the only way a real training set can work.
    payload["callback_url"] = callback_url_for(job)
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


HEAD_DIRECTORY = "algorithms"

# A head is one Linear layer: 72 KB over 17 species, about 3 MB over 749. The cap is well
# clear of that and only exists so a wrong or hostile upload cannot fill the bucket.
MAX_HEAD_BYTES = 64 * 1024 * 1024


class HeadTooLarge(Exception):
    """The upload is larger than any head this could reasonably be."""


def head_path(algorithm_key: str, job_id: int, filename: str) -> str:
    """Where one job's head is kept. Deterministic, so a re-run replaces its own file."""
    return f"{HEAD_DIRECTORY}/{slugify(algorithm_key)}-job-{job_id}/{filename}"


def store_head(algorithm_key: str, job_id: int, files: dict) -> dict[str, typing.Any]:
    """
    Save the uploaded head files and return where they landed.

    Returns the storage path and URL of each file, keyed by the name it was uploaded
    under, so the caller can record the head's location against the algorithm version.
    """
    stored = {}
    for name, uploaded in files.items():
        if uploaded.size > MAX_HEAD_BYTES:
            raise HeadTooLarge(f"'{name}' is {uploaded.size} bytes; the limit is {MAX_HEAD_BYTES}.")

        path = head_path(algorithm_key, job_id, uploaded.name)
        if default_storage.exists(path):
            # A re-run of the same job replaces its head instead of piling up copies,
            # matching how the training set is written.
            default_storage.delete(path)
        saved_path = default_storage.save(path, uploaded)
        stored[name] = {"path": saved_path, "url": default_storage.url(saved_path)}
        logger.info(f"Stored '{name}' for job {job_id} at {saved_path}")

    return stored
