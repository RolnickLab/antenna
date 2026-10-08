"""
The numbers the model-performance views read.

Each of these answers one question a screen asks, in a single query. They are kept apart
from the models so a view can ask for them without pulling in the training machinery, and
so the same number means the same thing everywhere it is shown.
"""

import typing

from django.db import models

from ami.main.models import OccurrenceSet, Project, TaxaList, Taxon
from ami.ml.models.algorithm import Algorithm
from ami.ml.models.evaluation import AlgorithmEvaluation, TaxonEvaluation

DEFAULT_EVALUATION_LIMIT = 5


def visible_sets(project: Project | None, user=None) -> models.QuerySet:
    """
    The evaluation sets a caller may be shown: the project's own, plus the global ones.

    Taxa and algorithms are shared across the platform but evaluation sets are not, so
    every read below has to be scoped or it reports another project's numbers.

    Without a project the scope falls back to the sets the user can reach, which is what a
    detail endpoint needs: the algorithm detail route carries no project id, and scoping
    those reads to the global sets alone hid every score a project had recorded. Falling
    back to the user keeps a caller from seeing another project's sets while still
    answering a request that simply did not name one. With neither, only the global sets.
    """
    if project is not None:
        return OccurrenceSet.objects.for_project(project)
    if user is not None:
        return OccurrenceSet.objects.visible_for_user(user)
    return OccurrenceSet.objects.filter(projects__isnull=True)


def project_for(request) -> Project | None:
    """
    The project a request is asking about, if the caller may see it.

    get_active_project loads a project by id alone, so a caller can name a draft project
    they are not a member of and have it scoped to. Anything that scopes by project has to
    check visibility itself until that helper does.
    """
    from ami.base.views import get_active_project

    if request is None:
        return None
    project = get_active_project(request=request, required=False)
    if project is None:
        return None
    return Project.objects.visible_for_user(request.user).filter(pk=project.pk).first()


# How "best" is decided, in one place so the single-list lookup and the list page cannot
# drift. Ranked on the per-species average rather than the plain share: trap data is
# long-tailed, so a model that only handles the common species would otherwise win.
BEST_MODEL_ORDERING = ("-macro_accuracy", "-micro_accuracy")


def best_evaluation_for_taxa_list(
    taxa_list: TaxaList, project: Project | None = None, user=None
) -> AlgorithmEvaluation | None:
    """The algorithm that scores highest on the species in this list."""
    # No .distinct(): the join repeats an evaluation once per species it scored in the list,
    # which cannot change which row sorts first.
    rows = AlgorithmEvaluation.objects.filter(
        taxa__taxon__lists=taxa_list, occurrence_set__in=visible_sets(project, user)
    )
    return rows.select_related("algorithm", "occurrence_set").order_by(*BEST_MODEL_ORDERING).first()


def annotate_best_model(taxa_lists: models.QuerySet, project: Project | None = None, user=None) -> models.QuerySet:
    """
    Attach each list's best-scoring evaluation, for a page of lists.

    Correlated subqueries rather than a lookup per row: every list on the page renders its
    best model, so a per-row lookup costs one query each.
    """
    best = AlgorithmEvaluation.objects.filter(taxa__taxon__lists=models.OuterRef("pk"))
    best = best.filter(occurrence_set__in=visible_sets(project, user)).order_by(*BEST_MODEL_ORDERING)
    return taxa_lists.annotate(
        best_algorithm_id=models.Subquery(best.values("algorithm_id")[:1]),
        best_algorithm_name=models.Subquery(best.values("algorithm__name")[:1]),
        best_micro_accuracy=models.Subquery(best.values("micro_accuracy")[:1]),
        best_macro_accuracy=models.Subquery(best.values("macro_accuracy")[:1]),
        best_occurrence_set_name=models.Subquery(best.values("occurrence_set__name")[:1]),
    )


def performance_for_taxon(taxon: Taxon, project: Project | None = None, user=None) -> list[dict[str, typing.Any]]:
    """
    How each algorithm has done on one species.

    The breakdown the taxon page shows: one row per algorithm that has been scored on a set
    containing this species.
    """
    rows = TaxonEvaluation.objects.filter(taxon=taxon, evaluation__occurrence_set__in=visible_sets(project, user))
    rows = rows.select_related("evaluation__algorithm", "evaluation__occurrence_set").order_by("-accuracy")
    return [
        {
            "algorithm": {
                "id": row.evaluation.algorithm_id,
                "name": row.evaluation.algorithm.name,
                "key": row.evaluation.algorithm.key,
                "version": row.evaluation.algorithm.version,
            },
            "occurrence_set": {
                "id": row.evaluation.occurrence_set_id,
                "name": row.evaluation.occurrence_set.name,
            },
            "accuracy": row.accuracy,
            "occurrences_scored": row.occurrences_scored,
            "correct": row.correct,
            "overall_accuracy": row.evaluation.micro_accuracy,
            "overall_accuracy_by_species": row.evaluation.macro_accuracy,
        }
        for row in rows
    ]


def latest_evaluations(
    algorithm: Algorithm, limit: int = DEFAULT_EVALUATION_LIMIT, project: Project | None = None, user=None
) -> list[dict[str, typing.Any]]:
    """
    What this algorithm has scored, most recent first. Shown on its details panel.

    Read through the related manager without filtering or reordering, so a list view that
    prefetched the evaluations is served from that cache instead of one query per row.
    """
    rows = sorted(algorithm.evaluations.all(), key=lambda row: row.created_at, reverse=True)
    # Filtered in Python, not SQL, to keep using the prefetched cache above.
    allowed = set(visible_sets(project, user).values_list("pk", flat=True))
    rows = [row for row in rows if row.occurrence_set_id in allowed]
    rows = rows[:limit]
    return [
        {
            "id": row.pk,
            "occurrence_set": {"id": row.occurrence_set_id, "name": row.occurrence_set.name},
            "accuracy": row.micro_accuracy,
            "accuracy_by_species": row.macro_accuracy,
            "occurrences_scored": row.occurrences_scored,
            "occurrences_skipped": row.occurrences_skipped,
            "species_scored": row.species_scored,
            "created_at": row.created_at,
        }
        for row in rows
    ]
