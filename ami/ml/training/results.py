"""
What a retrain learned from, recorded per occurrence and as two occurrence sets.

The training set builder decides, for every verified occurrence in scope, whether it goes in
the train split, the test split, or nowhere and why. That is written down twice: as a
``classifier_training`` algorithm result on each occurrence, and as a train and a test
``OccurrenceSet`` named after the job, so the run can be repeated and its test set reused.
"""

from __future__ import annotations

import dataclasses
import logging
import typing

from django.db import transaction

from ami.ml.models import AlgorithmResult
from ami.ml.results.schemas import DeterminationSnapshot
from ami.ml.schemas import NamedReference

if typing.TYPE_CHECKING:
    from ami.jobs.models import Job
    from ami.ml.models import Algorithm

logger = logging.getLogger(__name__)

# Why a verified occurrence in scope was left out of the training set.
REJECT_NOT_IN_TAXA_LIST = "not_in_taxa_list"
REJECT_TOO_FEW_EXAMPLES = "below_min_per_species"
REJECT_NO_EMBEDDING = "no_embedding"
RejectReason = typing.Literal["not_in_taxa_list", "below_min_per_species", "no_embedding"]

WRITE_BATCH_SIZE = 2000


class ClassifierTrainingResultData(DeterminationSnapshot):
    """
    How one verified occurrence took part in a retrain.

    ``determination_before_id`` is the label the training set gave it. A retrain changes no
    determination, so ``determination_after_id`` stays empty.
    """

    kind: typing.ClassVar[str] = "classifier_training"
    value_field: typing.ClassVar[str | None] = "species_train_accuracy"

    # "train" or "test" for an occurrence in the training set; None for one left out.
    split: typing.Literal["train", "test"] | None = None
    # True only on the train split: test rows score the head but are not fitted on.
    used_for_training: bool = False
    rejected: bool = False
    reject_reason: RejectReason | None = None
    # The new head's top-1 on the training rows of this occurrence's species, when the service
    # reports it per class. None when it does not, which no service does yet.
    species_train_accuracy: float | None = None


@dataclasses.dataclass
class OccurrenceInTraining:
    """One verified occurrence as the training set builder saw it."""

    label_id: int
    split: str | None = None
    reject_reason: str | None = None


def save_split_sets(job: Job, occurrences: dict[int, OccurrenceInTraining]) -> dict[str, NamedReference]:
    """
    Store the train and test occurrences of this run as two occurrence sets named after the job.

    A re-run of the same job refills its own sets rather than adding two more.
    """
    from ami.main.models import OccurrenceSet, OccurrenceSetMember
    from ami.ml.training.dataset import SPLITS

    sets: dict[str, OccurrenceSet] = {}
    with transaction.atomic():
        for split in SPLITS:
            name = f"Job #{job.pk} {split} set"
            occurrence_set = OccurrenceSet.objects.filter(name=name, project=job.project).first()
            if occurrence_set is None:
                occurrence_set = OccurrenceSet.objects.create(
                    name=name,
                    project=job.project,
                    description=f"The {split} split of training job #{job.pk} ({job.name}).",
                )
            sets[split] = occurrence_set

        # Replace the members rather than add to them (add_members() merges). The ids are
        # this project's verified occurrences, so add_members()'s project check is not needed.
        OccurrenceSetMember.objects.filter(occurrence_set_id__in=[s.pk for s in sets.values()]).delete()
        OccurrenceSetMember.objects.bulk_create(
            (
                OccurrenceSetMember(occurrence_set_id=sets[entry.split].pk, occurrence_id=occurrence_id)
                for occurrence_id, entry in occurrences.items()
                if entry.split in sets
            ),
            batch_size=WRITE_BATCH_SIZE,
        )
    return {split: NamedReference(id=s.pk, name=s.name) for split, s in sets.items()}


def record_training_occurrences(job: Job, algorithm: Algorithm, occurrences: dict[int, OccurrenceInTraining]) -> int:
    """
    Write one ``classifier_training`` result per verified occurrence the run considered.

    Written when the training set is built, the only time each occurrence's label and the
    reason it was left out are known; the service's per-species figures are filled in when its
    result arrives. A re-run of the same job replaces its own results, since it rebuilds the set.
    """
    kind = ClassifierTrainingResultData.kind
    with transaction.atomic():
        AlgorithmResult.objects.filter(job=job, kind=kind).delete()
        # Every occurrence here came from the job's project, so it is copied rather than looked up.
        results = [
            AlgorithmResult(
                project_id=job.project_id,
                occurrence_id=occurrence_id,
                algorithm=algorithm,
                job=job,
                kind=kind,
                data={
                    "determination_before_id": entry.label_id,
                    "split": entry.split,
                    "used_for_training": entry.split == "train",
                    "rejected": entry.reject_reason is not None,
                    "reject_reason": entry.reject_reason,
                },
            )
            for occurrence_id, entry in occurrences.items()
        ]
        AlgorithmResult.objects.bulk_create(results, batch_size=WRITE_BATCH_SIZE)
    return len(results)


def record_species_accuracy(job: Job, accuracy_by_label: dict[str, float]) -> int:
    """
    Copy the service's per-species train accuracy onto this job's results, by label name.

    Occurrences left out of the training set keep None: their species was not trained.
    Returns how many results were updated.
    """
    from ami.main.models import Taxon

    if not accuracy_by_label:
        return 0
    # One label name per taxon id; a run's labels are taxon names (see build_training_dataset).
    accuracy_by_taxon = {
        pk: accuracy_by_label[name]
        for pk, name in Taxon.objects.filter(name__in=list(accuracy_by_label)).values_list("pk", "name")
    }
    results = (
        AlgorithmResult.objects.filter(job=job, kind=ClassifierTrainingResultData.kind, data__rejected=False)
        .only("pk", "kind", "data")
        .order_by("pk")
    )
    updated: list[AlgorithmResult] = []
    count = 0
    for result in results.iterator(chunk_size=WRITE_BATCH_SIZE):
        accuracy = accuracy_by_taxon.get(result.data.get("determination_before_id"))
        if accuracy is None:
            continue
        result.data = {**result.data, "species_train_accuracy": accuracy}
        updated.append(result)
        if len(updated) >= WRITE_BATCH_SIZE:
            AlgorithmResult.objects.bulk_update(updated, ["data"])
            count += len(updated)
            updated = []
    if updated:
        AlgorithmResult.objects.bulk_update(updated, ["data"])
        count += len(updated)
    return count
