"""
Taxonomy: the Taxon, TaxaList, and Tag models, their managers/querysets, and the
cached-parent schema.

Models are declared here but remain in the ``main`` app. Related models are
referenced by string label, or imported inside the method that needs them, so
this module never imports ``ami.main.models`` at import time — ``main.models``
imports this one.
"""

import collections
import datetime
import logging
import typing
from typing import TYPE_CHECKING, final

import pydantic
from django.contrib.auth.models import AnonymousUser
from django.contrib.postgres.fields import ArrayField
from django.db import models, transaction
from django.db.models import Exists, OuterRef, Q
from django.db.models.functions import Coalesce
from django_pydantic_field import SchemaField
from rest_framework.request import Request

from ami.base.models import BaseModel, BaseQuerySet
from ami.main import charts
from ami.main.models_future.enums import TaxonRank
from ami.main.models_future.filters import build_occurrence_default_filters_q, build_taxa_recursive_filter_q
from ami.users.models import User
from ami.utils.requests import get_apply_default_filters_flag

if TYPE_CHECKING:
    from ami.main.models import Classification, Detection, Occurrence, Project

logger = logging.getLogger(__name__)


class TaxonParent(pydantic.BaseModel):
    """
    Should contain all data needed for TaxonParentSerializer

    Needs a custom encoder and decoder for for the TaxonRank enum
    because it is an OrderedEnum and not a standard str Enum.
    """

    id: int
    name: str
    rank: TaxonRank

    class Config:
        # Make sure the TaxonRank is retrieved as an object and not a string
        # so we can sort by rank. The DRF serializer will convert it to a string.
        # just for the API responses.
        use_enum_values = False


def _case_from_map(mapping: dict, default, output_field: models.Field) -> models.expressions.Combinable:
    """Turn a precomputed ``{taxon_id: value}`` map into a constant-time ``CASE``.

    The result is constant per row, so it is DB-sortable, paginatable, and stripped from
    the pagination ``COUNT`` — unlike a per-taxon correlated subquery, which is
    re-evaluated for every row and (in ``COUNT``) for every taxon in the project. Only
    sparse maps work here: one ``When`` per entry blows past sqlparse's 10000-token
    limit at ~hundreds of taxa × multiple columns.
    """
    if not mapping:
        return models.Value(default, output_field=output_field)
    return models.Case(
        *(
            models.When(id=taxon_id, then=models.Value(value, output_field=output_field))
            for taxon_id, value in mapping.items()
        ),
        default=models.Value(default, output_field=output_field),
        output_field=output_field,
    )


def verified_taxon_counts(
    project: "Project",
    request: "Request | None",
    *,
    occurrence_filters: models.Q,
    apply_default_score_filter: bool = True,
    apply_default_taxa_filter: bool = True,
) -> dict[int, int]:
    """Hierarchical rollup of verified-occurrence counts, keyed by taxon id.

    Each occurrence with a non-withdrawn ``Identification`` counts toward its determination
    taxon and every ancestor in ``parents_json`` (verifying a species also credits its
    genus / family / order rows). The verified subset is sparse relative to all
    occurrences, so this is a single cheap Python pass. The result feeds both the
    constant-time ``verified_count`` ``CASE`` annotation
    (:meth:`TaxonQuerySet.with_verification_counts`) and the verified-vs-unverified branch
    of the example-occurrence dispatch (:meth:`TaxonQuerySet.with_example_occurrence_ids`),
    so callers compute it once and pass it to both.
    """
    # We need to do a function level import here to avoid a circular import,
    # since ami.main.models imports this module.
    from ami.main.models import Identification, Occurrence

    default_q = build_occurrence_default_filters_q(
        project,
        request,
        occurrence_accessor="",
        apply_default_score_filter=apply_default_score_filter,
        apply_default_taxa_filter=apply_default_taxa_filter,
    )
    verified_occurrences = (
        Occurrence.objects.filter(occurrence_filters)
        .filter(default_q)
        .filter(Exists(Identification.objects.filter(occurrence=OuterRef("pk"), withdrawn=False)))
    )
    # ``pk`` is selected only so ``.distinct()`` below dedupes by occurrence: when
    # occurrence_filters joins to detections (e.g. ?collection=<id>), one Occurrence
    # yields a row per matching Detection, which would otherwise inflate counts.
    value_fields = ["pk", "determination_id", "determination__parents_json"]

    counts: dict[int, int] = {}
    for row in verified_occurrences.values(*value_fields).distinct():
        determination_id = row["determination_id"]
        taxon_ids: set[int] = set()
        if determination_id is not None:
            taxon_ids.add(determination_id)
        for parent in row["determination__parents_json"] or []:
            # parents_json round-trips through the pydantic schema field, so elements
            # may be dicts or ``TaxonParent`` objects depending on the query path.
            parent_id = parent.get("id") if isinstance(parent, dict) else getattr(parent, "id", None)
            if parent_id is not None:
                taxon_ids.add(int(parent_id))
        for taxon_id in taxon_ids:
            counts[taxon_id] = counts.get(taxon_id, 0) + 1
    return counts


