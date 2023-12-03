from django.db.models import F, OrderBy
from rest_framework.filters import OrderingFilter


class NullsLastOrderingFilter(OrderingFilter):
    def get_ordering(self, request, queryset, view):
        values = super().get_ordering(request, queryset, view)
        if not values:
            return values
        return [OrderBy(F(value.lstrip("-")), descending=value.startswith("-"), nulls_last=True) for value in values]
