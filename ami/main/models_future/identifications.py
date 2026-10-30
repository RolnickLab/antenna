"""
The Identification model and any managers/querysets associated with it.

Models are declared here but remain in the ``main`` app. Related models are
referenced by string label, or imported inside the method that needs them, so
this module never imports ``ami.main.models`` at import time — ``main.models``
imports this one.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, final

from django.conf import settings
from django.contrib.auth.models import AbstractUser, AnonymousUser
from django.core import exceptions
from django.db import IntegrityError, models, transaction

from ami.base.models import BaseModel

if TYPE_CHECKING:
    from ami.main.models import Classification, Occurrence, Taxon

logger = logging.getLogger(__name__)


@final
class Identification(BaseModel):
    """A classification of an occurrence by a human."""

    project_accessor = "occurrence__project"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="identifications",
    )
    taxon = models.ForeignKey(
        "Taxon",
        on_delete=models.SET_NULL,
        null=True,
        related_name="identifications",
    )
    occurrence = models.ForeignKey(
        "Occurrence",
        on_delete=models.CASCADE,
        related_name="identifications",
    )
    withdrawn = models.BooleanField(default=False)
    agreed_with_identification = models.ForeignKey(
        "Identification",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agreed_identifications",
    )
    agreed_with_prediction = models.ForeignKey(
        "Classification",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agreed_identifications",
    )
    score = 1.0  # Always 1 for humans, at this time
    comment = models.TextField(blank=True)

    class Meta:
        ordering = [
            "-created_at",
        ]

    def save(self, *args, **kwargs):
        """
        If this is a new identification:
        - Set previous identifications by this user to withdrawn
        - Set the determination of the occurrence to the taxon of this identification if it is primary

        # @TODO Add tests
        """
        from ami.main.models import update_occurrence_determination

        if not self.pk and not self.withdrawn and self.user:
            # This is a new identification and it has not been explicitly withdrawn
            # so set all other identifications of this user to withdrawn.
            Identification.objects.filter(
                occurrence=self.occurrence,
                user=self.user,
            ).exclude(
                pk=self.pk
            ).update(withdrawn=True)

        super().save(*args, **kwargs)

        update_occurrence_determination(self.occurrence)

    def delete(self, *args, **kwargs):
        """
        If this is the current identification for the occurrence, set the determination to the next best ID.
        and un-withdraw the previous ID by the same user.

        @TODO Add tests
        """
        from ami.main.models import update_occurrence_determination

        current_best: Identification | None = self.occurrence.best_identification
        if current_best and current_best == self:
            # Invalidate the cached property so it will be re-calculated
            del self.occurrence.best_identification
            if self.user:
                previous_id = (
                    Identification.objects.filter(
                        occurrence=self.occurrence,
                        user=self.user,
                        withdrawn=True,
                    )
                    .exclude(pk=self.pk)
                    # The "next best" ID by the same user is just the most recent one.
                    # but this could be more complex in the future.
                    .order_by("-created_at")
                    .first()
                )
                if previous_id:
                    previous_id.withdrawn = False
                    previous_id.save()

        super().delete(*args, **kwargs)

        # Allow the update_occurrence_determination to determine the next best ID
        update_occurrence_determination(self.occurrence, current_determination=self.taxon)

    def check_permission(self, user: AbstractUser | AnonymousUser, action: str) -> bool:
        """
        Custom permission check logic for Identification model.

        The "create" branch depends only on the occurrence's project. The bulk
        endpoint relies on that to check once per batch instead of once per
        occurrence — revisit it if this path gains per-occurrence logic. See #1371.
        """
        import ami.users.roles as roles

        project = self.get_project()
        if not project:
            return False

        if action == "destroy":
            # Allow if user is superuser, project manager, or owner of the identification
            return user.is_superuser or roles.ProjectManager.has_role(user, project) or self.user == user

        # Fallback to base class permission checks
        return super().check_permission(user, action)


def resolve_occurrences(items: list[dict]) -> dict[int, Occurrence]:
    """Fetch every occurrence in the batch in one query, with its project loaded."""
    # We need to do a function level import here to avoid a circular import,
    # since ami.main.models imports this module.
    from ami.main.models import Occurrence

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
    # Resolves every row a batch references in a fixed number of queries, validates
    # each item against the resolved batch, then saves each item inside its own
    # savepoint so one bad item does not abort the rest. See #1371.
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
    # We need to do a function level import here to avoid a circular import,
    # since ami.main.models imports this module.
    from ami.main.models import Taxon

    taxon_ids = {item["taxon_id"] for item in items}
    return {taxon.pk: taxon for taxon in Taxon.objects.filter(pk__in=taxon_ids)}


def _resolve_agreement_targets(
    items: list[dict],
) -> tuple[dict[int, Identification], dict[int, Classification]]:
    """Fetch the identifications and predictions that items claim to agree with."""
    # We need to do a function level import here to avoid a circular import,
    # since ami.main.models imports this module.
    from ami.main.models import Classification

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
