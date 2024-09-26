import datetime
import logging
import typing

from django.db import models
from django.utils import timezone

import ami.tasks


class BaseModel(models.Model):
    """ """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        """All django models should have this method."""
        if hasattr(self, "name"):
            name = getattr(self, "name") or "Untitled"
            return f"#{self.pk} {name}"
        else:
            return f"{self.__class__.__name__} #{self.pk}"

    def save_async(self, *args, **kwargs):
        """Save the model in a background task."""
        ami.tasks.model_task.delay(self.__class__.__name__, self.pk, "save", *args, **kwargs)

    def update_calculated_fields(self, *args, **kwargs):
        """Update calculated fields specific to each model."""
        pass

    class Meta:
        abstract = True


def update_calculated_fields_in_bulk(
    qs: models.QuerySet[BaseModel] | None = None,
    Model: type[models.Model] | None = None,
    pks: list[typing.Any] | None = None,
    fields: list[str] = [],
    last_updated: datetime.datetime | None = None,
    save=True,
) -> int:
    """
    This function is called by a migration to update the calculated fields for all instances of a model.
    """
    to_update: typing.Iterable[BaseModel] = []

    if qs:
        Model = qs.model
    assert Model is not None, "Either a queryset or model must be specified"

    # Ensure the model as a method to update calculated fields
    assert hasattr(Model, "update_calculated_fields"), f"{Model} has no method 'update_calculated_fields'"

    qs = qs or Model.objects.all()  # type: ignore
    assert qs is not None

    if pks:
        qs = qs.filter(pk__in=pks)
    if last_updated:
        # query for None or before the last updated time
        qs = qs.filter(
            models.Q(calculated_fields_updated_at__isnull=True)
            | models.Q(calculated_fields_updated_at__lte=last_updated)
        )

    logging.info(f"Updating pre-calculated fields for {len(to_update)} events")

    # Shared the updated timestamp for all instances in a bulk update
    updated_timestamp = timezone.now()
    for instance in qs:
        instance.update_calculated_fields(save=False, updated_timestamp=updated_timestamp)
        to_update.append(instance)

    if save:
        logging.info(f"Saving {len(to_update)} instances, only updating {len(fields)} fields: {fields}")
        updated_count = Model.objects.bulk_update(
            to_update,
            fields,
        )
        if updated_count != len(to_update):
            logging.error(f"Failed to update {len(to_update) - updated_count} events")

    return updated_count
