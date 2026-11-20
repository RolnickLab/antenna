"""
The SourceImage and SourceImageCollection models, their managers/querysets,
thumbnails, and capture sampling helpers.
"""

from __future__ import annotations

import datetime
import logging
import time
import typing
import urllib.parse
from io import BytesIO
from typing import TYPE_CHECKING, final

import PIL.Image
from django.conf import settings
from django.core.files.storage import default_storage
from django.db import models
from django.db.models.functions import Coalesce
from django.template.defaultfilters import filesizeformat
from django.utils import timezone
from guardian.shortcuts import get_perms
from rest_framework.request import Request

import ami.utils.dates
import ami.utils.s3
from ami.base.fields import DateStringField
from ami.base.models import BaseModel, BaseQuerySet
from ami.main.models_future.filters import build_occurrence_default_filters_q
from ami.main.models_future.occurrences import Occurrence
from ami.main.models_future.projects import Project
from ami.users.models import User
from ami.utils.media import fetch_image_content

if TYPE_CHECKING:
    from ami.jobs.models import Job
    from ami.main.models import Detection

logger = logging.getLogger(__name__)


as_choices = lambda x: [(i, i) for i in x]  # noqa: E731


class SourceImageQuerySet(BaseQuerySet):
    def with_occurrences_count(self, project: Project | None = None, request=None):
        """
        Annotate each source image with the number of occurrences,
        filtered by default filters (score threshold and taxa inclusion/exclusion).

        Note: classification_threshold parameter is deprecated, use project default filters instead.

        Uses a subquery to avoid GROUP BY in the pagination count query, which may
        improve performance for large datasets.
        """
        filter_q = build_occurrence_default_filters_q(project, request, "")

        # Use a subquery instead of Count with joins to avoid GROUP BY in pagination count query
        # The subquery counts distinct occurrences for each source image
        # Use Coalesce to return 0 when the subquery returns NULL (no matching rows)
        # @TODO update the SourceImageCollectionQuerySet to use the same approach
        occurrences_subquery = (
            Occurrence.objects.filter(detections__source_image_id=models.OuterRef("pk"))
            .filter(filter_q)
            .values("detections__source_image_id")  # Group by source_image_id to get one row per source_image
            .annotate(count=models.Count("id", distinct=True))
            .values("count")
        )

        return self.annotate(
            occurrences_count=Coalesce(models.Subquery(occurrences_subquery, output_field=models.IntegerField()), 0)
        )

    def with_taxa_count(self, project: Project | None = None, request=None):
        """
        Annotate each source image with the number of distinct taxa,
        filtered by default filters (score threshold and taxa inclusion/exclusion).

        Note: classification_threshold parameter is deprecated, use project default filters instead.

        Uses a subquery to avoid GROUP BY in the pagination count query, which may
        improve performance for large datasets.
        """
        filter_q = build_occurrence_default_filters_q(project, request, "")

        # Use a subquery instead of Count with joins to avoid GROUP BY in pagination count query
        # The subquery counts distinct taxa for each source image
        # Use Coalesce to return 0 when the subquery returns NULL (no matching rows)
        # @TODO update the SourceImageCollectionQuerySet to use the same approach
        taxa_subquery = (
            Occurrence.objects.filter(detections__source_image_id=models.OuterRef("pk"))
            .filter(filter_q)
            .values("detections__source_image_id")  # Group by source_image_id to get one row per source_image
            .annotate(count=models.Count("determination_id", distinct=True))
            .values("count")
        )

        return self.annotate(
            taxa_count=Coalesce(models.Subquery(taxa_subquery, output_field=models.IntegerField()), 0)
        )

    def with_was_processed(self):
        """
        Annotate each SourceImage with a boolean `was_processed` indicating
        whether any detections exist for that image.

        This mirrors `SourceImage.get_was_processed()` but as a queryset
        annotation for efficient bulk queries.
        """
        # @TODO: this returns a was processed status for any algorithm. One the session detail view supports
        # filtering by algorithm, this should be updated to return was_processed for the selected algorithm.
        from ami.main.models import Detection

        processed_exists = models.Exists(Detection.objects.filter(source_image_id=models.OuterRef("pk")))
        return self.annotate(was_processed=processed_exists)

    def with_thumbnails(self):
        """Prefetch ``thumbnails`` so :meth:`SourceImage.thumbnail_urls` decides
        warm/cold in memory instead of firing a SELECT per row.
        """
        return self.prefetch_related("thumbnails")


class SourceImageManager(models.Manager.from_queryset(SourceImageQuerySet)):
    pass


