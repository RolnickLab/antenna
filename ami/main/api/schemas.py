from drf_spectacular.utils import OpenApiParameter

project_id_doc_param = OpenApiParameter(
    name="project_id",
    description="Filter by project ID",
    required=False,
    type=int,
)

limit_doc_param = OpenApiParameter(
    name="limit",
    description="Maximum number of items to return (1-50, default 5).",
    required=False,
    type=int,
)

include_public_doc_param = OpenApiParameter(
    name="include_public",
    description="Include rows that are public (available to every project), not just the ones "
    "belonging to this project. Defaults to true.",
    required=False,
    type=bool,
)
