from django.conf import settings
from rest_framework.exceptions import ParseError
from rest_framework.parsers import JSONParser


class MaxSizeJSONParser(JSONParser):
    """
    JSONParser that enforces DATA_UPLOAD_MAX_MEMORY_SIZE for JSON request bodies.

    Django's DATA_UPLOAD_MAX_MEMORY_SIZE applies to multipart form data and direct
    request.body access, but DRF parsers read from the raw WSGI stream, bypassing
    that check. This parser enforces the same ceiling for JSON bodies using the
    Content-Length header before reading begins.

    Note: only effective when the client sends Content-Length. For chunked transfers
    without a Content-Length header the check is skipped; nginx's client_max_body_size
    is the hard outer limit in that case.
    """

    def parse(self, stream, media_type=None, parser_context=None):
        if parser_context is not None:
            request = parser_context.get("request")
            if request is not None:
                content_length = int(request.headers.get("content-length") or 0)
                max_size = getattr(settings, "DATA_UPLOAD_MAX_MEMORY_SIZE", None)
                if max_size and content_length > max_size:
                    limit_mb = max_size // (1024 * 1024)
                    raise ParseError(
                        f"Request body exceeds the {limit_mb} MB limit "
                        f"(Content-Length: {content_length} bytes). "
                        f"Raise DJANGO_DATA_UPLOAD_MAX_MEMORY_MB and nginx "
                        f"client_max_body_size in lockstep."
                    )
        return super().parse(stream, media_type, parser_context)
