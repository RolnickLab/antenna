"""API for occurrence sets: named groups of occurrences that a project keeps and uses again.

See ``ami.main.models_future.occurrence_set.OccurrenceSet``.
"""

from __future__ import annotations

import typing

from django.db.models import QuerySet
from drf_spectacular.utils import extend_schema
from guardian.shortcuts import get_perms
from rest_framework import exceptions as api_exceptions
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from ami.base.permissions import ObjectPermission
from ami.base.serializers import DefaultSerializer, reverse_with_params
from ami.base.views import ProjectMixin
from ami.main.api.schemas import project_id_doc_param
from ami.main.api.serializers import UserNestedSerializer
from ami.main.api.views import ChoicesPagination, DefaultViewSet
from ami.main.models import Occurrence, Project
from ami.main.models_future.occurrence_set import OccurrenceSet
from ami.main.models_future.saved_set import SetRefused

# The most occurrences one add or remove request can name. A selection on the
# occurrence page is one page of results, far below this.
MAX_OCCURRENCE_IDS_PER_REQUEST = 1000


def refused(error: SetRefused) -> api_exceptions.ValidationError:
    return api_exceptions.ValidationError({"non_field_errors": [str(error)]})


class OccurrenceSetPermissionsMixin:
    """Adds ``user_permissions`` to each set, reading the user's project permissions once per project."""

    context: dict

    def get_permissions(self, instance: OccurrenceSet, instance_data: dict) -> dict:
        # DRF's ListSerializer reuses one child serializer for every row, so a cache on
        # `self` reads permissions once per project and request, not once per row.
        user = self.context["request"].user
        cache: dict[int, set[str]] = self.__dict__.setdefault("_permissions_by_project", {})
        if instance.project_id not in cache:
            if user.is_superuser:
                cache[instance.project_id] = {"create", "update", "delete"}
            else:
                cache[instance.project_id] = {
                    perm.split("_", 1)[0]
                    for perm in get_perms(user, instance.project)
                    if perm.endswith("_occurrenceset")
                }
        project_permissions = cache[instance.project_id]
        # The actions this user can take on this set now. Hand edits need "update" on a
        # set that is not frozen.
        permissions = project_permissions & {"update", "delete"}
        if "update" in project_permissions and not instance.is_frozen:
            permissions.add("freeze")
        if "create" in project_permissions:
            permissions.add("copy")
        instance_data["user_permissions"] = sorted(permissions)
        return instance_data


class OccurrenceSetNestedSerializer(OccurrenceSetPermissionsMixin, DefaultSerializer):
    class Meta:
        model = OccurrenceSet
        fields = [
            "id",
            "details",
            "name",
            "method",
            "populated_at",
            "frozen_at",
        ]


class OccurrenceSetSerializer(OccurrenceSetPermissionsMixin, DefaultSerializer):
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all())
    kwargs = serializers.JSONField(required=False)
    occurrences = serializers.SerializerMethodField()
    occurrences_count = serializers.IntegerField(read_only=True)
    frozen_by = UserNestedSerializer(read_only=True)
    copied_from = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = OccurrenceSet
        fields = [
            "id",
            "details",
            "name",
            "description",
            "project",
            "method",
            "kwargs",
            "occurrences",
            "occurrences_count",
            "populated_at",
            "frozen_at",
            "frozen_by",
            "copied_from",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["populated_at", "frozen_at", "copied_from"]

    def get_occurrences(self, obj: OccurrenceSet) -> str:
        """URL of the occurrence list narrowed to the members of this set."""
        return reverse_with_params(
            "occurrence-list",
            request=self.context.get("request"),
            params={"project_id": obj.project_id, "occurrence_set_id": obj.pk},
        )

    def validate_kwargs(self, kwargs: typing.Any) -> dict:
        # A manual set takes no arguments. Saved filters come with the filters method.
        if kwargs:
            raise serializers.ValidationError("A manual set takes no arguments.")
        return {}

    def validate(self, data: dict) -> dict:
        if self.instance and "project" in data and data["project"] != self.instance.project:
            # The members belong to the project.
            raise serializers.ValidationError({"project": "The project of an occurrence set cannot change."})
        return data


class OccurrenceSetMembershipSerializer(serializers.Serializer):
    occurrence_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
        max_length=MAX_OCCURRENCE_IDS_PER_REQUEST,
    )


class OccurrenceSetMembershipResponseSerializer(serializers.Serializer):
    occurrence_set = serializers.IntegerField()
    occurrences_count = serializers.IntegerField()


class OccurrenceSetCopySerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)