@final
class SourceImage(BaseModel):
    """A single image captured during a monitoring session"""

    path = models.CharField(max_length=255, blank=True)
    public_base_url = models.CharField(max_length=255, blank=True, null=True)
    timestamp = models.DateTimeField(null=True, blank=True, db_index=True)
    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)
    # File metadata read from the source file in storage, populated by the sync
    # flow and upload handler. Writable in the API for manual SourceImage
    # creation; read-only in the admin.
    size = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Size of the image file in bytes, read from the source file in image storage.",
    )
    last_modified = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the image file was last modified, read from the source file in image storage.",
    )
    checksum = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Checksum of the image file, read from the source file in image storage.",
    )
    checksum_algorithm = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Algorithm used for the checksum (e.g. MD5, SHA256).",
    )
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    test_image = models.BooleanField(default=False)

    # Precaclulated values
    detections_count = models.IntegerField(null=True, blank=True)

    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, related_name="captures")
    deployment = models.ForeignKey("Deployment", on_delete=models.SET_NULL, null=True, related_name="captures")
    event = models.ForeignKey(
        "Event",
        on_delete=models.SET_NULL,
        null=True,
        related_name="captures",
        db_index=True,
        blank=True,
    )

    event_id: int | None
    detections: models.QuerySet[Detection]
    collections: models.QuerySet[SourceImageCollection]
    jobs: models.QuerySet[Job]

    objects = SourceImageManager()

    def __str__(self) -> str:
        return f"{self.__class__.__name__} #{self.pk} {self.path}"

    @staticmethod
    def build_public_url(base_url: str, path: str) -> str:
        """Join a public base URL with a stored object path.

        Shared with callers that have annotated `public_base_url` + `path` onto a
        queryset row and want to skip loading the SourceImage instance.
        """
        return urllib.parse.urljoin(base_url, path.lstrip("/"))

    def public_url(self, raise_errors=False) -> str | None:
        """
        Return the public URL for this image.

        The base URL is determined by the deployment's data source and is cached
        on the source image. If the deployment's data source changes, the URLs
        for all source images will be updated.

        @TODO add support for thumbnail URLs here?
        @TODO consider if we ever need to access the original image directly!
        @TODO every source image request requires joins for the deployment and data source, is this necessary?
        """
        # Get presigned URL if access keys are configured
        data_source = self.deployment.data_source if self.deployment and self.deployment.data_source else None
        if (
            data_source is not None
            and not data_source.public_base_url
            and data_source.access_key
            and data_source.secret_key
        ):
            url = ami.utils.s3.get_presigned_url(data_source.config, key=self.path)
        elif self.public_base_url:
            url = self.build_public_url(self.public_base_url, self.path)
        else:
            msg = f"Public URL for {self} is not available. Public base URL: '{self.public_base_url}'"
            if raise_errors:
                raise ValueError(msg)
            else:
                logger.error(msg)
                return None
        # Ensure url has a scheme
        if not urllib.parse.urlparse(url).netloc:
            msg = f"Public URL for {self} is invalid: {url}. Public base URL: '{self.public_base_url}'"
            if raise_errors:
                raise ValueError(msg)
            else:
                logger.error(msg)
                return None
        else:
            return url

    # backwards compatibility
    url = public_url

    def size_display(self) -> str:
        """
        Return the size of the image in human-readable format.
        """
        if self.size is None:
            return filesizeformat(0)
        else:
            return filesizeformat(self.size)

    def get_detections_count(self) -> int:
        """
        Return detections count filtered by project default filters.

        Excludes detections without bounding boxes — those are placeholder records
        indicating the image was successfully processed and no detections were found.
        """
        qs = self.detections.all().valid()
        project = self.project
        if not project:
            return qs.distinct().count()

        q = build_occurrence_default_filters_q(
            project=project,
            request=None,
            occurrence_accessor="occurrence",
        )
        return qs.filter(q).distinct().count()

    def get_was_processed(self, algorithm_key: str | None = None) -> bool:
        """
        Return True if this image has been processed by any algorithm (or a specific one).

        Uses the ``was_processed`` annotation when available (set by
        ``SourceImageQuerySet.with_was_processed()``). Falls back to a DB query otherwise.

        Do not call in bulk without the annotation — use ``with_was_processed()``
        on the queryset instead so each row does not trigger its own DB query.

        :param algorithm_key: If provided, only detections from this algorithm are checked.
                              The annotation does not filter by algorithm; per-algorithm
                              checks always use a DB query.
        """
        if algorithm_key is None and hasattr(self, "was_processed"):
            return self.was_processed  # type: ignore[return-value]
        if algorithm_key:
            return self.detections.filter(detection_algorithm__key=algorithm_key).exists()
        return self.detections.exists()

    def get_base_url(self) -> str | None:
        """
        Determine the public URL from the deployment's data source.

        If there is no data source, return None

        If the public_base_url is None, a presigned URL will be generated for each request.
        """
        if self.deployment and self.deployment.data_source and self.deployment.data_source.public_base_url:
            return self.deployment.data_source.public_base_url
        else:
            return None

    def extract_timestamp(self) -> datetime.datetime | None:
        """
        Extract a timestamp from the filename or EXIF data
        """
        # @TODO use EXIF data if necessary (use methods in AMI data companion repo)
        timestamp = ami.utils.dates.get_image_timestamp_from_filename(self.path)
        if not timestamp:
            # timestamp = ami.utils.dates.get_image_timestamp_from_exif(self.path)
            msg = f"No timestamp could be extracted from the filename or EXIF data of {self.path}"
            logger.error(msg)
        return timestamp

    def event_next_capture_id(self) -> int | None:
        """
        Return the next capture in the event.

        This should be populated by the query in the ViewSet
        but here is the query for reference:
        return SourceImage.objects.filter(
        event=self.event, timestamp__gt=self.timestamp).order_by("timestamp").values("id").first()
        """
        return None

    def event_prev_capture_id(self) -> int | None:
        """
        Return the previous capture in the event.

        This will be populated by the query in the ViewSet but here is the query for reference:
        return SourceImage.objects.filter(
        event=self.event, timestamp__lt=self.timestamp).order_by("-timestamp").values("id").first()
        """
        return None

    def event_current_capture_index(self) -> int | None:
        """
        Return the index of the current capture in the event.

        This will be populated by the query in the ViewSet but here is the query for reference:
        return SourceImage.objects.filter(
        event=self.event, timestamp__lt=self.timestamp).count()
        or using window functions:
        return SourceImage.objects.filter(
            event=self.event, timestamp__lt=self.timestamp).annotate(
            index=models.Window(
            expression=models.functions.RowNumber(),
            order_by=models.F("timestamp").desc(),
        )
        ).values("index").first()
        """
        return None

    def event_total_captures(self) -> int | None:
        """
        Return the total number of captures in the event.

        This will be populated by the query in the ViewSet but here is the query for reference:
        return SourceImage.objects.filter(event=self.event).count()

        These values are used to help navigate between images in the event.

        @TODO Can we remove these methods? Seems to be a requirement for DRF serializers.
        """
        return None

    def get_dimensions(self) -> tuple[int | None, int | None]:
        """Calculate the width and height of the original image."""
        if self.path and self.deployment and self.deployment.data_source:
            config = self.deployment.data_source.config
            try:
                img = ami.utils.s3.read_image(config=config, key=self.path)
            except Exception as e:
                logger.error(f"Could not determine image dimensions for {self.path}: {e}")
            else:
                self.width, self.height = img.size
                self.save()
                return self.width, self.height
        return None, None

    def occurrences_count(self) -> int | None:
        # This should always be pre-populated using queryset annotations
        return None

    def taxa_count(self) -> int | None:
        # This should always be pre-populated using queryset annotations
        return None

    def update_calculated_fields(self, save=False):
        if self.path and not self.timestamp:
            self.timestamp = self.extract_timestamp()
        if self.path and not self.public_base_url:
            self.public_base_url = self.get_base_url()
        if not self.project and self.deployment:
            self.project = self.deployment.project
        if self.pk is not None:
            self.detections_count = self.get_detections_count()
        if save:
            self.save(update_calculated_fields=False)

    def save(self, update_calculated_fields=True, *args, **kwargs):
        super().save(*args, **kwargs)
        if update_calculated_fields:
            self.update_calculated_fields(save=True)

    def check_custom_permission(self, user, action: str) -> bool:
        project = self.get_project() if hasattr(self, "get_project") else None
        if action in ["star", "unstar"]:
            return user.has_perm(Project.Permissions.STAR_SOURCE_IMAGE, project)

    def get_custom_user_permissions(self, user) -> list[str]:
        project = self.get_project()
        if not project:
            return []

        custom_perms = set()
        perms = get_perms(user, project)
        for perm in perms:
            # permissions are in the format "action_modelname"
            if perm.endswith("_sourceimage"):
                # process_single_image_sourceimage
                action = perm.split("_", 1)[0]
                # make sure to exclude standard CRUD actions
                if action not in ["view", "create", "update", "delete"]:
                    custom_perms.add(action)
        if Project.Permissions.RUN_SINGLE_IMAGE_JOB in perms:
            custom_perms.add(Project.Permissions.RUN_SINGLE_IMAGE_JOB)
        return list(custom_perms)

    def thumbnail_is_valid(self, spec: dict, thumb: SourceImageThumbnail | None) -> bool:
        """Whether ``thumb`` satisfies ``spec`` and need not be regenerated.

        ``thumb.width`` stores the requested spec width (see the generator), so the
        comparison is strict equality; legacy encoder-width rows read invalid and
        self-heal on next generation. A None ``last_modified`` on either side means
        "no signal of change" (matches ``NULL < x`` → ``False`` in SQL).
        """
        if thumb is None or not thumb.path or thumb.width != spec["width"]:
            return False
        source_changed = (
            self.last_modified is not None
            and thumb.last_modified is not None
            and thumb.last_modified < self.last_modified
        )
        return not source_changed

    def thumbnail_urls(self, request: Request | None = None) -> dict[str, str]:
        """Per-label ``{label: url}`` for this capture's thumbnails.

        Warm (cached row valid for the spec) → direct storage URL. Cold/stale →
        route URL into the thumbnail viewset, which (re)generates lazily.

        The warm path needs prefetched ``thumbnails``
        (:meth:`SourceImageQuerySet.with_thumbnails`). Without the prefetch — a
        freshly created instance in a write response, or a caller that skipped
        ``with_thumbnails`` — every label falls back to the route URL without
        querying. This never lazily loads per object (which would be an N+1 in
        list contexts); list endpoints must apply ``with_thumbnails`` to get the
        warm storage URLs, and the list query-count tests pin that.
        """
        # Local import avoids a models ↔ serializers cycle at module load time.
        from ami.base.serializers import reverse_with_params

        prefetched = "thumbnails" in getattr(self, "_prefetched_objects_cache", {})
        thumbs: dict[str, SourceImageThumbnail] = {t.label: t for t in self.thumbnails.all()} if prefetched else {}

        out: dict[str, str] = {}
        for label, spec in settings.THUMBNAILS["SIZES"].items():
            thumb = thumbs.get(label)
            if self.thumbnail_is_valid(spec, thumb):
                out[label] = default_storage.url(thumb.path)
            else:
                # Qualified ``api:`` namespace so this also resolves when ``request``
                # is None (management commands, template tags).
                out[label] = reverse_with_params(
                    "api:sourceimagethumbnail-detail",
                    args=(self.pk,),
                    request=request,
                    params={"label": label},
                )
        return out

    def find_or_generate_thumbnail_for_label(self, label):
        try:
            thumb = self.thumbnails.get(label=label)
        except SourceImageThumbnail.DoesNotExist:
            thumb = None
        size = settings.THUMBNAILS["SIZES"].get(label)
        prefix = settings.THUMBNAILS["STORAGE_PREFIX"]

        # The row is trusted without a storage existence check; an orphan row (blob
        # deleted out of band) shows a broken image until the row is removed.
        if not self.thumbnail_is_valid(size, thumb):
            img = PIL.Image.open(BytesIO(fetch_image_content(self.public_url(raise_errors=True))))
            # JPEG only supports L, RGB, CMYK — convert other modes (e.g. RGBA PNGs)
            # or PIL raises ``OSError: cannot write mode <X> as JPEG``.
            if img.mode not in ("L", "RGB", "CMYK"):
                img = img.convert("RGB")
            # Make the thumbnail
            orig_width, orig_height = img.size
            width = size["width"]
            height = size.get("height", None)
            if not height:
                height = int(orig_height * (width / float(orig_width)))
            new_size = (width, height)
            img.thumbnail(new_size)

            buffer = BytesIO()
            # No ``exif=`` argument: detection boxes are overlaid on thumbnails in raw
            # pixel coordinates, so the EXIF Orientation tag must not propagate.
            img.save(buffer, format="JPEG", progressive=True, optimize=True, quality=82)
            contents = buffer.getvalue()
            file_size = len(contents)

            # Snapshot the prior blob path before the upsert, for cleanup below.
            prior_path = self.thumbnails.filter(label=label).values_list("path", flat=True).first()

            # Storage backends may overwrite the key in place or suffix on collision —
            # record whichever path the backend returns.
            buffer.seek(0)
            thumbnail_key = f"{prefix}capture_{self.pk}/{label}.jpg"
            thumbnail_path = default_storage.save(thumbnail_key, buffer)

            # Atomic upsert: concurrent generation races on the (source_image, label)
            # unique constraint. ``width`` stores the requested spec width, not the
            # encoder output — PIL's rounding (e.g. 239 for a 240 spec) would otherwise
            # fail the strict regen gate above on every request. ``height`` is informational.
            thumb, _created = self.thumbnails.update_or_create(
                label=label,
                defaults={
                    "path": thumbnail_path,
                    "width": size["width"],
                    "height": img.size[1],
                    "size": file_size,
                },
            )
            # ``last_modified`` is ``auto_now_add`` (set on INSERT only) — force-bump it
            # on UPDATE or the freshness check re-triggers regen on every request.
            if not _created:
                type(thumb).objects.filter(pk=thumb.pk).update(last_modified=timezone.now())
                thumb.refresh_from_db(fields=["last_modified"])

            # Best-effort cleanup of the replaced blob; failure must not break the response.
            if prior_path and prior_path != thumbnail_path:
                try:
                    default_storage.delete(prior_path)
                except Exception as e:
                    logger.warning(f"Could not delete prior thumbnail blob at {prior_path}: {e}")
        return thumb

    class Meta:
        ordering = ("deployment", "event", "timestamp")

        # Add two "unique together" constraints to prevent duplicate images
        constraints = [
            # deployment + path (only one image per deployment with a given file path)
            models.UniqueConstraint(fields=["deployment", "path"], name="unique_deployment_path"),
        ]

        indexes = [
            models.Index(fields=["deployment", "timestamp"]),
            models.Index(fields=["event", "timestamp"]),
            models.Index(fields=["timestamp"]),
            # Backs the project "recent captures" sort: a per-project max(timestamp)
            # lookup (see ProjectViewSet ordering "last_capture_timestamp").
            models.Index(fields=["project", "-timestamp"], name="main_source_proj_ts_desc_idx"),
        ]


