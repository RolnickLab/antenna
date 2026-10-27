import datetime

from django.db.models import F, OrderBy
from django.forms import FloatField, IntegerField
from django_filters.rest_framework import NumberFilter
from rest_framework.filters import BaseFilterBackend, OrderingFilter

from .serializers import DateRangeFilterSerializer


class RelatedIdFilter(NumberFilter):
    """Filter a foreign key by integer id without enumerating the related table.

    django-filter's auto-generated ``ModelChoiceFilter`` renders the browsable API's
    filter form as a ``<select>`` with one option per row of the related table, which
    times out on production-sized tables. A plain number input accepts the same
    ``?<field>=<id>`` query parameter. The form field is an ``IntegerField`` rather than
    ``NumberFilter``'s ``DecimalField`` so a fractional value is rejected with 400 instead
    of being truncated to a different, valid id. See #1391 and
    https://www.django-rest-framework.org/topics/browsable-api/#handling-choicefield-with-large-numbers-of-items
    """

    field_class = IntegerField


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
        query_param="classification_threshold",
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


def get_date_range_bounds(query_params) -> tuple[datetime.datetime | None, datetime.datetime | None]:
    """
    Turn ``date_start`` / ``date_end`` (both inclusive) into a half-open ``[start, end)`` datetime range.

    Timestamps are the station's local capture time (USE_TZ is off), so dates match what users see.
    Comparing against datetimes, rather than casting with ``__date``, keeps the timestamp indexes usable.
    """
    serializer = DateRangeFilterSerializer(data=query_params)
    serializer.is_valid(raise_exception=True)
    start_date = serializer.validated_data.get("date_start")
    end_date = serializer.validated_data.get("date_end")
    start = datetime.datetime.combine(start_date, datetime.time.min) if start_date else None
    end = datetime.datetime.combine(end_date + datetime.timedelta(days=1), datetime.time.min) if end_date else None
    return start, end


class DateRangeFilter(BaseFilterBackend):
    """
    Filter records whose date field falls within ``date_start`` / ``date_end`` (both inclusive).

    Use a single-valued field. A multi-valued path such as ``detections__timestamp`` makes two joins,
    which repeats rows and matches records whose values only straddle the range.

    Example:

    CaptureDateFilter = DateRangeFilter.create("timestamp")
    SessionDateFilter = DateRangeFilter.create("start")
    """

    field = "timestamp"

    def filter_queryset(self, request, queryset, view):
        start, end = get_date_range_bounds(request.query_params)
        if start:
            queryset = queryset.filter(**{f"{self.field}__gte": start})
        if end:
            queryset = queryset.filter(**{f"{self.field}__lt": end})
        return queryset

    def get_schema_operation_parameters(self, view):
        return [
            {
                "name": name,
                "required": False,
                "in": "query",
                "description": description,
                "schema": {"type": "string", "format": "date"},
            }
            for name, description in [
                ("date_start", "Only records on or after this date (YYYY-MM-DD, local capture time)."),
                ("date_end", "Only records on or before this date (YYYY-MM-DD, local capture time)."),
            ]
        ]

    @classmethod
    def create(cls, field: str) -> type["DateRangeFilter"]:
        return type(f"{cls.__name__}_{field}", (cls,), {"field": field})