class TaxonQuerySet(BaseQuerySet):
    def with_observation_counts_subqueries(
        self,
        project: "Project",  # String to avoid circular import with ami.main.models.
        request: "Request | None",  # String to avoid circular import with ami.main.models.
        *,
        occurrence_filters: models.Q,
        apply_default_score_filter: bool = True,
        apply_default_taxa_filter: bool = True,
    ):
        """Annotate ``occurrences_count`` / ``best_determination_score`` / ``last_detected``
        via three correlated ``Subquery`` annotations.

        Index-served by the composite ``(determination_id, project_id, event_id,
        determination_score)`` index on Occurrence. Use this on non-collection paths.
        When ``occurrence_filters`` joins detections (e.g. ``?collection=<id>``) the
        correlated form degrades to a per-row scan; use
        :meth:`with_observation_counts_aggregated` instead.
        """
        # We need to do a function level import here to avoid a circular import,
        # since ami.main.models imports this module.
        from ami.main.models import Occurrence

        default_filters_q = build_occurrence_default_filters_q(
            project,
            request,
            occurrence_accessor="",
            apply_default_score_filter=apply_default_score_filter,
            apply_default_taxa_filter=apply_default_taxa_filter,
        )
        base_filter = models.Q(occurrence_filters, determination_id=OuterRef("id")) & default_filters_q

        occurrences_count_subquery = models.Subquery(
            Occurrence.objects.filter(base_filter)
            .values("determination_id")
            .annotate(count=models.Count("id"))
            .values("count")[:1],
            output_field=models.IntegerField(),
        )
        best_score_subquery = models.Subquery(
            Occurrence.objects.filter(base_filter)
            .values("determination_id")
            .annotate(max_score=models.Max("determination_score"))
            .values("max_score")[:1],
            output_field=models.FloatField(),
        )
        last_detected_subquery = models.Subquery(
            Occurrence.objects.filter(base_filter, detections__timestamp__isnull=False)
            .values("determination_id")
            .annotate(last_detected=models.Max("detections__timestamp"))
            .values("last_detected")[:1],
            output_field=models.DateTimeField(),
        )
        return self.annotate(
            occurrences_count=Coalesce(occurrences_count_subquery, 0),
            best_determination_score=best_score_subquery,
            last_detected=last_detected_subquery,
        )

    def with_observation_counts_aggregated(
        self,
        project: "Project",  # String to avoid circular import with ami.main.models.
        request: "Request | None",  # String to avoid circular import with ami.main.models.
        *,
        relation_occurrence_filters: models.Q,
        apply_default_score_filter: bool = True,
    ):
        """Annotate ``occurrences_count`` / ``best_determination_score`` / ``last_detected``
        via conditional aggregation over the Taxon→occurrences reverse relation.

        Required when ``relation_occurrence_filters`` joins detections (``?collection=<id>``),
        where the correlated-subquery form degrades to per-row scans. One GROUP BY,
        constant-size SQL. ``Count(distinct)`` dedupes the detections-join fan-out.

        The default *taxa* include/exclude filter is deliberately omitted from
        ``count_filter``: it is redundant with row-level
        :meth:`filter_by_project_default_taxa`, and including it adds a
        ``parents_json`` containment join inside the aggregate that the planner cannot
        reconcile with the detections join (measured: 0.3s → 182s on a ~1k-taxa project).
        Score threshold is per-occurrence so it stays.
        """
        count_filter = relation_occurrence_filters & build_occurrence_default_filters_q(
            project,
            request,
            occurrence_accessor="occurrences",
            apply_default_score_filter=apply_default_score_filter,
            apply_default_taxa_filter=False,
        )
        return self.annotate(
            occurrences_count=models.Count("occurrences", filter=count_filter, distinct=True),
            best_determination_score=models.Max("occurrences__determination_score", filter=count_filter),
            last_detected=models.Max("occurrences__detections__timestamp", filter=count_filter),
        )

    def observed_in_project_subqueries(
        self,
        project: "Project",  # String to avoid circular import with ami.main.models.
        request: "Request | None",  # String to avoid circular import with ami.main.models.
        *,
        occurrence_filters: models.Q,
        apply_default_score_filter: bool = True,
        apply_default_taxa_filter: bool = True,
    ):
        """Restrict the queryset to taxa observed in the filtered occurrence set, via a
        materialised ``id__in``. Pair with :meth:`with_observation_counts_subqueries`.

        The materialised form runs the (potentially detections-joined) filter exactly
        once and leaves the pagination ``COUNT`` / page as a plain indexed ``id IN
        (...)``. Aggregation-path callers should use ``.filter(occurrences_count__gt=0)``
        (HAVING) instead.
        """
        # We need to do a function level import here to avoid a circular import,
        # since ami.main.models imports this module.
        from ami.main.models import Occurrence

        default_filters_q = build_occurrence_default_filters_q(
            project,
            request,
            occurrence_accessor="",
            apply_default_score_filter=apply_default_score_filter,
            apply_default_taxa_filter=apply_default_taxa_filter,
        )
        observed_taxon_ids = list(
            Occurrence.objects.filter(occurrence_filters)
            .filter(default_filters_q)
            .filter(determination_id__isnull=False)
            .values_list("determination_id", flat=True)
            .distinct()
        )
        return self.filter(id__in=observed_taxon_ids)

    def with_verification_counts(
        self,
        project: "Project",  # String to avoid circular import with ami.main.models.
        request: "Request | None",  # String to avoid circular import with ami.main.models.
        *,
        occurrence_filters: models.Q,
        apply_default_score_filter: bool = True,
        apply_default_taxa_filter: bool = True,
        verified: bool | None = None,
        verified_counts: dict[int, int] | None = None,
    ):
        """Annotate ``verified_count`` and optionally apply the
        ``verified=true|false`` filter.

        Counts roll up descendant occurrences (verifying a species also counts toward
        its genus / family rows). They concern only *verified* occurrences (those with a
        non-withdrawn ``Identification``) — sparse relative to all occurrences — so the
        hierarchical rollup is a single Python pass over that small subset applied as
        constant-time ``CASE`` annotations. A correlated ``parents_json`` subquery per
        taxon would not scale (GIN can't serve a containment with an ``OuterRef`` RHS).

        ``verified_counts`` may be supplied precomputed (via :func:`verified_taxon_counts`)
        when the caller also needs the verified-taxon set — e.g. for the example-occurrence
        dispatch — so the verified-occurrence query runs once, not twice.

        Model-agreement counts (whether the chosen identification matched the model's
        top prediction) are tracked separately — see issue #1319.
        """
        if verified_counts is None:
            verified_counts = verified_taxon_counts(
                project,
                request,
                occurrence_filters=occurrence_filters,
                apply_default_score_filter=apply_default_score_filter,
                apply_default_taxa_filter=apply_default_taxa_filter,
            )

        qs = self.annotate(verified_count=_case_from_map(verified_counts, 0, models.IntegerField()))

        if verified is True:
            qs = qs.filter(id__in=list(verified_counts.keys()))
        elif verified is False:
            qs = qs.exclude(id__in=list(verified_counts.keys()))

        return qs

    def with_example_occurrence_ids(
        self,
        project: "Project",  # String to avoid circular import with ami.main.models.
        request: "Request | None",  # String to avoid circular import with ami.main.models.
        *,
        occurrence_filters: models.Q,
        verified_taxon_ids: set[int],
        apply_default_score_filter: bool = True,
        apply_default_taxa_filter: bool = True,
    ):
        """Annotate one representative occurrence id per taxon for the presence-verification
        Example column (#1320), plus the source occurrence ids behind the Last-seen and
        Best-score cells.

        - ``example_occurrence_id`` is hybrid: the latest occurrence for a *verified* row
          (is this taxon still showing up?), the best-scoring *unverified* occurrence
          otherwise (the cleanest predicted ID, fastest for a human to confirm).
          ``verified_taxon_ids`` (sparse — bounded by human review) selects the branch.
        - ``best_scoring_occurrence_id`` / ``last_detected_occurrence_id`` mirror the
          ``best_determination_score`` / ``last_detected`` value columns so those cells can
          deep-link to their source occurrence.

        All three match by exact determination (``determination_id = taxon``), consistent
        with the observation-count columns on the default path; only ``verified_count``
        rolls up to ancestors, so higher-rank rows without direct occurrences get ``NULL``.

        These are correlated subqueries, index-served by the composite
        ``(determination_id, project_id, event_id, determination_score)`` index on the
        default path. When ``occurrence_filters`` joins detections (``?collection=<id>``)
        they degrade to per-row scans, so the view gates this behind the opt-in
        ``with_example_occurrences`` query param to protect the list's latency budget.
        """
        # We need to do a function level import here to avoid a circular import,
        # since ami.main.models imports this module.
        from ami.main.models import Identification, Occurrence

        default_q = build_occurrence_default_filters_q(
            project,
            request,
            occurrence_accessor="",
            apply_default_score_filter=apply_default_score_filter,
            apply_default_taxa_filter=apply_default_taxa_filter,
        )
        base_filter = models.Q(occurrence_filters, determination_id=OuterRef("id")) & default_q

        # OuterRef("id") resolves to the outer Taxon; OuterRef("pk") inside the Exists
        # resolves to the inner Occurrence.
        not_verified = ~Exists(Identification.objects.filter(occurrence=OuterRef("pk"), withdrawn=False))

        # nulls_last: a NULL determination_score would otherwise sort first under DESC and
        # be picked as "best" whenever the score threshold is not applied.
        by_score_desc = (models.F("determination_score").desc(nulls_last=True), "-id")
        best_scoring = Occurrence.objects.filter(base_filter).order_by(*by_score_desc).values("id")[:1]
        latest = (
            Occurrence.objects.filter(base_filter, detections__timestamp__isnull=False)
            .order_by("-detections__timestamp", "-id")
            .values("id")[:1]
        )
        best_unverified = (
            Occurrence.objects.filter(base_filter).filter(not_verified).order_by(*by_score_desc).values("id")[:1]
        )

        return self.annotate(
            best_scoring_occurrence_id=models.Subquery(best_scoring, output_field=models.IntegerField()),
            last_detected_occurrence_id=models.Subquery(latest, output_field=models.IntegerField()),
            example_occurrence_id=models.Case(
                models.When(
                    id__in=list(verified_taxon_ids),
                    then=models.Subquery(latest, output_field=models.IntegerField()),
                ),
                default=models.Subquery(best_unverified, output_field=models.IntegerField()),
                output_field=models.IntegerField(),
            ),
        )

    def filter_by_project_default_taxa(
        self,
        project: "Project | None" = None,  # String to avoid circular import with ami.main.models.
        request: Request | None = None,
    ):
        """
        Filter taxa according to a project's default include and exclude settings,
        keeping taxa in the include set along with their descendants
        and removing taxa in the exclude set along with their descendants.

        Note: For TaxonQuerySet, this method DOES check apply_defaults since it's
        filtering Taxa objects directly, not Occurrences.
        """
        if project is None:
            return self

        # Check if default filters should be bypassed
        if get_apply_default_filters_flag(request) is False:
            return self

        include_taxa = project.default_filters_include_taxa.all()
        exclude_taxa = project.default_filters_exclude_taxa.all()

        # Use taxon_accessor="" for direct Taxa model filtering (not through occurrences)
        taxa_q = build_taxa_recursive_filter_q(include_taxa, exclude_taxa, taxon_accessor="")
        if taxa_q:
            return self.filter(taxa_q)

        return self

    def visible_for_user(self, user: User | AnonymousUser):
        # We need to do a function level import here to avoid a circular import,
        # since ami.main.models imports this module.
        from ami.main.models import Occurrence, Project

        if user.is_superuser:
            return self

        is_anonymous = isinstance(user, AnonymousUser)

        # Visible projects
        project_qs = Project.objects.all()
        if is_anonymous:
            project_qs = project_qs.filter(draft=False)
        else:
            project_qs = project_qs.filter(Q(draft=False) | Q(owner=user) | Q(members=user))

        # Taxa explicitly linked to visible projects
        direct_taxa = self.filter(projects__in=project_qs)

        # Taxa with at least one occurrence in visible projects
        occurrence_taxa = self.filter(
            Exists(
                Occurrence.objects.filter(
                    project__in=project_qs,
                    determination_id=OuterRef("id"),
                )
            )
        )

        return (direct_taxa | occurrence_taxa).distinct()