def update_detection_counts(
    qs: models.QuerySet[SourceImage] | None = None,
    null_only=False,
    project: Project | None = None,
) -> int:
    """
    Update the detection count for all source images using a bulk update query.

    When ``project`` is provided, the count is filtered by that project's default
    filters so the cached ``SourceImage.detections_count`` stays consistent with
    ``SourceImage.get_detections_count()``.

    @TODO Needs testing.
    """
    from ami.main.models import Detection

    qs = qs or SourceImage.objects.all()
    if null_only:
        qs = qs.filter(detections_count__isnull=True)

    detection_qs = Detection.objects.filter(source_image_id=models.OuterRef("pk")).valid()
    if project is not None:
        filter_q = build_occurrence_default_filters_q(
            project=project,
            request=None,
            occurrence_accessor="occurrence",
        )
        detection_qs = detection_qs.filter(filter_q)
    subquery = models.Subquery(
        detection_qs.values("source_image_id").annotate(count=models.Count("id")).values("count"),
        output_field=models.IntegerField(),
    )
    start_time = time.time()
    # Use Coalesce to default to 0 instead of NULL
    num_updated = qs.update(detections_count=models.functions.Coalesce(subquery, models.Value(0)))
    end_time = time.time()
    elapsed_time = end_time - start_time
    logger.info(f"Updated detection counts for {num_updated} source images in {elapsed_time:.2f} seconds")
    return num_updated


