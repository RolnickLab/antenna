"""Metadata classes for DRF OPTIONS responses.

DRF's default ``SimpleMetadata`` only emits serializer field schema under
``actions.POST`` / ``actions.PUT`` — write operations. Read-only endpoints
(stats actions, scalar aggregates) return just ``name`` + ``description`` on
OPTIONS, so their ``help_text=`` annotations on response serializers are
invisible to clients.

``ResponseSchemaMetadata`` adds ``actions.GET`` carrying the response
serializer's field info (``type``, ``label``, ``help_text``, etc.), so
frontends can fetch one OPTIONS request per stats endpoint and render
tooltips / labels from the field metadata without hardcoding copy.
"""

from __future__ import annotations

import typing

from rest_framework.metadata import SimpleMetadata


class ResponseSchemaMetadata(SimpleMetadata):
    """Adds ``actions.GET`` with the response serializer's field schema.

    Falls back gracefully if the view doesn't expose a serializer for GET
    (anonymous endpoints, raw responses) — in that case the OPTIONS body
    is unchanged from ``SimpleMetadata``'s default.
    """

    def determine_metadata(self, request, view) -> dict[str, typing.Any]:
        metadata = super().determine_metadata(request, view)
        if "GET" in view.allowed_methods and hasattr(view, "get_serializer"):
            try:
                serializer = view.get_serializer()
            except Exception:
                return metadata
            actions = metadata.setdefault("actions", {})
            actions.setdefault("GET", self.get_serializer_info(serializer))
        return metadata
