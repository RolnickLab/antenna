"""
Keep a copy of the head a processing service produced.

A retrained head only ever existed on the service's own disk, under a cache directory, so
a container rebuild or a cleared cache lost it. Antenna recorded that a version existed
but not where its weights were, which makes promoting one later meaningless: the artifact
being promoted may be gone.

The service uploads the head here rather than to storage directly. It holds no storage
credentials — it fetches everything over plain URLs — and a presigned upload would only
work where the storage backend is S3, not against the local filesystem. Going through
Antenna works the same in both, and reuses the signed token the service already has.

This is the opposite direction to ami/ml/training_dataset.py, which hands the service a
URL rather than the bytes. A training set runs to hundreds of megabytes; a head is a
single small matrix, so the cost of passing it through is not worth avoiding.
"""

import logging
import typing

from django.core.files.storage import default_storage
from django.utils.text import slugify

logger = logging.getLogger(__name__)

HEAD_DIRECTORY = "algorithms"

# A head is one Linear layer: 72 KB over 17 species, about 3 MB over 749. The cap is well
# clear of that and only exists so a wrong or hostile upload cannot fill the bucket.
MAX_HEAD_BYTES = 64 * 1024 * 1024


class HeadTooLarge(Exception):
    """The upload is larger than any head this could reasonably be."""


def head_path(algorithm_key: str, job_id: int, filename: str) -> str:
    """Where one job's head is kept. Deterministic, so a re-run replaces its own file."""
    return f"{HEAD_DIRECTORY}/{slugify(algorithm_key)}-job-{job_id}/{filename}"


def store(algorithm_key: str, job_id: int, files: dict) -> dict[str, typing.Any]:
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