def sample_captures_by_interval(
    minute_interval: int,
    qs: models.QuerySet[SourceImage],
    max_num: int | None = None,
) -> typing.Generator[SourceImage, None, None]:
    """
    Return a sample of captures from the deployment, evenly spaced apart by minute_interval.
    """

    last_capture = None
    total = 0

    qs = qs.exclude(timestamp=None).order_by("timestamp")

    for capture in qs.all():
        if max_num and total >= max_num:
            break
        if not last_capture:
            total += 1
            yield capture
            last_capture = capture
        else:
            assert capture.timestamp and last_capture.timestamp
            delta: datetime.timedelta = capture.timestamp - last_capture.timestamp
            if delta.total_seconds() >= minute_interval * 60:
                total += 1
                yield capture
                last_capture = capture


def sample_captures_by_position(
    position: int,
    qs: models.QuerySet[SourceImage],
) -> typing.Generator[SourceImage | None, None, None]:
    """
    Return the n-th position capture from each event.

    For example if position = 0, the first capture from each event will be returned.
    If position = -1, the last capture from each event will be returned.
    """

    from ami.main.models import Event

    qs = qs.exclude(timestamp=None).order_by("timestamp")

    events = Event.objects.filter(captures__in=qs).distinct()
    for event in events:
        qs = qs.filter(event=event)
        if position < 0:
            # Negative positions are relative to the end of the queryset
            # e.g. -1 is the last item, -2 is the second last item, etc.
            # but querysets do not support negative indexing, so we
            # sort the queryset in reverse order and then use positive indexing.
            # e.g. -1 becomes 0, -2 becomes 1, etc.
            position = abs(position) - 1
            qs = qs.order_by("-timestamp")
        else:
            qs = qs.order_by("timestamp")
        try:
            capture = qs[position]
        except IndexError:
            # If the position is out of range, just return the last capture
            capture = qs.last()

        yield capture


