import logging

from django.contrib.auth.models import AnonymousUser
from rest_framework.authentication import BaseAuthentication
from rest_framework_api_key.permissions import KeyParser

logger = logging.getLogger(__name__)


class ProcessingServiceAPIKeyAuthentication(BaseAuthentication):
    """
    Authenticate processing services via Api-Key header.

    Uses djangorestframework-api-key's KeyParser to extract the key,
    then looks up the ProcessingServiceAPIKey and returns
    (AnonymousUser, processing_service).

    The ProcessingService instance is available as request.auth.
    """

    key_parser = KeyParser()

    def authenticate(self, request):
        key = self.key_parser.get(request)
        if not key:
            return None

        from ami.ml.models.api_key import ProcessingServiceAPIKey

        try:
            api_key = ProcessingServiceAPIKey.objects.get_from_key(key)
        except ProcessingServiceAPIKey.DoesNotExist:
            return None

        if api_key.revoked:
            return None

        return (AnonymousUser(), api_key.processing_service)

    def authenticate_header(self, request):
        return "Api-Key"
