import logging
import secrets

from django.contrib.auth.models import AnonymousUser
from rest_framework.authentication import BaseAuthentication

logger = logging.getLogger(__name__)

API_KEY_PREFIX = "ant_ps_"


def generate_api_key() -> str:
    """Generate a prefixed API key for a processing service."""
    token = secrets.token_urlsafe(36)
    return f"{API_KEY_PREFIX}{token}"


class ProcessingServiceAPIKeyAuthentication(BaseAuthentication):
    """
    Authenticate processing services by API key.

    Expects: Authorization: Bearer ant_ps_...
    Returns: (AnonymousUser, ProcessingService) or None to fall through.

    The ProcessingService instance is available as request.auth.
    Access control is handled by HasProcessingServiceKey permission class,
    not by the user object — follows the djangorestframework-api-key pattern.
    """

    def authenticate(self, request):
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return None

        token = auth_header[7:]  # Strip "Bearer "
        if not token.startswith(API_KEY_PREFIX):
            return None  # Not an API key, let other backends handle it

        from ami.ml.models.processing_service import ProcessingService

        try:
            ps = ProcessingService.objects.get(api_key=token)
        except ProcessingService.DoesNotExist:
            return None  # Invalid key

        return (AnonymousUser(), ps)

    def authenticate_header(self, request):
        return "Bearer"
