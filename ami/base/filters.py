from django import forms
from django.core.exceptions import ValidationError
from django.db.models import F, OrderBy
from django.forms import FloatField, IntegerField
from django_filters import filters as base_filters
from django_filters.rest_framework import MultipleChoiceFilter, NumberFilter
from rest_framework.filters import BaseFilterBackend, OrderingFilter


class IntegerListField(forms.Field):
    """Whole numbers from a repeated query parameter (``?algorithm=1&algorithm=2``) or a JSON list.

    A single value is read as a list of one. Blank values are skipped; anything else that is not a
    whole number is refused, so the API answers 400 rather than failing in the database.
    """

    widget = forms.MultipleHiddenInput  # Reads every value of a repeated parameter.

    def to_python(self, value):
        if value in self.empty_values:
            return []
        items = value if isinstance(value, (list, tuple)) else [value]
        number = IntegerField()
        return [number.clean(item) for item in items if item not in ("", None)]


class QueryBooleanField(forms.Field):
    """A true or false query parameter that refuses any other value.

    Accepts ``true``/``false`` and ``1``/``0`` in any case, or a JSON boolean. A parameter that is
    present with an empty value (``?verified=``) means false, as Django's ``BooleanField`` reads it;
    an absent parameter is None, so the filter is not applied.
    """

    TRUE_VALUES = ("true", "1")
    FALSE_VALUES = ("false", "0", "")

    def to_python(self, value):
        if value is None or isinstance(value, bool):
            return value
        if isinstance(value, str):
            text = value.strip().lower()
            if text in self.TRUE_VALUES:
                return True
            if text in self.FALSE_VALUES:
                return False
        raise ValidationError("Enter true or false.", code="invalid")


class IntegerListFilter(MultipleChoiceFilter):
    """A filter on several ids, given by repeating the parameter, with no list of choices.

    Based on ``MultipleChoiceFilter`` so the OpenAPI schema shows a repeatable parameter typed from
    the model field at ``field_name``. Use it with ``method=``.
    """

    field_class = IntegerListField


class QueryBooleanFilter(base_filters.BooleanFilter):
    """A filter that takes ``true`` or ``false`` and answers 400 for any other value.

    Based on django-filter's own ``BooleanFilter``, not the REST framework one, whose widget turns
    unknown values into "no filter" before this field can refuse them.
    """

    field_class = QueryBooleanField


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
