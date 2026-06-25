import logging

from django.db import transaction
from rest_framework.response import Response
from rest_framework.views import APIView

from ami.base.permissions import UserMembershipPermission
from ami.base.views import ProjectMixin
from ami.main.api.views import DefaultViewSet
from ami.main.models import UserProjectMembership
from ami.users.api.serializers import (
    ProjectRoleSerializer,
    UserProjectMembershipListSerializer,
    UserProjectMembershipSerializer,
)
from ami.users.roles import BasicMember, Role
from ami.users.signals import suppress_membership_signal

logger = logging.getLogger(__name__)


class RolesAPIView(APIView):
    def get(self, request, **kwargs):
        roles = Role.get_supported_roles()
        serializer = ProjectRoleSerializer(roles, many=True)
        return Response(serializer.data)


class UserProjectMembershipViewSet(DefaultViewSet, ProjectMixin):
    require_project = True
    queryset = UserProjectMembership.objects.all()
    permission_classes = [UserMembershipPermission]
    ordering_fields = ["created_at", "updated_at", "user__email"]

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
        role_cls = serializer._validated_role_cls
        with transaction.atomic():
            membership = serializer.save(project=project)
            user = membership.user

            # Suppress the signal so it doesn't create/delete memberships in
            # response to the group changes we're making intentionally.
            with suppress_membership_signal():
                for r in Role.__subclasses__():
                    r.unassign_user(user, project)
                role_cls.assign_user(user, project)
                if role_cls is not BasicMember:
                    BasicMember.assign_user(user, project)

    def perform_update(self, serializer):
        membership = self.get_object()
        project = membership.project
        old_user = membership.user
        user = getattr(serializer, "_validated_user", None) or membership.user
        role_cls = getattr(serializer, "_validated_role_cls", None)
        if not role_cls:
            raise ValueError("role_cls not set during validation")

        with transaction.atomic():
            membership.user = user
            membership.save()

            with suppress_membership_signal():
                # If user changed, revoke all roles from the old user
                if old_user != user:
                    for r in Role.__subclasses__():
                        r.unassign_user(old_user, project)

                # Unassign all roles, assign the chosen role, then BasicMember
                for r in Role.__subclasses__():
                    r.unassign_user(user, project)
                role_cls.assign_user(user, project)
                if role_cls is not BasicMember:
                    BasicMember.assign_user(user, project)

    def perform_destroy(self, instance):
        user = instance.user
        project = instance.project

        with transaction.atomic():
            with suppress_membership_signal():
                for r in Role.__subclasses__():
                    r.unassign_user(user, project)

            instance.delete()
