# Refactor Pipeline Registration to Nested DRF Route

## Context

The `ProjectViewSet.pipelines` action ([views.py:212-283](ami/main/api/views.py#L212-L283)) manually parses pydantic with `parse_obj()` + try/except, lacks `transaction.atomic()`, and rejects re-registration. Since this is the first introduction of this API, we should get the design right: a proper nested route following the `/projects/{id}/members/` pattern, with standard DRF serializer validation.

**Current**: `POST /api/v2/projects/{pk}/pipelines/` — action on ProjectViewSet, pydantic-only validation
**Target**: `GET/POST /api/v2/projects/{project_pk}/pipelines/` — nested ViewSet with DRF patterns

## Changes

### 1. Create `ProjectPipelineViewSet` in [ami/ml/views.py](ami/ml/views.py)

New ViewSet registered on the nested router:

- **GET (list)**: Lists pipelines for the project. Reuse existing `PipelineSerializer` and the queryset logic from `PipelineViewSet.get_queryset()` ([ami/ml/views.py:88-107](ami/ml/views.py#L88-L107)) which already filters by project and prefetches processing services + configs.

- **POST (create)**: Pipeline registration. Uses a new `PipelineRegistrationSerializer` for validation, wraps DB ops in `transaction.atomic()`, idempotent re-registration.

```python
class ProjectPipelineViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """Pipelines for a specific project. GET lists, POST registers."""

    def get_queryset(self):
        project_pk = self.kwargs["project_pk"]
        # Reuse PipelineViewSet's prefetch pattern
        return Pipeline.objects.filter(
            projects=project_pk, project_pipeline_configs__enabled=True
        ).prefetch_related(...)

    def get_serializer_class(self):
        if self.action == "create":
            return PipelineRegistrationSerializer
        return PipelineSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = get_object_or_404(Project, pk=self.kwargs["project_pk"])

        with transaction.atomic():
            processing_service, _ = ProcessingService.objects.get_or_create(
                name=serializer.validated_data["processing_service_name"],
                defaults={"endpoint_url": None},
            )
            processing_service.projects.add(project)  # idempotent

            response = processing_service.create_pipelines(
                pipeline_configs=serializer.validated_data["pipelines"],
                projects=Project.objects.filter(pk=project.pk),
            )

        return Response(response.dict(), status=status.HTTP_201_CREATED)
```

### 2. Add `PipelineRegistrationSerializer` in [ami/ml/serializers.py](ami/ml/serializers.py)

Use `SchemaField` to embed pydantic validation inside DRF, consistent with existing patterns ([ami/ml/serializers.py:97](ami/ml/serializers.py#L97), [ami/jobs/serializers.py:49-50](ami/jobs/serializers.py#L49-L50)):

```python
from ami.ml.schemas import PipelineConfigResponse

class PipelineRegistrationSerializer(serializers.Serializer):
    processing_service_name = serializers.CharField()
    pipelines = SchemaField(schema=list[PipelineConfigResponse], default=[])
```

### 3. Register nested route in [config/api_router.py](config/api_router.py)

Add alongside the existing `members` nested route:

```python
from ami.ml.views import ProjectPipelineViewSet

projects_router.register(
    r"pipelines",
    ProjectPipelineViewSet,
    basename="project-pipelines",
)
```

**Result**: `GET/POST /api/v2/projects/{project_pk}/pipelines/`

### 4. Remove old action from [ami/main/api/views.py](ami/main/api/views.py)

Delete the `pipelines` action method (lines 212-283) and its associated imports (`AsyncPipelineRegistrationRequest`, `PipelineRegistrationResponse`, `ValidationError` if unused elsewhere).

### 5. Add OpenAPI schema annotations

Add `@extend_schema` decorators on `list` and `create` methods of the new ViewSet for proper documentation.

## Files to modify

| File | Change |
|------|--------|
| [ami/ml/views.py](ami/ml/views.py) | Add `ProjectPipelineViewSet` |
| [ami/ml/serializers.py](ami/ml/serializers.py) | Add `PipelineRegistrationSerializer` |
| [config/api_router.py](config/api_router.py) | Register nested route |
| [ami/main/api/views.py](ami/main/api/views.py) | Remove old `pipelines` action + unused imports |

## Verification

```bash
# Run existing tests
docker compose run --rm django python manage.py test -k pipeline

# Verify OpenAPI schema generates without errors
docker compose run --rm django python manage.py spectacular --api-version 'api' --format openapi --file /dev/null

# Test GET list
curl http://localhost:8000/api/v2/projects/1/pipelines/

# Test POST registration (same payload format as before)
curl -X POST http://localhost:8000/api/v2/projects/1/pipelines/ \
  -H "Content-Type: application/json" \
  -d '{"processing_service_name": "test", "pipelines": [...]}'
```
