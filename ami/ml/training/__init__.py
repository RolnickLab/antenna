"""
Retraining a classifier head from the species people have verified.

``dataset`` decides what the head learns from and writes it to storage; ``service`` hands a
processing service the URL and keeps the head that comes back. The names re-exported here
are the ones callers outside this package use; anything else is internal to it.
"""

from ami.ml.training.dataset import (
    DEFAULT_SPLIT_SALT,
    DEFAULT_TEST_FRACTION,
    SPLIT_TEST,
    SPLIT_TRAIN,
    SPLITS,
    NotEnoughVerifiedData,
    build_training_dataset,
    count_missing_embeddings,
    label_counts,
    row_as_dict,
    species_with_enough_examples,
    split_for,
    verified_occurrence_ids,
    verified_training_rows,
)
from ami.ml.training.service import (
    CALLBACK_MAX_AGE_SECONDS,
    DISPATCH_TIMEOUT_SECONDS,
    MAX_HEAD_BYTES,
    HeadTooLarge,
    absolute_media_url,
    callback_url_for,
    head_path,
    head_upload_url_for,
    make_callback_token,
    progress_url_for,
    send_training_request,
    store_head,
    verify_callback_token,
)

__all__ = [
    "CALLBACK_MAX_AGE_SECONDS",
    "DEFAULT_SPLIT_SALT",
    "DEFAULT_TEST_FRACTION",
    "DISPATCH_TIMEOUT_SECONDS",
    "MAX_HEAD_BYTES",
    "SPLITS",
    "SPLIT_TEST",
    "SPLIT_TRAIN",
    "HeadTooLarge",
    "NotEnoughVerifiedData",
    "absolute_media_url",
    "build_training_dataset",
    "callback_url_for",
    "count_missing_embeddings",
    "head_path",
    "head_upload_url_for",
    "label_counts",
    "make_callback_token",
    "progress_url_for",
    "row_as_dict",
    "send_training_request",
    "species_with_enough_examples",
    "split_for",
    "store_head",
    "verified_occurrence_ids",
    "verified_training_rows",
    "verify_callback_token",
]