def sample_captures_by_nth(
    nth: int,
    qs: models.QuerySet[SourceImage],
) -> typing.Generator[SourceImage, None, None]:
    """
    Return every nth capture from each event.

    For example if nth = 1, every capture from each event will be returned.
    If nth = 5, every 5th capture from each event will be returned.
    """

    from ami.main.models import Event

    qs = qs.exclude(timestamp=None).order_by("timestamp")

    events = Event.objects.filter(captures__in=qs).distinct()
    for event in events:
        qs = qs.filter(event=event).order_by("timestamp")
        yield from qs[::nth]


@final
class SourceImageThumbnail(BaseModel):
    """A thumbnail cache of a SourceImage"""

    path = models.CharField(max_length=255, blank=True)
    label = models.CharField(max_length=255)
    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)
    size = models.BigIntegerField(null=True, blank=True)
    last_modified = models.DateTimeField(null=True, blank=True, auto_now_add=True)

    # CASCADE: thumbnails are pure derivatives of their source. SET_NULL leaves
    # orphan rows + dangling storage blobs forever and nothing else reaps them.
    # The pre_delete signal in ``ami.main.signals`` cleans the storage blob.
    source_image = models.ForeignKey(SourceImage, on_delete=models.CASCADE, related_name="thumbnails")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source_image", "label"],
                name="unique_source_image_thumbnail_label",
            ),
        ]
        indexes = [
            models.Index(fields=["source_image", "label"]),
        ]


