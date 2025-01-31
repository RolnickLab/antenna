from django.forms import FloatField
from drf_spectacular.utils import OpenApiParameter
from rest_framework.request import Request


def get_active_classification_threshold(request: Request) -> float:
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
