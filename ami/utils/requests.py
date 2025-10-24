import typing

import requests
from django.forms import BooleanField, FloatField
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter
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


project_id_doc_param = OpenApiParameter(
    name="project_id",
    description="Filter by project ID",
    required=False,
    type=int,
)

ids_only_param = OpenApiParameter(
    name="ids_only",
    description="Return only job IDs instead of full job objects",
    required=False,
    type=OpenApiTypes.BOOL,
)
incomplete_only_param = OpenApiParameter(
    name="incomplete_only",
    description="Filter to only show incomplete jobs (excludes SUCCESS, FAILURE, REVOKED)",
    required=False,
    type=OpenApiTypes.BOOL,
)
batch_param = OpenApiParameter(
    name="batch",
    description="Number of tasks to pull in the batch",
    required=False,
    type=OpenApiTypes.INT,
)
