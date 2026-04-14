"""
API key authentication for processing services.

Uses djangorestframework-api-key to provide key-based auth. Each ProcessingService
can have one or more API keys. When a request arrives with `Authorization: Api-Key <key>`,
the authentication class identifies the ProcessingService and sets request.auth to it.

Contains:
    - ProcessingServiceAPIKeyAuthentication: DRF auth backend
    - HasProcessingServiceAPIKey: DRF permission class

The ProcessingServiceAPIKey model lives in ami.ml.models.processing_service.
"""

import logging

from rest_framework import authentication, exceptions, permissions
from rest_framework_api_key.permissions import KeyParser

from ami.ml.models.processing_service import ProcessingServiceAPIKey

logger = logging.getLogger(__name__)


class ProcessingServiceAPIKeyAuthentication(authentication.BaseAuthentication):
    """
    DRF authentication class that identifies a ProcessingService from an API key.

    Sets:
        request.user = AnonymousUser (required by django-guardian/ObjectPermission)
        request.auth = ProcessingService instance

    This allows views to check `request.auth` to get the calling service,
    and permission classes to verify project access.
    """

    key_parser = KeyParser()

    def authenticate(self, request):
        key = self.key_parser.get(request)
        if not key:
            return None  # No Api-Key header; fall through to next auth class

        try:
            api_key = ProcessingServiceAPIKey.objects.get_from_key(key)
        except ProcessingServiceAPIKey.DoesNotExist:
            raise exceptions.AuthenticationFailed("Invalid API key.")

        if not api_key.is_valid:
            raise exceptions.AuthenticationFailed("API key has been revoked or expired.")

        from django.contrib.auth.models import AnonymousUser

        return (AnonymousUser(), api_key.processing_service)

    def authenticate_header(self, request):
        return "Api-Key"


class HasProcessingServiceAPIKey(permissions.BasePermission):
    """
    Allow access for requests authenticated with a ProcessingService API key.

    The auth backend places the ProcessingService on request.auth.
    This permission verifies project membership.

    Compose with ObjectPermission for endpoints used by both users and services:
        permission_classes = [ObjectPermission | HasProcessingServiceAPIKey]
    """

    def has_permission(self, request, view):
        from ami.ml.models.processing_service import ProcessingService

        if not isinstance(request.auth, ProcessingService):
            return False

        # For detail views (e.g. /jobs/{pk}/tasks/), defer project scoping
        # to has_object_permission where we can derive it from the object.
        # CONTRACT: all detail-level actions using this permission MUST call
        # self.get_object() so that DRF invokes has_object_permission().
        # Actions that fetch objects manually without get_object() will bypass
        # project-scoping checks.
        if view.kwargs.get("pk"):
            return True

        get_active_project = getattr(view, "get_active_project", None)
        if not callable(get_active_project):
            return False

        project = get_active_project()
        if not project:
            return False

        return request.auth.projects.filter(pk=project.pk).exists()

    def has_object_permission(self, request, view, obj):
        from ami.ml.models.processing_service import ProcessingService

        if not isinstance(request.auth, ProcessingService):
            return False

        ps = request.auth
        project = obj.get_project() if hasattr(obj, "get_project") else None
        if not project:
            return False
        return ps.projects.filter(pk=project.pk).exists()
