from rest_framework.pagination import LimitOffsetPagination

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
