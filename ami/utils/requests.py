import typing

import requests
from django.forms import BooleanField, FloatField
from requests.adapters import HTTPAdapter
from rest_framework.request import Request
from urllib3.util import Retry

if typing.TYPE_CHECKING:
    from ami.main.models import Project


def create_session(
    retries: int = 3,
    backoff_factor: int = 2,
    status_forcelist: tuple[int, ...] = (500, 502, 503, 504),
) -> requests.Session:
    """
    Create a requests Session with retry capabilities.

    Args:
        retries: Maximum number of retries
        backoff_factor: Backoff factor for retries
        status_forcelist: HTTP status codes to retry on

    Returns:
        Session configured with retry behavior
    """
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def extract_error_message_from_response(resp: requests.Response) -> str:
    """
    Extract detailed error information from an HTTP response.

    Prioritizes the "detail" field from JSON responses (FastAPI standard),
    falls back to other fields, text content, or raw bytes.

    Args:
        resp: The HTTP response object

    Returns:
        A formatted error message string
    """
    error_details = [f"HTTP {resp.status_code}: {resp.reason}"]

    try:
        # Try to parse JSON response
        resp_json = resp.json()
        if isinstance(resp_json, dict):
            # Check for the standard "detail" field first
            if "detail" in resp_json:
                error_details.append(f"Detail: {resp_json['detail']}")
            else:
                # Fallback: add all fields from the error response
                for key, value in resp_json.items():
                    error_details.append(f"{key}: {value}")
        else:
            error_details.append(f"Response: {resp_json}")
    except (ValueError, KeyError):
        # If JSON parsing fails, try to get text content
        try:
            content_text = resp.text
            if content_text:
                error_details.append(f"Response text: {content_text[:500]}")  # Limit to first 500 chars
        except Exception:
            # Last resort: raw content
            error_details.append(f"Response content: {resp.content[:500]}")

    return " | ".join(error_details)


def get_active_classification_threshold(request: Request) -> float:
    """
    Get the active classification threshold from request parameters.

    Args:
        request: The incoming request object

    Returns:
        The classification threshold value, defaulting to 0 if not specified
    """
    # Look for a query param to filter by score
    classification_threshold = request.query_params.get("classification_threshold")

    if classification_threshold is not None:
        classification_threshold = FloatField(required=False).clean(classification_threshold)
    else:
        classification_threshold = 0
    return classification_threshold


def get_apply_default_filters_flag(request: Request | None = None) -> bool:
    """
    Get the apply_default_filters parameter from request parameters.

    Args:
        request: The incoming request object
    Returns:
        The apply_default_filters value, defaulting to True if not specified
    """
    default = True

    if request is None:
        return default

    apply_default_filters = request.query_params.get("apply_defaults") or default
    apply_default_filters = BooleanField(required=False).clean(apply_default_filters)
    return apply_default_filters


def get_default_classification_threshold(project: "Project | None" = None, request: Request | None = None) -> float:
    """
    Get the classification threshold from project settings by default,
    or from request query parameters if `apply_defaults=false` is set in the request.

    Args:
        project: A Project instance.
        request: The incoming request object (optional).

    Returns:
        The classification threshold value from project settings by default,
        or from request if `apply_defaults=false` is provided.
    """
    default_threshold = 0.0

    if get_apply_default_filters_flag(request) is False:
        return get_active_classification_threshold(request)

    if project:
        return project.default_filters_score_threshold
    else:
        return default_threshold
