from __future__ import annotations

import dataclasses
import enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ami.main.models import Classification, TaxaList, Taxon
    from ami.ml.models import Pipeline

import typing

from django.contrib.postgres.fields import ArrayField
from django.db import models, transaction
from django.utils.text import slugify

from ami.base.models import BaseModel, BaseQuerySet


@dataclasses.dataclass
class TaxaListSyncResult:
    """
    What happened the last time ``Algorithm.sync_taxa_list()`` ran.

    ``taxa_list`` is ``None`` only when the algorithm has no category map or the map has
    no labels — the one case where nothing is written. ``unresolved`` holds the labels
    that matched no taxon and were left out of the list, so a caller can report or fix
    them; it is only non-empty when ``create_missing_taxa`` is False.
    """

    taxa_list: TaxaList | None
    created_list: bool
    labels: int
    matched: int
    created_taxa: int
    removed: int
    unresolved: list[str]


@typing.final
class AlgorithmCategoryMap(BaseModel):
    """
    A list of classification labels for a given algorithm version

    Expected schema for `data` field. This is the primary "category map" used by the model
    to map from the category index in the model output to a human-readable label and other metadata.

    IMPORTANT: Currently only `label` & `taxon_rank` are imported to the Taxon model if the taxon does
    not already exist in the Antenna database. But the Taxon model can store any metadata, so this is
    extensible in the future.
    [
        {
            "index": 0,
            "gbif_key": 123456,
            "label": "Vanessa atalanta",
            "taxon_rank": "SPECIES",
        },
        {
            "index": 1,
            "gbif_key": 789012,
            "label": "Limenitis",
            "taxon_rank": "GENUS",
        },
        {
            "id": 3,
            "gbif_key": 345678,
            "label": "Nymphalis californica",
            "taxon_rank": "SPECIES",
        }
    ]

    The labels field is a simple list of string labels the correct index order used by the model.
    [
        "Vanessa atalanta",
        "Limenitis",
        "Nymphalis californica",
    ]

    """

    data = models.JSONField(
        help_text="Complete metadata for each label, such as id, gbif_key, lookup value, source, etc."
    )
    labels = ArrayField(
        models.CharField(max_length=255),
        default=list,
        help_text="A simple list of string labels in the correct index order used by the model.",
    )
    labels_hash = models.BigIntegerField(
        help_text="A hash of the labels for faster comparison of label sets. Created on save.",
        null=True,
    )
    version = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    uri = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text=("A URI to the category map file. " "Could be a public web URL or object store path."),
    )

    algorithms: models.QuerySet[Algorithm]

    def __str__(self):
        return f"#{self.pk} with {len(self.labels)} classes ({self.version or 'unknown version'})"

    @classmethod
    def make_labels_hash(cls, labels):
        """
        Create a hash from the labels for faster comparison of unique label sets
        """
        return hash("".join(labels))

    @classmethod
    def labels_from_data(cls, data, label_field="label"):
        return [category[label_field] for category in data]

    @classmethod
    def data_from_labels(cls, labels, label_field="label"):
        return [{"index": i, label_field: label} for i, label in enumerate(labels)]

    def get_category(self, label, label_field="label"):
        # Can use JSON containment operators
        return self.data.index(next(category for category in self.data if category[label_field] == label))

    def with_taxa(self, category_field="label", only_indexes: list[int] | None = None) -> list[dict]:
        """
        Add Taxon objects to the category map, or None if no match

        :param category_field: The field in the category data to match against the Taxon name
        :return: The category map with the taxon objects added

        @TODO consider creating missing taxa in batch? the top 1 taxon is saved when a classification is created, but
        not the rest of the taxa in the category map, so the top_n response will often have missing taxa.
        @TODO this needs refactoring and optimization
        """

        from ami.main.models import Taxon

        if only_indexes:
            labels_data: list[dict] = [category for category in self.data if category["index"] in only_indexes]
            labels_label = [self.labels[i] for i in only_indexes]
        else:
            labels_data: list[dict] = self.data
            labels_label = self.labels

        if not labels_label or not labels_data:
            raise ValueError("No label data found in category map data")

        # @TODO standardize species search / lookup.
        # See similar query in ml.models.pipeline.get_or_create_taxon_for_classification()
        taxa = Taxon.objects.filter(
            models.Q(name__in=labels_label) | models.Q(search_names__overlap=labels_label),
            active=True,
        )
        taxon_map = {taxon.name: taxon for taxon in taxa}

        for category in labels_data:
            taxon = taxon_map.get(category[category_field])
            category["taxon"] = taxon

        return labels_data

    def resolve_taxa(self, label_field: str = "label") -> tuple[dict[str, Taxon], list[str]]:
        """
        Map every label of this category map to the active taxon it names.

        A label matches a taxon by its name or by one of its search names, the same rule
        used when a classification result is saved. Returns the matches keyed by label,
        and the labels that matched nothing, in category order.
        """
        from ami.main.models import Taxon

        labels = list(dict.fromkeys(self.labels))
        if not labels:
            raise ValueError("Category map has no labels")

        taxa = Taxon.objects.filter(
            models.Q(name__in=labels) | models.Q(search_names__overlap=labels),
            active=True,
        )
        by_label: dict[str, Taxon] = {}
        for taxon in taxa:
            by_label.setdefault(taxon.name, taxon)
            for alias in taxon.search_names or []:
                by_label.setdefault(alias, taxon)

        resolved = {label: by_label[label] for label in labels if label in by_label}
        unresolved = [label for label in labels if label not in by_label]
        return resolved, unresolved

    def save(self, *args, **kwargs):
        if not self.labels_hash:
            self.labels_hash = self.make_labels_hash(self.labels)
        super().save(*args, **kwargs)


