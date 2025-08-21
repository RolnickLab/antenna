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

        param = "project_id"

        project_id = None
        # Extract from URL `/projects/` is in the url path
        if "/projects/" in self.request.path:
            project_id = self.kwargs.get("pk")

        # If not in URL, try query parameters
        if not project_id:
            # Look for project_id in GET query parameters or POST data
            # POST data returns a list of ints, but QueryDict.get() returns a single value
            project_id = self.request.query_params.get(param) or self.request.data.get(param)

            project_id = SingleParamSerializer[int].clean(
                param_name=param,
                field=serializers.IntegerField(required=self.require_project, min_value=0),
                data={param: project_id} if project_id else {},
            )

        return get_object_or_404(Project, id=project_id) if project_id else None
