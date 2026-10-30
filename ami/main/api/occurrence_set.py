"""
Occurrence set choices for the retraining job form's picker.

A stop-gap until #1544 (the occurrence set API) is rebuilt on #1543. It serves only
``occurrences/sets/choices``, at the route and in the shape #1544 uses, so #1544 can
replace this module without the form changing.
"""

from drf_spectacular.utils import extend_schema
from rest_framework import exceptions as api_exceptions
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from ami.base.views import ProjectMixin
from ami.main.api.schemas import project_id_doc_param
from ami.main.api.views import ChoicesPagination
from ami.main.models import Project
from ami.main.models_future.occurrence_set import OccurrenceSet


class OccurrenceSetChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = OccurrenceSet
        fields = ["id", "name", "method", "updated_at"]


class OccurrenceSetViewSet(ProjectMixin, viewsets.GenericViewSet):
    queryset = OccurrenceSet.objects.all()
    serializer_class = OccurrenceSetChoiceSerializer
    require_project = True

    @extend_schema(parameters=[project_id_doc_param], responses=OccurrenceSetChoiceSerializer(many=True))
    @action(detail=False, methods=["get"], name="choices")
    def choices(self, request: Request) -> Response:
        """Occurrence sets of one project, most recently updated first, in one response."""
        project = self.get_active_project()
        if not Project.objects.visible_for_user(request.user).filter(pk=project.pk).exists():
            raise api_exceptions.NotFound("Project not found.")
        queryset = OccurrenceSet.objects.filter(project=project).order_by("-updated_at", "-pk")
        paginator = ChoicesPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = self.get_serializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