class ArrayLength(models.Func):
    function = "CARDINALITY"


class AlgorithmQuerySet(BaseQuerySet):
    def with_category_count(self):
        """
        Annotate the queryset with the number of categories in the category map
        """
        return self.annotate(category_count=ArrayLength("category_map__labels"))

    def used_in_project(self, project) -> AlgorithmQuerySet:
        """Algorithms that produced results in the project, whether or not their
        pipeline is still enabled there.

        "Used" means owning actual output rows: classifiers and post-processing
        algorithms are found through their classifications, detectors through their
        detections (detectors never author a Classification). Superseded pipeline
        versions and standalone post-processing algorithms therefore stay listed as
        long as their results exist, while a configured-but-never-run algorithm does
        not appear.

        Cost note (EXPLAIN-verified against a production copy): neither lookup can be
        answered from an index, because neither table has a project column — project is
        reachable only through source_image. Both sides scan, so the call costs roughly
        0.1-0.6 s cold regardless of project size, growing with total table size.
        Executes the two lookups immediately rather than lazily; the id lists are tiny
        (one row per algorithm) and sorted so the SQL string, and therefore cachalot's
        cache key, is stable. Making this index-fast requires a denormalised project
        column on Classification/Detection.
        """
        from ami.main.models import Classification, Detection

        # ``order_by()`` clears each model's default ordering before ``distinct()``;
        # otherwise the ordering columns widen the DISTINCT back to one row per result.
        classifier_ids = (
            Classification.objects.filter(detection__source_image__project=project)
            .order_by()
            .values_list("algorithm_id", flat=True)
            .distinct()
        )
        detector_ids = (
            Detection.objects.filter(source_image__project=project)
            .order_by()
            .values_list("detection_algorithm", flat=True)
            .distinct()
        )
        ids = set(classifier_ids) | set(detector_ids)
        ids.discard(None)  # detections without a detection_algorithm
        return self.filter(pk__in=sorted(ids))


