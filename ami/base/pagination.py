from django.core.exceptions import ValidationError
from django.forms import BooleanField
from rest_framework.pagination import LimitOffsetPagination, remove_query_param, replace_query_param
from rest_framework.response import Response

from .permissions import add_collection_level_permissions

# Query parameter name used to request the total count in paginated list responses.
# When not provided or set to false, COUNT(*) is skipped for performance on large tables.
WITH_TOTAL_COUNT_PARAM = "with_counts"


class LimitOffsetPaginationWithPermissions(LimitOffsetPagination):
    """
    LimitOffsetPagination that optionally skips the expensive COUNT(*) query.

    By default the total count is not computed (``with_counts`` defaults to
    ``False``).  Callers that need the total for pagination UI can pass
    ``?with_counts=true``; all other callers get a fast response where
    ``count`` is ``null`` in the JSON payload.

    When the count is skipped, ``next`` / ``previous`` cursor links are still
    computed correctly by fetching one extra row to detect whether a following
    page exists.
    """

    # Sentinel used internally when COUNT(*) is skipped.
    _SKIP_COUNT = object()

    # Maximum rows scanned when with_counts=true is requested.  If the filtered
    # result set contains at least this many rows the full COUNT(*) is abandoned
    # and the response falls back to ``count: null``.
    LARGE_QUERYSET_THRESHOLD = 10_000

    def paginate_queryset(self, queryset, request, view=None):
        self.request = request
        self.limit = self.get_limit(request)
        if self.limit is None:
            return None
        self.offset = self.get_offset(request)

        if self._should_skip_count(request):
            # Fetch one extra item to detect whether a next page exists without
            # issuing a COUNT(*) on the full table.
            page = list(queryset[self.offset : self.offset + self.limit + 1])
            self._has_next = len(page) > self.limit
            self.count = self._SKIP_COUNT  # type: ignore[assignment]
            return page[: self.limit]

        # with_counts=true path: attempt a capped count so we never run a
        # full COUNT(*) against a huge result set.
        self.count = self._get_capped_count(queryset)
        if self.count is self._SKIP_COUNT:
            # Result set exceeds LARGE_QUERYSET_THRESHOLD - fall back to the
            # probe-based fast path (count stays null in the response).
            page = list(queryset[self.offset : self.offset + self.limit + 1])
            self._has_next = len(page) > self.limit
            return page[: self.limit]

        if self.count > self.limit and self.template is not None:
            self.display_page_controls = True
        if self.count == 0 or self.offset > self.count:
            return []
        return list(queryset[self.offset : self.offset + self.limit])

    def get_next_link(self):
        if self.count is self._SKIP_COUNT:
            if not self._has_next:
                return None
            url = self.request.build_absolute_uri()
            url = replace_query_param(url, self.limit_query_param, self.limit)
            return replace_query_param(url, self.offset_query_param, self.offset + self.limit)
        return super().get_next_link()

    def get_previous_link(self):
        # Previous link logic does not depend on the total count.
        if self.count is self._SKIP_COUNT:
            if self.offset <= 0:
                return None
            url = self.request.build_absolute_uri()
            url = replace_query_param(url, self.limit_query_param, self.limit)
            offset = max(0, self.offset - self.limit)
            if offset == 0:
                return remove_query_param(url, self.offset_query_param)
            return replace_query_param(url, self.offset_query_param, offset)
        return super().get_previous_link()

    def get_paginated_response(self, data):
        model = self._get_current_model()
        project = self._get_project()
        count = None if self.count is self._SKIP_COUNT else self.count
        response = Response(
            {
                "count": count,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
            }
        )
        response.data = add_collection_level_permissions(
            user=self.request.user, response_data=response.data, model=model, project=project
        )
        return response

    def get_paginated_response_schema(self, schema):
        paginated_schema = super().get_paginated_response_schema(schema)
        # Allow count to be null when WITH_TOTAL_COUNT_PARAM is not requested.
        paginated_schema["properties"]["count"]["nullable"] = True
        return paginated_schema

    def _get_capped_count(self, queryset):
        """
        Run a bounded COUNT(*) that stops scanning after ``LARGE_QUERYSET_THRESHOLD``
        rows.  Returns the exact count when the result set is small, or the
        ``_SKIP_COUNT`` sentinel when the threshold is reached so callers can
        fall back gracefully.

        Django translates ``queryset[:N].count()`` into::

            SELECT COUNT(*) FROM (SELECT … LIMIT N) sub

        which is always O(N) regardless of total table size.
        """
        # Fetch one extra row beyond the threshold so we can distinguish
        # "exactly N rows" (exact count returned) from "more than N rows"
        # (sentinel returned to avoid the full scan).
        capped = queryset[: self.LARGE_QUERYSET_THRESHOLD + 1].count()
        if capped <= self.LARGE_QUERYSET_THRESHOLD:
            return capped
        return self._SKIP_COUNT

    def _should_skip_count(self, request) -> bool:
        """Return True when the caller has not opted in to receiving the total count."""
        raw = request.query_params.get(WITH_TOTAL_COUNT_PARAM, None)
        if raw is None:
            return True
        try:
            return not BooleanField(required=False).clean(raw)
        except ValidationError:
            return True

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