@final
class TaxonManager(models.Manager.from_queryset(TaxonQuerySet)):
    def get_queryset(self):
        # Prefetch parent and parents
        # return super().get_queryset().select_related("parent").prefetch_related("parents")
        return super().get_queryset().select_related("parent")

    def add_genus_parents(self):
        """Add direct genus parents to all species that don't have them, based on the scientific name.

        Create a genus if it doesn't exist based on the scientific name of the species.
        This will replace any parents of a species that are not of the GENUS rank.
        """
        Taxon: "Taxon" = self.model  # type: ignore
        species = self.get_queryset().filter(rank=TaxonRank.SPECIES)  # , parent=None)
        updated = []
        for taxon in species:
            if taxon.parent and taxon.parent.rank == TaxonRank.GENUS:
                continue

            genus_name = taxon.name.split()[0].strip()

            # There can be only one taxon with a given name.
            genus_taxon, created = Taxon.objects.get_or_create(name=genus_name, defaults={"rank": TaxonRank.GENUS})
            if created:
                updated.append(genus_taxon)
            elif genus_taxon.rank != TaxonRank.GENUS:
                genus_taxon.rank = TaxonRank.GENUS
                logger.info(f"Updating rank of existing {genus_taxon} from {genus_taxon.rank} to {TaxonRank.GENUS}")
                genus_taxon.save()
                updated.append(genus_taxon)

            taxon.parent = genus_taxon
            logger.info(f"Added parent {genus_taxon} to {taxon}")
            taxon.save()
            updated.append(taxon)

        return updated

    def update_display_names(self, queryset: models.QuerySet | None = None):
        """Update the display names of all taxa."""

        taxa = []

        for taxon in queryset or self.get_queryset():
            taxon.display_name = taxon.get_display_name()
            taxa.append(taxon)

        self.bulk_update(taxa, ["display_name"])

    # Method that returns taxa nested in a tree structure
    def tree(self, root: typing.Optional["Taxon"] = None, filter_ranks: list[TaxonRank] = []) -> dict:
        """Build a recursive tree of taxa."""

        root = root or self.root()

        # Fetch all taxa
        taxa = self.get_queryset().filter(active=True)

        # Build index of taxa by parent
        taxa_by_parent = collections.defaultdict(list)
        for taxon in taxa:
            # Skip adding this taxon if its rank is excluded
            if filter_ranks and TaxonRank(taxon.rank) not in filter_ranks:
                continue

            parent = taxon.parent or root

            # Attach taxa to the nearest parent with a rank that is not excluded
            if filter_ranks and TaxonRank(parent.rank) not in filter_ranks:
                while parent and TaxonRank(parent.rank) not in filter_ranks:
                    parent = parent.parent

            if parent != taxon:
                taxa_by_parent[parent].append(taxon)

        # Recursively build a nested tree
        def _tree(taxon):
            return {
                "taxon": taxon,
                "children": [_tree(child) for child in taxa_by_parent[taxon]],
            }

        if filter_ranks and TaxonRank(root.rank) not in filter_ranks:
            raise ValueError(f"Cannot filter rank {root.rank} from tree because the root taxon must be included")

        return _tree(root)

    def tree_of_names(self, root: typing.Optional["Taxon"] = None) -> dict:
        """
        Build a recursive tree of taxon names.

        Names in the database are not not formatted as nicely as the python-rendered versions.
        """

        root = root or self.root()

        # Fetch all names and parent names
        names = self.get_queryset().filter(active=True).values_list("name", "parent__name")

        # Index names by parent name
        names_by_parent = collections.defaultdict(list)
        for name, parent_name in names:
            names_by_parent[parent_name].append(name)

        # Recursively build a nested tree

        def _tree(name):
            return {
                "name": name,
                "children": [_tree(child) for child in names_by_parent[name]],
            }

        return _tree(root.name)

    def root(self):
        """Get the root taxon, the one with no parent and the highest taxon rank."""

        for rank in list(TaxonRank):
            taxon = self.get_queryset().filter(parent=None, rank=rank.name).first()
            if taxon:
                return taxon

        root = self.get_queryset().filter(parent=None).first()
        assert root, "No root taxon found"
        return root

    def update_all_parents(self):
        """Efficiently update all parents for all taxa."""
        taxa = self.get_queryset().select_related("parent")
        logging.info(f"Updating the cached parent tree for {taxa.count()} taxa")

        # Build a dictionary of taxon parents
        parents = {taxon.id: taxon.parent_id for taxon in taxa}

        # Precompute all parents in a single pass
        all_parents = {}
        for taxon_id in parents:
            if taxon_id not in all_parents:
                taxon_parents = []
                current_id = taxon_id
                while current_id in parents:
                    current_id = parents[current_id]
                    taxon_parents.append(current_id)
                all_parents[taxon_id] = taxon_parents

        # Prepare bulk update data
        bulk_update_data = []
        for taxon in taxa:
            taxon_parents = all_parents[taxon.id]
            parent_taxa = list(taxa.filter(id__in=taxon_parents))
            taxon_parents = [
                TaxonParent(
                    id=taxon.id,
                    name=taxon.name,
                    rank=taxon.rank,
                )
                for taxon in parent_taxa
            ]
            taxon_parents.sort(key=lambda t: t.rank)

            bulk_update_data.append(taxon)

        # Perform bulk update
        # with transaction.atomic():
        #     self.bulk_update(bulk_update_data, ["parents_json"], batch_size=1000)
        # There is a bug that causes the bulk update to fail with a custom JSONField
        # https://code.djangoproject.com/ticket/35167
        # So we have to update each taxon individually
        for taxon in bulk_update_data:
            taxon.save(update_fields=["parents_json"])

        logging.info(f"Updated parents for {len(bulk_update_data)} taxa")

    def with_children(self):
        qs = self.get_queryset()
        # Add Taxon that are children of this Taxon using parents_json field (not direct_children)

        # example for single taxon:
        taxon = Taxon.objects.get(pk=1)
        taxa = Taxon.objects.filter(parents_json__contains=[{"id": taxon.id}])
        # add them to the queryset
        qs = qs.annotate(children=models.Subquery(taxa.values("id")))
        return qs

    def with_occurrence_counts(self) -> models.QuerySet:
        """
        Count the number of occurrences for a taxon and all occurrences of the taxon's children.

        @TODO Try a recursive CTE in a raw SQL query,
        or count the occurrences in a separate query and attach them to the Taxon objects.
        """

        raise NotImplementedError(
            "Occurrence counts can not be calculated in a subquery with the current JSONField schema. "
            "Fetch them per taxon."
        )


