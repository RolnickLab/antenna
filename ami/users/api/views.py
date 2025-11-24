import logging

from django.db import transaction
from rest_framework import viewsets
from rest_framework.response import Response

from ami.base.permissions import ProjectMemberPermissions
from ami.base.views import ProjectMixin
from ami.users.api.serializers import ProjectMemberSerializer, ProjectRoleSerializer
from ami.users.models import User
from ami.users.roles import Role

logger = logging.getLogger(__name__)


class ProjectRolesViewSet(ProjectMixin, viewsets.ViewSet):
    require_project = True
    serializer_class = ProjectRoleSerializer
    permission_classes = [ProjectMemberPermissions]

    def list(self, request):
        roles = Role.get_supported_roles()
        serializer = ProjectRoleSerializer(roles, many=True)
        return Response(serializer.data)


class ProjectMembersViewSet(ProjectMixin, viewsets.ViewSet):
    require_project = True
    permission_classes = [ProjectMemberPermissions]

    # GET /members/
    def list(self, request):
        project = self.get_active_project()
        logger.info(f"Fetching members for project {project}")
        results = [{"user": user, "role": self._get_primary_role(project, user)} for user in project.members.all()]
        serializer = ProjectMemberSerializer(results, many=True, context={"request": request})
        return Response(serializer.data)

    # POST /members/
    def create(self, request):
        project = self.get_active_project()

        serializer = ProjectMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        role_cls = serializer.validated_data["role"]

        with transaction.atomic():
            # Remove previous roles
            for r in Role.__subclasses__():
                r.unassign_user(user, project)
            role_cls.assign_user(user, project)
        return Response({"detail": "Member added"}, status=201)

    # PUT /members/{pk}/
    def update(self, request, pk=None):
        project = self.get_active_project()

        serializer = ProjectMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        role_cls = serializer.validated_data["role"]

        user = User.objects.filter(pk=pk).first()
        if not user:
            return Response({"detail": "User not found"}, status=404)

        with transaction.atomic():
            # Ensure user remains in project.members
            project.members.add(user)
            for r in Role.__subclasses__():
                r.unassign_user(user, project)
            role_cls.assign_user(user, project)
        return Response({"detail": "Role updated"})

    # DELETE /members/{user_id}/
    def destroy(self, request, pk=None):
        project = self.get_active_project()

        user = User.objects.filter(pk=pk).first()
        if not user:
            return Response({"detail": "User not found"}, status=404)

        with transaction.atomic():
            # Remove user from project.members M2M relation
            project.members.remove(user)  # type: ignore
            # Remove all roles for this project
            for role_cls in Role.__subclasses__():
                role_cls.unassign_user(user, project)

        return Response({"detail": "Member removed"})

    def _get_primary_role(self, project, user):
        """
        Returns a single primary role for the user, chosen based on
        the largest permission set among assigned roles.
        """
        roles = Role.get_user_roles(project, user)
        if not roles:
            return None

        # Pick the role with the largest permissions count
        best_role = max(roles, key=lambda role_cls: len(role_cls.permissions))
        return best_role.__name__