# Task types enum for better type checking
class AlgorithmTaskType(str, enum.Enum):
    DETECTION = "detection"
    LOCALIZATION = "localization"
    SEGMENTATION = "segmentation"
    CLASSIFICATION = "classification"
    EMBEDDING = "embedding"
    TRACKING = "tracking"
    TAGGING = "tagging"
    REGRESSION = "regression"
    CAPTIONING = "captioning"
    GENERATION = "generation"
    TRANSLATION = "translation"
    SUMMARIZATION = "summarization"
    QUESTION_ANSWERING = "question_answering"
    DEPTH_ESTIMATION = "depth_estimation"
    POSE_ESTIMATION = "pose_estimation"
    SIZE_ESTIMATION = "size_estimation"
    POST_PROCESSING = "post_processing"
    OTHER = "other"
    UNKNOWN = "unknown"

    def as_choice(self):
        return (self.value, self.name.replace("_", " ").title())


@typing.final
class Algorithm(BaseModel):
    """A machine learning algorithm"""

    name = models.CharField(max_length=255)
    key = models.SlugField(max_length=255, unique=True)
    task_type = models.CharField(
        max_length=255,
        default="unknown",
        null=True,
        choices=[task_type.as_choice() for task_type in AlgorithmTaskType],
    )
    description = models.TextField(blank=True)
    version = models.IntegerField(
        default=1,
        help_text="An internal, sortable and incrementable version number for the model.",
    )
    version_name = models.CharField(max_length=255, blank=True, null=True)
    uri = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text=("A URI to the weights or model details. Could be a public web URL or object store path."),
    )

    category_map = models.ForeignKey(
        AlgorithmCategoryMap,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="algorithms",
        default=None,
    )
    taxa_list = models.ForeignKey(
        "main.TaxaList",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="algorithms",
        help_text="The taxa list that mirrors this algorithm's category map. See sync_taxa_list().",
    )

    # api_base_url = models.URLField(blank=True)
    # api = models.CharField(max_length=255, blank=True)

    pipelines: models.QuerySet[Pipeline]
    classifications: models.QuerySet[Classification]

    objects = AlgorithmQuerySet.as_manager()

    detection_task_types = [
        AlgorithmTaskType.DETECTION,
        AlgorithmTaskType.LOCALIZATION,
        AlgorithmTaskType.SEGMENTATION,
    ]
    classification_task_types = [
        AlgorithmTaskType.CLASSIFICATION,
        AlgorithmTaskType.TAGGING,
    ]

    def __str__(self):
        return f'#{self.pk} "{self.name}" ({self.key}) v{self.version}'

    class Meta:
        ordering = ["name", "version"]

        unique_together = [
            ["name", "version"],
        ]

    def save(self, *args, **kwargs):
        if not self.version_name:
            self.version_name = f"{self.version}"
        if not self.key:
            self.key = f"{slugify(self.name)}-{self.version}"
        super().save(*args, **kwargs)

    def category_count(self) -> int | None:
        """
        Return the number of classes in the category map, if applicable and available.

        This must be retrieved using the QuerySet method with_category_count()
        but is defined here for the serializer to work.
        """
        return None

    def has_valid_category_map(self):
        return (
            (self.category_map is not None)
            and (self.category_map.data is not None)
            and (len(self.category_map.data) > 0)
        )

    def taxa_list_name(self) -> str:
        """Name of the global taxa list that holds every taxon this algorithm can predict."""
        return f"Category map of {self.name}"

    def sync_taxa_list(self, create_missing_taxa: bool = True) -> TaxaListSyncResult:
        """
        Make this algorithm's taxa list mirror its category map exactly (taxa added or
        removed to match), safe to call repeatedly. Algorithms sharing a category map
        share one list, which becomes "managed" (see TaxaList.is_managed) and refuses
        hand edits, since the next sync would overwrite them. Does nothing and returns
        a result with ``taxa_list=None`` when the algorithm has no category map, or the
        map has no labels.
        """
        from ami.main.models import Taxon, TaxonRank

        category_map = self.category_map
        if category_map is None or not category_map.labels:
            return TaxaListSyncResult(
                taxa_list=None, created_list=False, labels=0, matched=0, created_taxa=0, removed=0, unresolved=[]
            )

        with transaction.atomic():
            resolved, unresolved = category_map.resolve_taxa()
            created_taxa = 0
            if unresolved and create_missing_taxa:
                rank_by_label = {category["label"]: category.get("taxon_rank") for category in category_map.data}
                new_taxa = []
                for label in unresolved:
                    taxon = Taxon(name=label, rank=rank_by_label.get(label) or TaxonRank.UNKNOWN.name)
                    taxon.display_name = taxon.get_display_name()
                    new_taxa.append(taxon)
                Taxon.objects.bulk_create(new_taxa)
                for label, taxon in zip(unresolved, new_taxa):
                    resolved[label] = taxon
                created_taxa = len(new_taxa)
                unresolved = []

            taxa_list, created_list = self._get_or_create_shared_taxa_list(category_map)

            desired_ids = {taxon.pk for taxon in resolved.values()}
            current_ids = set(taxa_list.taxa.values_list("pk", flat=True))
            to_add = desired_ids - current_ids
            to_remove = current_ids - desired_ids
            if to_add:
                taxa_list.taxa.add(*to_add)
            if to_remove:
                taxa_list.taxa.remove(*to_remove)

            matched = len(resolved) - created_taxa
            self._sync_taxa_list_visibility_and_description(taxa_list, category_map, matched, unresolved)

        return TaxaListSyncResult(
            taxa_list=taxa_list,
            created_list=created_list,
            labels=len(category_map.labels),
            matched=matched,
            created_taxa=created_taxa,
            removed=len(to_remove),
            unresolved=unresolved,
        )

    def _get_or_create_shared_taxa_list(self, category_map: AlgorithmCategoryMap) -> tuple[TaxaList, bool]:
        """
        Find the list this algorithm should sync into: its own if it already has one, else a
        sibling algorithm's list for the same category map (so both share one list), else a
        new one. Links the list to this algorithm before returning.
        """
        from ami.main.models import TaxaList

        if self.taxa_list_id:
            return self.taxa_list, False

        sibling_list_id = (
            Algorithm.objects.filter(category_map_id=category_map.pk)
            .exclude(pk=self.pk)
            .exclude(taxa_list=None)
            .values_list("taxa_list_id", flat=True)
            .first()
        )
        if sibling_list_id:
            taxa_list = TaxaList.objects.get(pk=sibling_list_id)
            created_list = False
        else:
            taxa_list = TaxaList.objects.create(name=self.taxa_list_name())
            created_list = True

        self.taxa_list = taxa_list
        self.save(update_fields=["taxa_list"])
        return taxa_list, created_list

    def _sync_taxa_list_visibility_and_description(
        self,
        taxa_list: TaxaList,
        category_map: AlgorithmCategoryMap,
        matched: int,
        unresolved: list[str],
    ) -> None:
        """
        Visibility follows the processing services currently offering any algorithm that
        shares this list: public if any of them is public, else scoped to the union of
        their projects, else superuser-only.
        """
        from ami.ml.models.processing_service import ProcessingService

        describing = list(Algorithm.objects.filter(taxa_list=taxa_list).order_by("pk"))
        services = ProcessingService.objects.filter(pipelines__algorithms__in=describing).distinct()

        taxa_list.is_public = services.filter(is_public=True).exists()
        if taxa_list.is_public:
            taxa_list.projects.clear()
        else:
            # A service's projects M2M is blank=True: one with none produces a null
            # in this column via the LEFT JOIN, which .set() would try to insert as
            # a through-row's project_id and fail a NOT NULL constraint.
            project_ids = [pid for pid in services.values_list("projects", flat=True) if pid is not None]
            taxa_list.projects.set(project_ids)

        names = ", ".join(f"{algorithm.name} (key {algorithm.key})" for algorithm in describing)
        taxa_list.description = (
            f"Every taxon predicted by the category map used by {names}: "
            f"{len(category_map.labels)} labels, {matched} resolved, {len(unresolved)} unresolved."
        )
        taxa_list.save(update_fields=["is_public", "description"])
