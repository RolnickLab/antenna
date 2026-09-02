"""
Batch creation of identifications.

Resolves every row a batch references in a fixed number of queries, validates
each item against the resolved batch, then saves each item inside its own
savepoint so one bad item does not abort the rest. See #1371.
"""

import logging

from django.contrib.auth.models import AbstractUser
from django.core import exceptions
from django.db import IntegrityError, transaction

from ami.main.models import Classification, Identification, Occurrence, Taxon

logger = logging.getLogger(__name__)


def resolve_occurrences(items: list[dict]) -> dict[int, Occurrence]:
    """Fetch every occurrence in the batch in one query, with its project loaded."""
    occurrence_ids = {item["occurrence_id"] for item in items}
    # select_related("project") lets the caller's permission check and the
    # single-project check read the project without a query per occurrence.
    return {
        occurrence.pk: occurrence
        for occurrence in Occurrence.objects.filter(pk__in=occurrence_ids).select_related("project")
    }


def create_identifications_batch(
    items: list[dict],
    user: AbstractUser,
    occurrences: dict[int, Occurrence],
) -> list[dict]:
    """
    Save one identification per item and report an outcome per item.

    Returns one result dict per item, in item order: ``{index, occurrence_id,
    status: "created", id}`` on success, ``{index, occurrence_id, status:
    "error", errors}`` on failure. A failed item never aborts the batch.
    The caller is responsible for authorization; ``occurrences`` comes from
    :func:`resolve_occurrences` so the permission check and the writes see the
    same rows.
    """
    taxa = _resolve_taxa(items)
    agreed_identifications, agreed_predictions = _resolve_agreement_targets(items)

    results = []
    for index, item in enumerate(items):
        errors = _validate_item(item, occurrences, taxa, agreed_identifications, agreed_predictions)
        if errors:
            results.append(
                {
                    "index": index,
                    "occurrence_id": item["occurrence_id"],
                    "status": "error",
                    "errors": errors,
                }
            )
            continue

        identification = Identification(
            occurrence=occurrences[item["occurrence_id"]],
            taxon=taxa[item["taxon_id"]],
            user=user,
            comment=item["comment"],
            agreed_with_identification=agreed_identifications.get(item["agreed_with_identification_id"]),
            agreed_with_prediction=agreed_predictions.get(item["agreed_with_prediction_id"]),
        )
        try:
            # Under ATOMIC_REQUESTS this is a savepoint, so rolling it back
            # discards only this item and the rest of the batch continues.
            # save() also withdraws the user's earlier identification on this
            # occurrence and recomputes the determination. See #1371.
            with transaction.atomic():
                identification.save()
        except (IntegrityError, exceptions.ObjectDoesNotExist) as error:
            # A referenced row (the occurrence, or something save() touches)
            # was deleted between resolving the batch and writing this item.
            logger.warning(
                f"Bulk identification of occurrence {item['occurrence_id']} failed and was skipped: {error}"
            )
            results.append(
                {
                    "index": index,
                    "occurrence_id": item["occurrence_id"],
                    "status": "error",
                    "errors": {
                        "occurrence_id": [
                            "This identification could not be saved. "
                            "A related record may have been deleted. Refresh and retry."
                        ]
                    },
                }
            )
            continue

        results.append(
            {
                "index": index,
                "occurrence_id": item["occurrence_id"],
                "status": "created",
                "id": identification.pk,
            }
        )

    return results


def _resolve_taxa(items: list[dict]) -> dict[int, Taxon]:
    """Fetch every taxon in the batch in one query."""
    taxon_ids = {item["taxon_id"] for item in items}
    return {taxon.pk: taxon for taxon in Taxon.objects.filter(pk__in=taxon_ids)}


def _resolve_agreement_targets(
    items: list[dict],
) -> tuple[dict[int, Identification], dict[int, Classification]]:
    """Fetch the identifications and predictions that items claim to agree with."""
    identification_ids = {
        item["agreed_with_identification_id"] for item in items if item["agreed_with_identification_id"]
    }
    prediction_ids = {item["agreed_with_prediction_id"] for item in items if item["agreed_with_prediction_id"]}

    agreed_identifications = {}
    if identification_ids:
        agreed_identifications = {
            identification.pk: identification
            for identification in Identification.objects.filter(pk__in=identification_ids)
        }

    agreed_predictions = {}
    if prediction_ids:
        agreed_predictions = {
            classification.pk: classification
            for classification in Classification.objects.filter(pk__in=prediction_ids).select_related("detection")
        }

    return agreed_identifications, agreed_predictions


def _validate_item(
    item: dict,
    occurrences: dict[int, Occurrence],
    taxa: dict[int, Taxon],
    agreed_identifications: dict[int, Identification],
    agreed_predictions: dict[int, Classification],
) -> dict[str, list[str]]:
    """Check one item against the already-fetched batch. Returns field errors, empty when valid."""
    errors: dict[str, list[str]] = {}

    occurrence = occurrences.get(item["occurrence_id"])
    if occurrence is None:
        errors["occurrence_id"] = [f"Occurrence {item['occurrence_id']} does not exist."]

    if item["taxon_id"] not in taxa:
        errors["taxon_id"] = [f"Taxon {item['taxon_id']} does not exist."]

    agreed_identification_id = item["agreed_with_identification_id"]
    if agreed_identification_id:
        agreed = agreed_identifications.get(agreed_identification_id)
        if agreed is None:
            errors["agreed_with_identification_id"] = [f"Identification {agreed_identification_id} does not exist."]
        elif occurrence is not None and agreed.occurrence_id != occurrence.pk:
            errors["agreed_with_identification_id"] = [
                "An identification can only agree with another identification of the same occurrence."
            ]

    agreed_prediction_id = item["agreed_with_prediction_id"]
    if agreed_prediction_id:
        prediction = agreed_predictions.get(agreed_prediction_id)
        if prediction is None:
            errors["agreed_with_prediction_id"] = [f"Classification {agreed_prediction_id} does not exist."]
        elif occurrence is not None and (
            # A classification keeps its row when its detection is deleted, so
            # the link back to an occurrence can be missing entirely.
            prediction.detection is None
            or prediction.detection.occurrence_id != occurrence.pk
        ):
            errors["agreed_with_prediction_id"] = [
                "An identification can only agree with a prediction of the same occurrence."
            ]

    return errors