@final
class Taxon(BaseModel):
    """A taxonomic classification"""

    name = models.CharField(max_length=255, unique=True)
    display_name = models.CharField("Cached display name", max_length=255, null=True, blank=True, unique=True)
    rank = models.CharField(max_length=255, choices=TaxonRank.choices(), default=TaxonRank.SPECIES.name)
    parent = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="direct_children"
    )

    # Examples how to query this JSON array field
    # Taxon.objects.filter(parents_json__contains=[{"id": 1}])
    # https://stackoverflow.com/a/53942463/966058
    parents_json = SchemaField(list[TaxonParent], null=False, blank=True, default=list)

    active = models.BooleanField(default=True)
    synonym_of = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="synonyms")

    common_name_en = models.CharField(max_length=255, blank=True, null=True)

    search_names = ArrayField(models.CharField(max_length=255), null=True, blank=True)
    gbif_taxon_key = models.BigIntegerField("GBIF taxon key", blank=True, null=True)
    bold_taxon_bin = models.CharField("BOLD taxon BIN", max_length=255, blank=True, null=True)
    inat_taxon_id = models.BigIntegerField("iNaturalist taxon ID", blank=True, null=True)
    fieldguide_id = models.CharField(max_length=255, blank=True, null=True)
    # lepsai_id = models.BigIntegerField("LepsAI / Fieldguide ID", blank=True, null=True)

    cover_image_url = models.URLField(max_length=255, blank=True, null=True)
    cover_image_credit = models.CharField(max_length=255, blank=True, null=True)

    notes = models.TextField(blank=True)

    projects = models.ManyToManyField("Project", related_name="taxa")
    direct_children: models.QuerySet["Taxon"]
    occurrences: models.QuerySet["Occurrence"]
    classifications: models.QuerySet["Classification"]
    lists: models.QuerySet["TaxaList"]

    author = models.CharField(max_length=255, blank=True)
    authorship_date = models.DateField(null=True, blank=True, help_text="The date the taxon was described.")
    ordering = models.IntegerField(null=True, blank=True)
    sort_phylogeny = models.BigIntegerField(blank=True, null=True)
    tags = models.ManyToManyField("Tag", related_name="taxa", blank=True)
    objects: TaxonManager = TaxonManager()

    # Type hints for auto-generated fields
    parent_id: int | None

    def __str__(self) -> str:
        name_with_rank = f"{self.name} ({self.rank})"
        return name_with_rank

    def get_display_name(self):
        """
        This must be unique because it is used for choice keys in Label Studio.
        """
        if self.rank == "SPECIES":
            return self.name
        elif self.rank == "GENUS":
            return f"{self.name} sp."
        # elif self.rank not in ["ORDER", "FAMILY"]:
        #     return f"{self.name} ({self.rank})"
        else:
            return self.name

    def get_rank(self) -> TaxonRank:
        """
        Return the rank str value as a TaxonRank enum.
        """
        return TaxonRank(self.rank)

    def num_direct_children(self) -> int:
        return self.direct_children.count()

    def num_children_recursive(self) -> int:
        # Use the parents_json field to get all children
        return Taxon.objects.filter(parents_json__contains=[{"id": self.pk}]).count()

    def occurrences_count(self) -> int:
        # return self.occurrences.count()
        return 0

    def occurrences_count_recursive(self) -> int:
        """
        Use the parents_json field to get all children, count their occurrences and sum them.
        """
        return (
            Taxon.objects.filter(models.Q(models.Q(parents_json__contains=[{"id": self.pk}]) | models.Q(id=self.pk)))
            .annotate(occurrences_count=models.Count("occurrences"))
            .aggregate(models.Sum("occurrences_count"))["occurrences_count__sum"]
            or 0
        )

    def detections_count(self) -> int:
        # return Detection.objects.filter(occurrence__determination=self).count()
        return 0

    def events_count(self) -> int:
        return 0

    def latest_occurrence(self) -> "Occurrence | None":  # String to avoid circular import with ami.main.models.
        return self.occurrences.order_by("-created_at").first()

    def latest_detection(self) -> "Detection | None":  # String to avoid circular import with ami.main.models.
        from ami.main.models import Detection

        return Detection.objects.filter(occurrence__determination=self).order_by("-created_at").first()

    def last_detected(self) -> datetime.datetime | None:
        # This is handled by an annotation
        return None

    def best_determination_score(self) -> float | None:
        # This is handled by an annotation if we are filtering by project, deployment or event
        return None

    def verified_count(self) -> int | None:
        # Handled by an annotation when filtering by project (TaxonQuerySet.with_verification_counts)
        return None

    def occurrence_images(self, limit: int | None = 10) -> list[str]:
        # This is handled by an annotation if we are filtering by project, deployment or event
        return []

    def get_occurrence_images(
        self,
        limit: int | None = 10,
        project_id: int | None = None,
        classification_threshold: float = 0,
    ) -> list[str]:
        """
        Return one image from each occurrence of this Taxon.
        The image should be from the detection with the highest classification score.

        This is used for image thumbnail previews in the species summary view.

        The project ID is an optional filter however
        @TODO important, this should always filter by what the current user has access to.
        Use the request.user to filter by the user's access.
        Use the request to generate the full media URLs.
        """
        # We need to do a function level import here to avoid a circular import,
        # since ami.main.models imports this module.
        from ami.main.models import Classification, get_media_url

        # Retrieve the URLs using a single optimized query
        qs = (
            self.occurrences.prefetch_related(
                models.Prefetch(
                    "detections__classifications",
                    queryset=Classification.objects.filter(score__gte=classification_threshold).order_by("-score"),
                )
            )
            .annotate(max_score=models.Max("detections__classifications__score"))
            .filter(detections__classifications__score=models.F("max_score"))
            .order_by("-max_score")
        )
        if project_id is not None:
            # @TODO this should check the user's access instead
            qs = qs.filter(project=project_id)

        detection_image_paths = qs.values_list("detections__path", flat=True)[:limit]

        # @TODO should this be done in the serializer?
        # @TODO better way to get distinct values from an annotated queryset?
        return [get_media_url(path) for path in detection_image_paths if path]

    def list_names(self) -> str:
        return ", ".join(self.lists.values_list("name", flat=True))

    def update_parents(self, save=True):
        """
        Populate the cached `parents_json` list by recursively following the `parent` field.

        @TODO this requires all of the taxon's parent taxa to have the `parent` attribute set correctly.
        """

        current_taxon = self
        parents = []
        logger.debug(f"Updating parents for {current_taxon} (#{current_taxon.pk})")
        while current_taxon.parent is not None:
            taxon_parent = TaxonParent(
                id=current_taxon.parent.id,
                name=current_taxon.parent.name,
                rank=current_taxon.parent.rank,
            )
            logger.debug(f"Adding parent {taxon_parent} to {current_taxon} (#{current_taxon.pk}) in parents_json")
            parents.append(taxon_parent)
            current_taxon = current_taxon.parent
        # Sort parents by rank using ordered enum
        parents = sorted(parents, key=lambda t: t.rank)
        self.parents_json = parents
        if save:
            self.save()

        return parents

    def update_search_names(self, save=False):
        """
        Add common names to the search names list.

        @TODO add synonyms and other names to the search names list.
        """
        search_names = self.search_names or []
        common_name_field_names = [field.name for field in self._meta.fields if field.name.startswith("common_name_")]
        for field_name in common_name_field_names:
            common_name = getattr(self, field_name)
            if common_name:
                search_names.append(common_name)
        self.search_names = list(set(search_names))
        if save:
            self.save(update_fields=["search_names"])

    def summary_data(
        self, project: "Project | None" = None  # String to avoid circular import with ami.main.models.
    ) -> list[dict]:
        """
        Data prepared for rendering charts with plotly.js
        """

        if project is None:
            # We could return data for all projects a user has access to,
            # but for now we just return an empty list.
            return []

        plots = []

        plots.append(charts.average_occurrences_per_day(project_pk=project.pk, taxon_pk=self.pk))
        plots.append(charts.average_occurrences_per_month(project_pk=project.pk, taxon_pk=self.pk))

        return plots

    class Meta:
        ordering = [
            "ordering",
            "name",
        ]
        verbose_name_plural = "Taxa"

        # Set unique constraints on name & rank
        # constraints = [
        #     models.UniqueConstraint(fields=["name", "rank", "parent"], name="unique_name_and_placement"),
        # ]
        indexes = [
            # Add index for default ordering
            models.Index(fields=["ordering", "name"]),
        ]

    def update_calculated_fields(self, save=False):
        self.display_name = self.get_display_name()
        self.update_parents(save=False)
        self.update_search_names(save=False)
        if save:
            self.save(update_calculated_fields=False)

    def save(self, update_calculated_fields=True, *args, **kwargs):
        super().save(*args, **kwargs)
        if update_calculated_fields:
            self.update_calculated_fields(save=True)


