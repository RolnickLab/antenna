import logging

from rest_framework import generics
from rest_framework.response import Response

from ami.base.views import ProjectMixin
from ami.users.api.serializers import ProjectMemberSerializer, ProjectRoleSerializer
from ami.users.roles import Role

logger = logging.getLogger(__name__)


class ProjectRolesView(ProjectMixin, generics.ListAPIView):
    require_project = True
    # permission_classes = [IsProjectMember]
    serializer_class = ProjectRoleSerializer

    def get(self, request, *args, **kwargs):
        roles = Role.get_supported_roles()
        return Response(roles)


class ProjectMembersView(ProjectMixin, generics.ListAPIView):
    require_project = True
    # permission_classes = [IsProjectMember]

    serializer_class = ProjectMemberSerializer

    def get(self, request, *args, **kwargs):
        project = self.get_active_project()
        logger.info(f"Fetching members for project {project}")

        members = project.members.all()  # type: ignore

        results = []
        for user in members:
            role = Role.get_user_role(project, user)
            results.append({"user": user, "role": role})

        serializer = ProjectMemberSerializer(results, many=True)
        return Response(serializer.data)
