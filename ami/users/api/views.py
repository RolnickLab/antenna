import logging

from django.db import transaction
from rest_framework import viewsets
from rest_framework.response import Response

from ami.base.permissions import IsActiveStaffOrReadOnly, ObjectPermission
from ami.base.views import ProjectMixin
from ami.main.api.views import DefaultViewSet
from ami.main.models import UserProjectMembership
from ami.users.api.serializers import (
    ProjectRoleSerializer,
    UserProjectMembershipListSerializer,
    UserProjectMembershipSerializer,
)
from ami.users.roles import Role

logger = logging.getLogger(__name__)


class ProjectRolesViewSet(viewsets.ViewSet, ProjectMixin):
    require_project = True
    serializer_class = ProjectRoleSerializer
    permission_classes = [IsActiveStaffOrReadOnly]

    def list(self, request):
        roles = Role.get_supported_roles()
        serializer = ProjectRoleSerializer(roles, many=True)
        return Response(serializer.data)


class UserProjectMembershipViewSet(DefaultViewSet, ProjectMixin):
    require_project = True
    queryset = UserProjectMembership.objects.all()
    permission_classes = [ObjectPermission]

    def get_queryset(self):
        project = self.get_active_project()
        return UserProjectMembership.objects.filter(project=project).select_related("user")

    def get_serializer_class(self):
        if self.action == "list":
            return UserProjectMembershipListSerializer
        return UserProjectMembershipSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["project"] = self.get_active_project()
        return ctx

    def perform_create(self, serializer):
        project = self.get_active_project()
        user = serializer._validated_user
        role_cls = serializer._validated_role_cls
        with transaction.atomic():
            membership = serializer.save(project=project)
            user = membership.user

            # unassign all existing roles for this project
            for r in Role.__subclasses__():
                r.unassign_user(user, project)

            # assign new role
            role_cls.assign_user(user, project)

    def perform_update(self, serializer):
        membership = self.get_object()
        project = membership.project
        user = serializer._validated_user if hasattr(serializer, "_validated_user") else membership.user
        role_cls = serializer._validated_role_cls
        with transaction.atomic():
            membership.user = user
            membership.save()

            for r in Role.__subclasses__():
                r.unassign_user(user, project)

            role_cls.assign_user(user, project)

    def perform_destroy(self, instance):
        user = instance.user
        project = instance.project

        with transaction.atomic():
            # remove roles for this project
            for r in Role.__subclasses__():
                r.unassign_user(user, project)

            instance.delete()
