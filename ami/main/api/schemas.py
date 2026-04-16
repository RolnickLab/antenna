from drf_spectacular.utils import OpenApiParameter

project_id_doc_param = OpenApiParameter(
    name="project_id",
    description="Filter by project ID",
    required=False,
    type=int,
)
