import requests
from django.forms import FloatField
from drf_spectacular.utils import OpenApiParameter
from requests.adapters import HTTPAdapter
from rest_framework.request import Request
from urllib3.util import Retry


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


project_id_doc_param = OpenApiParameter(
    name="project_id",
    description="Filter by project ID",
    required=False,
    type=int,
)
