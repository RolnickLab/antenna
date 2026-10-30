"""Snapshots of the verified training data of every project that opted in to share it.

A snapshot is a set of Parquet files in storage, written by ``ami.ml.training.export``. These
rows record what each snapshot holds and where its files are.
"""

import typing

from django.db import models

from ami.base.models import BaseModel


class TrainingDataSnapshotStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"


@typing.final
class TrainingDataSnapshot(BaseModel):
    """One export of the verified species detections of all opted-in projects.

    It belongs to no project, so only superusers can manage it.
    """

    status = models.CharField(
        max_length=32, choices=TrainingDataSnapshotStatus.choices, default=TrainingDataSnapshotStatus.PENDING
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)
    triggered_by = models.ForeignKey(
        "users.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="training_data_snapshots"
    )

    storage_prefix = models.CharField(max_length=255, blank=True)
    files = models.JSONField(default=dict, blank=True, help_text="Storage path of each file, by its name.")
    file_size = models.PositiveBigIntegerField(default=0, help_text="Total size of the files, in bytes.")
    # When the files were deleted to keep storage bounded. The counts stay.
    pruned_at = models.DateTimeField(null=True, blank=True)

    rows = models.PositiveIntegerField(default=0, help_text="Detections in the manifest.")
    occurrences = models.PositiveIntegerField(default=0)
    taxa = models.PositiveIntegerField(default=0)
    algorithms = models.ManyToManyField(
        "ml.Algorithm",
        blank=True,
        related_name="training_data_snapshots",
        help_text="Algorithms whose feature vectors were exported, one file each.",
    )
    rules = models.JSONField(default=dict, blank=True, help_text="How rows were selected and split.")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Training data snapshot #{self.pk} ({self.status}, {self.rows} rows)"


@typing.final
class TrainingDataSnapshotProject(models.Model):
    """What one project contributed to one snapshot."""

    snapshot = models.ForeignKey(TrainingDataSnapshot, on_delete=models.CASCADE, related_name="project_counts")
    # Kept when the project is deleted, so the snapshot still says what it held.
    project = models.ForeignKey(
        "main.Project", on_delete=models.SET_NULL, null=True, related_name="training_data_snapshot_counts"
    )
    project_name = models.CharField(max_length=255)
    rows = models.PositiveIntegerField(default=0)
    occurrences = models.PositiveIntegerField(default=0)
    taxa = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["snapshot", "project"], name="unique_training_data_snapshot_project"),
        ]

    def __str__(self) -> str:
        return f"{self.project_name} in snapshot #{self.snapshot_id}: {self.rows} rows"
