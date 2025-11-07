import collections.abc

from django.core.paginator import EmptyPage, PageNotAnInteger
from django.utils.translation import gettext_lazy as _
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response
from rest_framework.utils.urls import remove_query_param, replace_query_param

from .permissions import add_collection_level_permissions


class LimitOffsetPaginationWithPermissions(LimitOffsetPagination):
    def get_paginated_response(self, data):
        model = self._get_current_model()
        project = self._get_project()
        paginated_response = super().get_paginated_response(data=data)
        paginated_response.data = add_collection_level_permissions(
            user=self.request.user, response_data=paginated_response.data, model=model, project=project
        )
        return paginated_response

    def _get_current_model(self):
        """
        Retrieve the current model from the view.
        """
        view = self.request.parser_context.get("view")
        if view and hasattr(view, "queryset"):
            queryset = view.queryset
            if queryset is not None:
                return queryset.model
        return None

    def _get_project(self):
        view = self.request.parser_context.get("view")
        if hasattr(view, "get_active_project"):
            return view.get_active_project()
        return None


class CountlessPage(collections.abc.Sequence):
    def __init__(self, object_list, number, page_size):
        self.object_list = object_list
        self.number = number
        self.page_size = page_size

        if not isinstance(self.object_list, list):
            self.object_list = list(self.object_list)

        self._has_next = len(self.object_list) > len(self.object_list[: self.page_size])
        self._has_previous = self.number > 1

    def __repr__(self):
        return "<Page %s>" % self.number

    def __len__(self):
        return len(self.object_list)

    def __getitem__(self, index):
        if not isinstance(index, (int, slice)):
            raise TypeError
        return self.object_list[index]

    def has_next(self):
        return self._has_next

    def has_previous(self):
        return self._has_previous

    def has_other_pages(self):
        return self.has_next() or self.has_previous()

    def next_page_number(self):
        if self.has_next():
            return self.number + 1
        else:
            raise EmptyPage(_("Next page does not exist"))

    def previous_page_number(self):
        if self.has_previous():
            return self.number - 1
        else:
            raise EmptyPage(_("Previous page does not exist"))


class CountlessPaginator:
    def __init__(self, object_list, per_page) -> None:
        self.object_list = object_list
        self.per_page = per_page

    def validate_number(self, number):
        try:
            if isinstance(number, float) and not number.is_integer():
                raise ValueError
            number = int(number)
        except (TypeError, ValueError):
            raise PageNotAnInteger(_("Page number is not an integer"))
        if number < 1:
            raise EmptyPage(_("Page number is less than 1"))
        return number

    def get_page(self, number):
        try:
            number = self.validate_number(number)
        except (PageNotAnInteger, EmptyPage):
            number = 1
        return self.page(number)

    def page(self, number):
        number = self.validate_number(number)
        bottom = (number - 1) * self.per_page
        top = bottom + self.per_page + 1
        return CountlessPage(self.object_list[bottom:top], number, self.per_page)


class CountlessLimitOffsetPagination(LimitOffsetPagination):
    """
    DRF paginator that avoids expensive COUNT queries.

    Instead of returning a total count, it only returns:
    - next: URL to next page (if there are more results)
    - previous: URL to previous page (if not on first page)
    - results: the actual data

    This is much faster for large datasets where COUNT queries are slow,
    especially with complex filters and joins.
    """

    def paginate_queryset(self, queryset, request, view=None):
        self.request = request
        self.limit = self.get_limit(request)
        if self.limit is None:
            return None

        self.offset = self.get_offset(request)

        # Fetch one extra item to check if there's a next page
        self.queryset = queryset[self.offset : self.offset + self.limit + 1]
        items = list(self.queryset)

        # Check if there are more items
        self.has_next = len(items) > self.limit

        # Return only the requested number of items
        return items[: self.limit]

    def get_paginated_response(self, data):
        return Response({"next": self.get_next_link(), "previous": self.get_previous_link(), "results": data})

    def get_next_link(self):
        if not self.has_next:
            return None

        url = self.request.build_absolute_uri()
        offset = self.offset + self.limit
        return replace_query_param(url, self.offset_query_param, offset)

    def get_previous_link(self):
        if self.offset <= 0:
            return None

        url = self.request.build_absolute_uri()

        if self.offset - self.limit <= 0:
            # First page - remove offset param
            return remove_query_param(url, self.offset_query_param)

        offset = self.offset - self.limit
        return replace_query_param(url, self.offset_query_param, offset)
