from django.db.models import Count, Q, QuerySet

from ami.main.models import Project, User


def top_identifiers_for_project(project: Project, limit: int = 5) -> QuerySet[User]:
    """Users ranked by distinct occurrences they identified in this project.

    Counts distinct occurrences, not raw Identification rows: a user revising
    their own ID on the same occurrence is one occurrence-identification, not two.
    """
    return (
        User.objects.filter(identifications__occurrence__project=project)
        .annotate(
            identification_count=Count(
                "identifications__occurrence",
                filter=Q(identifications__occurrence__project=project),
                distinct=True,
            )
        )
        .filter(identification_count__gt=0)
        .order_by("-identification_count")[:limit]
    )