class TaxaListQuerySet(BaseQuerySet):
    def get_or_create_for_project(
        self, name: str, project: "Project | None" = None, **defaults
    ) -> tuple["TaxaList", bool]:
        """
        Get or create a TaxaList with uniqueness scoped to project.

        - If project is None: looks for/creates a global list (no project associations)
        - If project is provided: looks for/creates a list associated with that project

        :param name: Name of the taxa list.
        :param project: Project to scope the list to, or None for a global list.
        :param defaults: Extra field values applied only when creating a new list
            (ignored on the get path, matching Django's ``get_or_create`` semantics).

        If concurrent callers race past the ``DoesNotExist`` check and both create
        rows, the next caller will see ``MultipleObjectsReturned`` and fall back
        to returning the oldest row instead of raising.

        Returns:
            Tuple of (TaxaList, created: bool)
        """
        if project is None:
            # Global list: find list with this name that has no project associations
            qs = self.filter(name=name).annotate(project_count=models.Count("projects")).filter(project_count=0)
        else:
            # Project-specific: find list with this name in this project
            qs = self.filter(name=name, projects=project)

        try:
            return qs.get(), False
        except self.model.DoesNotExist:
            with transaction.atomic():
                taxa_list = self.create(name=name, **defaults)
                if project:
                    taxa_list.projects.add(project)
            return taxa_list, True
        except self.model.MultipleObjectsReturned:
            # Handle existing duplicates gracefully - return the oldest one
            taxa_list = qs.order_by("created_at").first()
            assert taxa_list is not None  # We know there's at least one
            return taxa_list, False


class TaxaListManager(models.Manager.from_queryset(TaxaListQuerySet)):
    pass


@final
class TaxaList(BaseModel):
    """A checklist of taxa"""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    taxa = models.ManyToManyField(Taxon, related_name="lists")
    projects = models.ManyToManyField("Project", related_name="taxa_lists")

    objects: TaxaListManager = TaxaListManager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Taxa Lists"


@final
class Tag(BaseModel):
    """A tag for taxa"""

    name = models.CharField(max_length=255)
    project = models.ForeignKey(
        "Project",  # String to avoid circular import with ami.main.models.
        on_delete=models.CASCADE,
        related_name="tags",
        null=True,
        blank=True,
    )

    taxa: models.QuerySet[Taxon]

    class Meta:
        unique_together = ("name", "project")
