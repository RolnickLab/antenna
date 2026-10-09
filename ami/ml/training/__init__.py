"""
Retraining a classifier head from the species people have verified.

``dataset`` decides what the head learns from and writes it to storage. The names
re-exported here are the ones callers outside this package use; anything else is internal
to it.
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

__all__ = [
    "DEFAULT_SPLIT_SALT",
    "DEFAULT_TEST_FRACTION",
    "SPLITS",
    "SPLIT_TEST",
    "SPLIT_TRAIN",
    "NotEnoughVerifiedData",
    "build_training_dataset",
    "count_missing_embeddings",
    "label_counts",
    "row_as_dict",
    "species_with_enough_examples",
    "split_for",
    "verified_occurrence_ids",
    "verified_training_rows",
]
