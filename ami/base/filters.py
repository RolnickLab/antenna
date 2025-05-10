from django.db.models import F, OrderBy
from django.forms import FloatField
from rest_framework.filters import BaseFilterBackend, OrderingFilter


class NullsLastOrderingFilter(OrderingFilter):
    def get_ordering(self, request, queryset, view):
        values = super().get_ordering(request, queryset, view)
        if not values:
            return values
        return [OrderBy(F(value.lstrip("-")), descending=value.startswith("-"), nulls_last=True) for value in values]


class ThresholdFilter(BaseFilterBackend):
    """
    Filter a numeric field by a minimum value.

    Usage:

    Filter occurrences by their determination score:
    GET /occurrences/?score=0.5
    This will return all occurrences with a determination score greater than or equal to 0.5.

    Customize the query_param and filter_param to match your API and model fields using
    the create method.

    Example:

    DeterminationScoreFilter = ThresholdFilter.create(
        query_param="classification_treshold",
        filter_param="determination_score",
    )
    OODScoreFilter = ThresholdFilter.create("determination_ood_score")

    class OccurrenceViewSet(DefaultViewSet):
        filter_backends = DefaultViewSetMixin.filter_backends + [
            DeterminationScoreFilter,
            OODScoreFilter,
        ]
    """

    query_param = "score"
    filter_param = "score"

    def filter_queryset(self, request, queryset, view):
        value = FloatField(required=False).clean(request.query_params.get(self.query_param))
        if value:
            filters = {f"{self.filter_param}__gte": value}
            queryset = queryset.filter(**filters)
        return queryset

    @classmethod
    def create(cls, query_param: str, filter_param: str | None = None) -> type["ThresholdFilter"]:
        class_name = f"{cls.__name__}_{query_param}"
        if filter_param is None:
            filter_param = query_param
        return type(
            class_name,
            (cls,),
            {
                "query_param": query_param,
                "filter_param": filter_param,
            },
        )
