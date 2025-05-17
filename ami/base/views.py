import logging

import rest_framework.request
from django.shortcuts import get_object_or_404
from rest_framework import serializers

from ami.main.models import Project

logger = logging.getLogger(__name__)


class ProjectMixin:
    """
    Mixin to handle project_id fetching from query parameters or URL parameters.
    By default, project_id is required, but this can be overridden.
    """

    require_project = False  # Project is optional
    request: rest_framework.request.Request
    kwargs: dict

    def get_active_project(self) -> Project | None:
        from ami.base.serializers import SingleParamSerializer

        project_id = None
        # Extract from URL `/projects/` is in the url path
        if "/projects/" in self.request.path:
            project_id = self.kwargs.get("pk")

        # If not in URL, try query parameters
        if not project_id:
            if self.require_project:
                project_id = SingleParamSerializer[int].clean(
                    param_name="project_id",
                    field=serializers.IntegerField(required=self.require_project, min_value=0),
                    data=self.request.query_params,
                )

        return get_object_or_404(Project, id=project_id) if project_id else None