_SOURCE_IMAGE_SAMPLING_METHODS = [
    "full",
    "random",
    "stratified_random",
    "interval",
    "manual",
    "starred",
    "random_from_each_event",
    "last_and_random_from_each_event",
    "greatest_file_size_from_each_event",
    "detections_only",
    "common_combined",  # Deprecated
]


class SourceImageCollectionQuerySet(BaseQuerySet):
    def with_source_images_count(self):
        return self.annotate(
            source_images_count=models.Count(
                "images",
                distinct=True,
            )
        )

    def with_source_images_with_detections_count(self):
        from ami.main.models import null_detections_q

        return self.annotate(
            source_images_with_detections_count=models.Count(
                "images",
                filter=~null_detections_q("images__detections__"),
                distinct=True,
            )
        )

    def with_source_images_processed_count(self):
        return self.annotate(
            source_images_processed_count=models.Count(
                "images",
                filter=models.Q(images__detections__isnull=False),
                distinct=True,
            )
        )

    def with_source_images_processed_by_algorithm_count(self, algorithm_id: int):
        return self.annotate(
            source_images_processed_by_algorithm_count=models.Count(
                "images",
                filter=models.Q(images__detections__classifications__algorithm_id=algorithm_id),
                distinct=True,
            )
        )

    def with_occurrences_count(
        self, classification_threshold: float = 0, project: Project | None = None, request=None
    ):
        """
        Annotate each collection with the number of occurrences,
        filtered by default filters (score threshold and taxa inclusion/exclusion).

        Note: classification_threshold parameter is deprecated, use project default filters instead.
        """
        filter_q = build_occurrence_default_filters_q(project, request, "images__detections__occurrence")
        return self.annotate(
            occurrences_count=models.Count(
                "images__detections__occurrence",
                filter=filter_q,
                distinct=True,
            )
        )

    def with_taxa_count(self, classification_threshold: float = 0, project: Project | None = None, request=None):
        """
        Annotate each collection with the number of distinct taxa,
        filtered by default filters (score threshold and taxa inclusion/exclusion).

        Note: classification_threshold parameter is deprecated, use project default filters instead.
        """
        filter_q = build_occurrence_default_filters_q(project, request, "images__detections__occurrence")
        return self.annotate(
            taxa_count=models.Count(
                "images__detections__occurrence__determination",
                filter=filter_q,
                distinct=True,
            )
        )


class SourceImageCollectionManager(models.Manager):
    def get_queryset(self) -> SourceImageCollectionQuerySet:
        return SourceImageCollectionQuerySet(self.model, using=self._db)