class OccurrenceSetViewSet(DefaultViewSet, ProjectMixin):
    """
    Endpoint for occurrence sets: named groups of occurrences that a project keeps and uses again.
    """

    queryset = OccurrenceSet.objects.all()
    serializer_class = OccurrenceSetSerializer
    permission_classes = [ObjectPermission]
    require_project = False
    require_project_for_list = True
    filterset_fields = ["method"]
    ordering_fields = ["id", "created_at", "updated_at", "name", "method", "frozen_at", "occurrences_count"]
    # Recently updated first, so a caller reading one page gets the sets a user is most likely to want.
    ordering = ["-updated_at"]

    def get_queryset(self) -> QuerySet:
        if self.action == "choices":
            # Picker choices are always scoped to one project.
            self.require_project = True
        query_set = super().get_queryset().select_related("project")
        project = self.get_active_project()
        if project:
            query_set = query_set.filter(project=project)
        if self.action == "choices":
            return query_set
        return query_set.select_related("frozen_by").with_occurrences_count()

    def _serialize(self, occurrence_set: OccurrenceSet) -> dict:
        """The set as the detail view returns it, with its member count."""
        return self.get_serializer(self.get_queryset().get(pk=occurrence_set.pk)).data

    @extend_schema(parameters=[project_id_doc_param])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(parameters=[project_id_doc_param], responses=OccurrenceSetNestedSerializer(many=True))
    @action(detail=False, methods=["get"], name="choices")
    def choices(self, request: Request) -> Response:
        """Choices for occurrence set filters and pickers: names and dates, enough that a dropdown never pages."""
        # Sorting by a count would fail here, since the counts are not annotated.
        self.ordering_fields = ["id", "created_at", "updated_at", "name", "method", "frozen_at"]
        queryset = self.filter_queryset(self.get_queryset())
        paginator = ChoicesPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = OccurrenceSetNestedSerializer(page, many=True, context=self.get_serializer_context())
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(request=None, responses=OccurrenceSetSerializer)
    @action(detail=True, methods=["post"], name="freeze")
    def freeze(self, request: Request, pk=None) -> Response:
        """Freeze the set for good. The members of a frozen set cannot change; copy it to change it."""
        occurrence_set: OccurrenceSet = self.get_object()
        try:
            occurrence_set.freeze(request.user)
        except SetRefused as e:
            raise refused(e)
        return Response(self._serialize(occurrence_set))

    @extend_schema(request=OccurrenceSetCopySerializer, responses={201: OccurrenceSetSerializer})
    @action(detail=True, methods=["post"], name="copy")
    def copy(self, request: Request, pk=None) -> Response:
        """Copy the set: same project, method, kwargs and members, not frozen. ``name`` is optional."""
        occurrence_set: OccurrenceSet = self.get_object()
        serializer = OccurrenceSetCopySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        copy = occurrence_set.copy(**serializer.validated_data)
        return Response(self._serialize(copy), status=status.HTTP_201_CREATED)

    def _get_occurrence_ids(self, occurrence_set: OccurrenceSet) -> list[int]:
        """The occurrence ids in the request, checked against the set's project with one query."""
        serializer = OccurrenceSetMembershipSerializer(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        occurrence_ids = set(serializer.validated_data["occurrence_ids"])
        found = set(
            Occurrence.objects.filter(project_id=occurrence_set.project_id, pk__in=occurrence_ids)
            .order_by()
            .values_list("pk", flat=True)
        )
        missing = sorted(occurrence_ids - found)
        if missing:
            raise api_exceptions.ValidationError(
                {"occurrence_ids": f"These occurrences are not in the project of this set: {missing}"}
            )
        return sorted(occurrence_ids)

    def _edit_members(self, edit: typing.Callable[[OccurrenceSet, list[int]], None]) -> Response:
        occurrence_set: OccurrenceSet = self.get_object()
        try:
            # Checked before the ids so the error names the real problem. The edit checks
            # again under a row lock.
            occurrence_set.check_editable_by_hand()
            occurrence_ids = self._get_occurrence_ids(occurrence_set)
            edit(occurrence_set, occurrence_ids)
        except SetRefused as e:
            raise refused(e)
        serializer = OccurrenceSetMembershipResponseSerializer(
            {"occurrence_set": occurrence_set.pk, "occurrences_count": occurrence_set.occurrences.count()}
        )
        return Response(serializer.data)

    @extend_schema(request=OccurrenceSetMembershipSerializer, responses=OccurrenceSetMembershipResponseSerializer)
    @action(detail=True, methods=["post"], name="add")
    def add(self, request: Request, pk=None) -> Response:
        """Add occurrences to the set. Occurrences that are already members stay as they are."""
        return self._edit_members(OccurrenceSet.add_occurrences)

    @extend_schema(request=OccurrenceSetMembershipSerializer, responses=OccurrenceSetMembershipResponseSerializer)
    @action(detail=True, methods=["post"], name="remove")
    def remove(self, request: Request, pk=None) -> Response:
        """Remove occurrences from the set. Occurrences that are not members are ignored."""
        return self._edit_members(OccurrenceSet.remove_occurrences)
