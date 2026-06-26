from django.core.exceptions import ValidationError
from django.forms import BooleanField
from rest_framework.pagination import LimitOffsetPagination, remove_query_param, replace_query_param
from rest_framework.response import Response

from .permissions import add_collection_level_permissions

# Query parameter name used to opt out of the total count in paginated list responses.
# Pass ``?with_counts=false`` to skip the COUNT(*) query entirely on large tables.
WITH_TOTAL_COUNT_PARAM = "with_counts"


class LimitOffsetPaginationWithPermissions(LimitOffsetPagination):
    """
    LimitOffsetPagination with a precision cap on the total count.

    The total ``count`` is exact for result sets up to
    ``COUNT_PRECISION_THRESHOLD`` rows. Beyond that, counting the full set means
    scanning a large slice of a big table on every page load, so the count is
    capped: the response returns the threshold value with
    ``count_is_exact: false``, which the UI renders as e.g. "10,000+". That
    number is a lower bound, not the true total, so ``next`` / ``previous`` links
    are computed from a one-extra-row probe rather than from ``count``.

    Callers that don't need a total at all can pass ``?with_counts=false`` to
    skip the count query entirely and receive ``count: null`` (with
    ``count_is_exact: null``). ``next`` / ``previous`` still work via the probe.

    Response fields:
      - ``count``: the exact total, the precision cap (a lower bound), or null.
      - ``count_is_exact``: true when ``count`` is exact, false when it is the
        capped lower bound, null when counting was skipped.
    """

    # Sentinel returned by ``_get_capped_count`` when the result set is larger
    # than the precision threshold, so the exact total is deliberately not run.
    _OVER_CAP = object()

    # Largest result set we count exactly. Past this the count query would scan
    # an unbounded slice of a large table, so we cap precision instead.
    COUNT_PRECISION_THRESHOLD = 10_000

    # Per-request flag; the default is overwritten in ``paginate_queryset``.
    count_is_exact = True

    def paginate_queryset(self, queryset, request, view=None):
        self.request = request
        self.limit = self.get_limit(request)
        if self.limit is None:
            return None
        self.offset = self.get_offset(request)

        if self._should_skip_count(request):
            # Opt-out: no count at all. Probe one extra row for the next link.
            self.count = None
            self.count_is_exact = None
            page = list(queryset[self.offset : self.offset + self.limit + 1])
            self._has_next = len(page) > self.limit
            return page[: self.limit]

        capped = self._get_capped_count(queryset)
        if capped is self._OVER_CAP:
            # Over the precision cap: report the threshold as an approximate
            # lower bound. It must not drive next/previous (the true total is
            # higher), so fall back to the probe-based links.
            self.count = self.COUNT_PRECISION_THRESHOLD
            self.count_is_exact = False
            page = list(queryset[self.offset : self.offset + self.limit + 1])
            self._has_next = len(page) > self.limit
            return page[: self.limit]

        # Exact count.
        self.count = capped
        self.count_is_exact = True
        if self.count > self.limit and self.template is not None:
            self.display_page_controls = True
        if self.count == 0 or self.offset > self.count:
            return []
        return list(queryset[self.offset : self.offset + self.limit])

    def get_next_link(self):
        # When the count is not exact (opt-out or over the cap) the total can't
        # tell us whether a next page exists, so use the one-extra-row probe.
        if not self.count_is_exact:
            if not self._has_next:
                return None
            url = self.request.build_absolute_uri()
            url = replace_query_param(url, self.limit_query_param, self.limit)
            return replace_query_param(url, self.offset_query_param, self.offset + self.limit)
        return super().get_next_link()

    def get_previous_link(self):
        # Previous link logic does not depend on the total count.
        if not self.count_is_exact:
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
        response = Response(
            {
                "count": self.count,
                "count_is_exact": self.count_is_exact,
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
        # count is the exact total, the precision cap (a lower bound), or null
        # when the caller passed with_counts=false.
        paginated_schema["properties"]["count"]["nullable"] = True
        paginated_schema["properties"]["count_is_exact"] = {
            "type": "boolean",
            "nullable": True,
            "description": (
                "True when `count` is exact; false when it is the precision cap "
                '(a lower bound, render as e.g. "10,000+"); null when the count '
                "was skipped via with_counts=false."
            ),
        }
        return paginated_schema

    def _get_capped_count(self, queryset):
        """
        Run a bounded COUNT(*) that stops scanning after
        ``COUNT_PRECISION_THRESHOLD`` rows. Returns the exact count when the
        result set is within the cap, or the ``_OVER_CAP`` sentinel when it is
        larger so the caller reports an approximate lower bound instead.

        Django translates ``queryset.order_by()[:N].count()`` into::

            SELECT COUNT(*) FROM (SELECT 1 … LIMIT N) sub

        Stripping the queryset's ordering is essential to the bound. An
        ``ORDER BY`` that is not served by an index forces Postgres to top-N
        sort the entire filtered set before the ``LIMIT`` can stop it, which
        defeats the early exit and can make this capped count slower than an
        uncapped one. With the ordering removed the scan stops after at most N
        matching rows, so the cost is O(N) regardless of total table size. The
        order is irrelevant to a count, so dropping it changes only performance.
        """
        # Fetch one extra row beyond the threshold so we can distinguish
        # "exactly N rows" (exact count) from "more than N rows" (over the cap).
        # Drop the list view's ordering first so the LIMIT short-circuits
        # instead of sorting.
        capped = queryset.order_by()[: self.COUNT_PRECISION_THRESHOLD + 1].count()
        if capped <= self.COUNT_PRECISION_THRESHOLD:
            return capped
        return self._OVER_CAP

    def _should_skip_count(self, request) -> bool:
        """Return True when the caller has explicitly opted out of the total count."""
        raw = request.query_params.get(WITH_TOTAL_COUNT_PARAM, None)
        if raw is None:
            return False
        try:
            return not BooleanField(required=False).clean(raw)
        except ValidationError:
            return False

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