@final
class SourceImageCollection(BaseModel):
    """
    A subset of source images for review, processing, etc.

    Examples:
        - Random subset
        - Stratified random sample from all deployments
        - Images sampled based on a time interval (every 30 minutes)


    Collections are saved so that they can be reviewed or re-used later.

    """

    reference_type = "capture_set"
    reference_name_field = "name"

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    # dataset_type = models.CharField(
    #     max_length=255,
    #     choices=as_choices(["Curated", "Dynamic", "Sampling"]),
    # )
    images = models.ManyToManyField("SourceImage", related_name="collections", blank=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="sourceimage_collections")
    method = models.CharField(
        max_length=255,
        choices=as_choices(_SOURCE_IMAGE_SAMPLING_METHODS),
        default="full",
    )
    # @TODO this should be a JSON field with a schema, use a pydantic model
    kwargs = models.JSONField(
        "Arguments",
        null=True,
        blank=True,
        help_text="Arguments passed to the sampling function (JSON dict)",
        default=dict,
    )

    objects = SourceImageCollectionManager()

    jobs: models.QuerySet[Job]

    def infer_dataset_type(self):
        if "starred" in self.name.lower():
            return "curated"
        else:
            return "sampling"

    @property
    def dataset_type(self):
        return self.infer_dataset_type()

    def source_images_count(self) -> int | None:
        # This should always be pre-populated using queryset annotations
        # return self.images.count()
        return None

    def source_images_with_detections_count(self) -> int | None:
        # This should always be pre-populated using queryset annotations
        return None

    def source_images_processed_count(self) -> int | None:
        # This should always be pre-populated using queryset annotations
        return None

    def occurrences_count(self) -> int | None:
        # This should always be pre-populated using queryset annotations
        return None

    def taxa_count(self) -> int | None:
        # This should always be pre-populated using queryset annotations
        return None

    def get_queryset(
        self,
        *args,
        **kwargs,
    ):
        return SourceImage.objects.filter(project=self.project)

    @classmethod
    def sampling_methods(cls):
        return [method for method in dir(cls) if method.startswith("sample_")]

    def populate_sample(self, job: Job | None = None):
        """Create a sample of source images based on the method and kwargs"""
        kwargs = self.kwargs or {}

        if job:
            task_logger = job.logger
        else:
            task_logger = logger

        method_name = f"sample_{self.method}"
        if not hasattr(self, method_name):
            raise ValueError(f"Invalid sampling method: {self.method}. Choices are: {_SOURCE_IMAGE_SAMPLING_METHODS}")
        else:
            task_logger.info(f"Sampling using method '{method_name}' with params: {kwargs}")
            method = getattr(self, method_name)
            task_logger.info(f"Sampling and saving captures to {self}")
            self.images.set(method(**kwargs))
            self.save()
            task_logger.info(f"Done sampling and saving captures to {self}")

    def _filter_sample(
        self,
        qs: models.QuerySet,
        hour_start: int | None = None,
        hour_end: int | None = None,
        month_start: int | None = None,
        month_end: int | None = None,
        date_start: str | None = None,
        date_end: str | None = None,
        deployment_ids: list[int] | None = None,
        research_site_ids: list[int] | None = None,
        event_ids: list[int] | None = None,
    ):
        if deployment_ids is not None:
            qs = qs.filter(deployment__in=deployment_ids)
        if research_site_ids is not None:
            qs = qs.filter(deployment__research_site__in=research_site_ids)
        if event_ids is not None:
            qs = qs.filter(event__in=event_ids)
        if date_start is not None:
            qs = qs.filter(timestamp__date__gte=DateStringField.to_date(date_start))
        if date_end is not None:
            qs = qs.filter(timestamp__date__lte=DateStringField.to_date(date_end))

        if month_start is not None:
            qs = qs.filter(timestamp__month__gte=month_start)
        if month_end is not None:
            qs = qs.filter(timestamp__month__lte=month_end)

        if hour_start is not None and hour_end is not None:
            if hour_start < hour_end:
                # Hour range within the same day (e.g., 08:00 to 15:00)
                qs = qs.filter(timestamp__hour__gte=hour_start, timestamp__hour__lte=hour_end)
            else:
                # Hour range has Midnight crossover: (e.g., 17:00 to 06:00)
                qs = qs.filter(models.Q(timestamp__hour__gte=hour_start) | models.Q(timestamp__hour__lte=hour_end))
        elif hour_start is not None:
            qs = qs.filter(timestamp__hour__gte=hour_start)
        elif hour_end is not None:
            qs = qs.filter(timestamp__hour__lte=hour_end)

        return qs

    def sample_random(
        self,
        size: int = 100,
        hour_start: int | None = None,
        hour_end: int | None = None,
        month_start: int | None = None,
        month_end: int | None = None,
        date_start: str | None = None,
        date_end: str | None = None,
        deployment_ids: list[int] | None = None,
        research_site_ids: list[int] | None = None,
        event_ids: list[int] | None = None,
    ):
        """Create a random sample of source images"""

        qs = self.get_queryset()
        qs = self._filter_sample(
            qs=qs,
            hour_start=hour_start,
            hour_end=hour_end,
            month_start=month_start,
            month_end=month_end,
            date_start=date_start,
            date_end=date_end,
            deployment_ids=deployment_ids,
            research_site_ids=research_site_ids,
            event_ids=event_ids,
        )
        return qs.order_by("?")[:size]

    def sample_manual(self, image_ids: list[int]):
        """Create a sample of source images based on a list of source image IDs"""

        qs = self.get_queryset()
        return qs.filter(id__in=image_ids)

    # Deprecated
    def sample_common_combined(
        self,
        minute_interval: int | None = None,
        max_num: int | None = None,
        shuffle: bool = True,  # This is applicable if max_num is set and minute_interval is not set
        hour_start: int | None = None,
        hour_end: int | None = None,
        month_start: int | None = None,
        month_end: int | None = None,
        date_start: str | None = None,
        date_end: str | None = None,
        deployment_ids: list[int] | None = None,
        research_site_ids: list[int] | None = None,
        event_ids: list[int] | None = None,
    ) -> models.QuerySet | typing.Generator[SourceImage, None, None]:
        qs = self.get_queryset()
        qs = self._filter_sample(
            qs=qs,
            hour_start=hour_start,
            hour_end=hour_end,
            month_start=month_start,
            month_end=month_end,
            date_start=date_start,
            date_end=date_end,
            deployment_ids=deployment_ids,
            research_site_ids=research_site_ids,
            event_ids=event_ids,
        )

        if minute_interval is not None:
            # @TODO can this be done in the database and return a queryset?
            # this currently returns a list of source images
            # Ensure the queryset is limited to the project
            qs = qs.filter(project=self.project)
            qs = sample_captures_by_interval(minute_interval=minute_interval, qs=qs, max_num=max_num)
        else:
            if max_num is not None:
                if shuffle:
                    qs = qs.order_by("?")
                qs = qs[:max_num]

        return qs

    def sample_interval(
        self,
        minute_interval: int = 10,
        exclude_events: list[int] = [],
        deployment_id: int | None = None,  # Deprecated
        hour_start: int | None = None,
        hour_end: int | None = None,
        month_start: int | None = None,
        month_end: int | None = None,
        date_start: str | None = None,
        date_end: str | None = None,
        deployment_ids: list[int] | None = None,
        research_site_ids: list[int] | None = None,
        event_ids: list[int] | None = None,
    ):
        """Create a sample of source images based on a time interval"""

        qs = self.get_queryset()
        qs = self._filter_sample(
            qs=qs,
            hour_start=hour_start,
            hour_end=hour_end,
            month_start=month_start,
            month_end=month_end,
            date_start=date_start,
            date_end=date_end,
            deployment_ids=deployment_ids,
            research_site_ids=research_site_ids,
            event_ids=event_ids,
        )
        if deployment_id:
            qs = qs.filter(deployment=deployment_id)
        qs = qs.exclude(event__in=exclude_events)
        # Limit to project
        qs = qs.filter(project=self.project)

        # Sample per-deployment so the minute interval applies independently per station.
        # If specific deployment ids are provided, use them; otherwise iterate over all deployments
        # in the project and sample each separately.
        if deployment_ids is not None:
            deps = deployment_ids
        elif deployment_id is not None:
            deps = [deployment_id]
        else:
            deps = list(self.project.deployments.values_list("id", flat=True))

        captures: set[SourceImage] = set()
        for dep in deps:
            dep_qs = qs.filter(deployment=dep)
            for c in sample_captures_by_interval(minute_interval=minute_interval, qs=dep_qs):
                captures.add(c)

        # Return results in a deterministic order. Sort by timestamp (oldest first),
        # then by primary key to stabilize ordering when timestamps are equal.
        captures_list = sorted(captures, key=lambda s: (s.timestamp is None, s.timestamp, s.pk))
        return captures_list

    def sample_positional(self, position: int = -1):
        """Sample the single nth source image from all events in the project"""

        qs = self.get_queryset()
        return sample_captures_by_position(position=position, qs=qs)

    def sample_nth(self, nth: int):
        """Sample every nth source image from all events in the project"""

        qs = self.get_queryset()
        return sample_captures_by_nth(nth=nth, qs=qs)

    def sample_random_from_each_event(self, num_each: int = 10):
        """Sample n random source images from each event in the project."""

        qs = self.get_queryset()
        captures = set()
        for event in self.project.events.all():
            captures.update(qs.filter(event=event).order_by("?")[:num_each])
        return captures

    def sample_last_and_random_from_each_event(self, num_each: int = 1):
        """Sample the last image from each event and n random from each event."""

        qs = self.get_queryset()
        captures = set()
        for event in self.project.events.all():
            last_capture = qs.filter(event=event).order_by("timestamp").last()
            if not last_capture:
                # This event has no captures
                continue
            captures.add(last_capture)
            random_captures = qs.filter(event=event).exclude(pk=last_capture.pk).order_by("?")[:num_each]
            captures.update(random_captures)
        return captures

    def sample_greatest_file_size_from_each_event(self, num_each: int = 1):
        """Sample the image with the greatest file size from each event."""

        qs = self.get_queryset()
        captures = set()
        for event in self.project.events.all():
            captures.update(qs.filter(event=event).order_by("-size")[:num_each])
        return captures

    def sample_detections_only(self):
        """Sample all source images with at least one real (non-null-marker) detection."""

        from ami.main.models import Detection

        qs = self.get_queryset()
        valid_detection_image_ids = Detection.objects.valid().values("source_image_id")
        return qs.filter(pk__in=valid_detection_image_ids).distinct()

    def sample_full(
        self,
        hour_start: int | None = None,
        hour_end: int | None = None,
        month_start: int | None = None,
        month_end: int | None = None,
        date_start: str | None = None,
        date_end: str | None = None,
        deployment_ids: list[int] | None = None,
        research_site_ids: list[int] | None = None,
        event_ids: list[int] | None = None,
    ):
        """Sample all source images"""

        qs = self.get_queryset()
        qs = self._filter_sample(
            qs=qs,
            hour_start=hour_start,
            hour_end=hour_end,
            month_start=month_start,
            month_end=month_end,
            date_start=date_start,
            date_end=date_end,
            deployment_ids=deployment_ids,
            research_site_ids=research_site_ids,
            event_ids=event_ids,
        )
        return qs.all().distinct()

    @classmethod
    def get_or_create_starred_collection(cls, project: Project) -> SourceImageCollection:
        """
        Get or create a collection for starred images.
        """
        collection = (
            SourceImageCollection.objects.filter(
                project=project,
                method="starred",
            )
            .order_by("created_at")
            .first()
        )  # Use the oldest match
        if not collection:
            collection = SourceImageCollection.objects.create(
                project=project,
                method="starred",
                name="Starred Images",  # @TODO make this translatable
            )
        return collection
