import logging
import secrets

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
    Returns: (ProcessingServiceUser, ProcessingService) or None to fall through.
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

        return (ProcessingServiceUser(ps), ps)

    def authenticate_header(self, request):
        return "Bearer"


class ProcessingServiceUser:
    """
    Lightweight user stand-in for API key authenticated requests.
    Satisfies DRF's expectation of a user object on request.user.
    """

    def __init__(self, processing_service):
        self.processing_service = processing_service
        self.pk = None
        self.is_authenticated = True
        self.is_active = True
        self.is_staff = False
        self.is_superuser = False

    def __str__(self):
        return f"ProcessingService:{self.processing_service.name}"
