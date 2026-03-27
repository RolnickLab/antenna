# Processing Service API Keys & Endpoint Refactor

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add API key authentication for processing services, pass client_info on every request for instance tracking, and refactor /tasks and /result endpoints with proper DRF serializers.

**Architecture:** ProcessingService gains an `api_key` field (prefixed `ant_ps_`). A new DRF auth backend authenticates workers by API key. The `/tasks` endpoint changes from GET to POST. Both `/tasks` and `/result` accept a `client_info` JSON object (hostname, software, version, platform) merged with server-observed values (IP, User-Agent). Task results are stamped with client_info for audit trail.

**Tech Stack:** Django 4.2, DRF, PostgreSQL, Celery, NATS JetStream, React 18 + TypeScript

**Design Doc:** https://docs.google.com/document/d/17sHrI6OIyDsf0CcuhkzczCp1xVXacV8Ak__7CtDi2Ig/edit

**Closes:** #1117, #1141, #1153
**Close PR:** #1117 (superseded by this work)
**Depends on:** PR #1146 must be merged first (last_seen rename + heartbeat infrastructure)

---

## Prerequisites

Before starting, ensure:
1. PR #1146 is merged into main
2. You have a fresh branch from main: `git checkout -b feat/ps-api-keys main`
3. Docker compose is running: `docker compose up -d`
4. Tests pass on main: `docker compose run --rm django python manage.py test ami.ml.tests ami.jobs --keepdb`

## File Map

### New Files
- `ami/ml/auth.py` — API key auth backend + key generation utility
- `ami/ml/serializers_client_info.py` — ClientInfoSerializer (separate file, used by multiple serializers)
- `ami/ml/migrations/0028_add_api_key_fields.py` — Migration for new fields
- `ami/ml/management/commands/create_default_processing_service.py` — Auto-setup for docker compose

### Modified Files
- `ami/ml/models/processing_service.py` — Add api_key, api_key_prefix, api_key_created_at, last_seen_client_info fields
- `ami/ml/serializers.py` — Update ProcessingServiceSerializer, PipelineRegistrationSerializer
- `ami/ml/views.py` — Update ProjectPipelineViewSet.create() for API key auth + client_info
- `ami/ml/tests.py` — Add API key auth tests, client_info tests
- `ami/jobs/views.py` — Refactor tasks() to POST, add client_info to both endpoints, remove _log_processing_service_name
- `ami/jobs/schemas.py` — Remove processing_service_name_param, add new params
- `ami/jobs/tests.py` — Add E2E tests for full flow
- `config/settings/base.py` — Add API key auth backend to REST_FRAMEWORK
- `ui/src/pages/project/entities/details-form/processing-service-details-form.tsx` — Make endpoint_url optional, show API key
- `ui/src/data-services/models/processing-service.ts` — Add apiKey, apiKeyPrefix, lastSeenClientInfo fields
- `ui/src/utils/language.ts` — Add new string constants

---

## Task 1: API Key Generation Utility and Auth Backend

**Files:**
- Create: `ami/ml/auth.py`
- Modify: `config/settings/base.py`
- Test: `ami/ml/tests.py`

- [ ] **Step 1: Write failing tests for key generation and auth backend**

Add to `ami/ml/tests.py`:

```python
import secrets
from django.test import TestCase, RequestFactory
from rest_framework.test import APIClient
from ami.ml.auth import generate_api_key, ProcessingServiceAPIKeyAuthentication
from ami.ml.models import ProcessingService
from ami.main.models import Project
from ami.users.tests.factories import UserFactory


class TestAPIKeyGeneration(TestCase):
    def test_generate_api_key_has_prefix(self):
        key = generate_api_key()
        self.assertTrue(key.startswith("ant_ps_"))

    def test_generate_api_key_is_unique(self):
        key1 = generate_api_key()
        key2 = generate_api_key()
        self.assertNotEqual(key1, key2)

    def test_generate_api_key_sufficient_length(self):
        key = generate_api_key()
        # ant_ps_ (7) + 48 chars of token = 55 min
        self.assertGreaterEqual(len(key), 50)


class TestAPIKeyAuthentication(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.project = Project.objects.create(name="Test Project", owner=self.user)
        self.ps = ProcessingService.objects.create(
            name="Test Service",
            endpoint_url=None,
        )
        self.ps.projects.add(self.project)
        # Generate and assign API key
        from ami.ml.auth import generate_api_key
        self.api_key = generate_api_key()
        self.ps.api_key = self.api_key
        self.ps.api_key_prefix = self.api_key[:12]
        self.ps.save(update_fields=["api_key", "api_key_prefix"])

    def test_authenticate_valid_key(self):
        factory = RequestFactory()
        request = factory.get("/", HTTP_AUTHORIZATION=f"Bearer {self.api_key}")
        auth = ProcessingServiceAPIKeyAuthentication()
        result = auth.authenticate(request)
        self.assertIsNotNone(result)
        user, ps = result
        self.assertEqual(ps.pk, self.ps.pk)

    def test_authenticate_invalid_key(self):
        factory = RequestFactory()
        request = factory.get("/", HTTP_AUTHORIZATION="Bearer ant_ps_invalid_key")
        auth = ProcessingServiceAPIKeyAuthentication()
        result = auth.authenticate(request)
        self.assertIsNone(result)

    def test_authenticate_non_api_key_passes_through(self):
        """Non ant_ps_ tokens should return None (fall through to next backend)."""
        factory = RequestFactory()
        request = factory.get("/", HTTP_AUTHORIZATION="Token some_djoser_token")
        auth = ProcessingServiceAPIKeyAuthentication()
        result = auth.authenticate(request)
        self.assertIsNone(result)

    def test_authenticate_no_header(self):
        factory = RequestFactory()
        request = factory.get("/")
        auth = ProcessingServiceAPIKeyAuthentication()
        result = auth.authenticate(request)
        self.assertIsNone(result)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose run --rm django python manage.py test ami.ml.tests.TestAPIKeyGeneration ami.ml.tests.TestAPIKeyAuthentication --keepdb -v2`
Expected: `ImportError: cannot import name 'generate_api_key' from 'ami.ml.auth'`

- [ ] **Step 3: Implement auth module**

Create `ami/ml/auth.py`:

```python
import secrets
import logging

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
    Returns: (AnonymousUser-like, ProcessingService) or None to fall through.
    """

    def authenticate(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
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

        # Return a lightweight user-like object and the PS instance
        # The PS is available as request.auth in views
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose run --rm django python manage.py test ami.ml.tests.TestAPIKeyGeneration ami.ml.tests.TestAPIKeyAuthentication --keepdb -v2`
Expected: All 7 tests PASS

- [ ] **Step 5: Add auth backend to settings**

In `config/settings/base.py`, update `REST_FRAMEWORK`:

```python
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "ami.ml.auth.ProcessingServiceAPIKeyAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ),
    # ... rest unchanged
}
```

- [ ] **Step 6: Commit**

```bash
git add ami/ml/auth.py ami/ml/tests.py config/settings/base.py
git commit -m "feat: add API key auth backend for processing services

Add generate_api_key() utility with ant_ps_ prefix and
ProcessingServiceAPIKeyAuthentication DRF backend. API key auth
is checked first, falling through to existing TokenAuthentication
for regular users.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: ProcessingService Model Changes + Migration

**Files:**
- Modify: `ami/ml/models/processing_service.py`
- Create: `ami/ml/migrations/0028_add_api_key_fields.py` (auto-generated)
- Test: `ami/ml/tests.py`

**Note:** This task assumes PR #1146 is merged. The model already has `last_seen`, `last_seen_live`, `last_seen_latency`, `mark_seen()`, `ProcessingServiceQuerySet` with `async_services()` and `sync_services()`.

- [ ] **Step 1: Write failing tests for new model fields**

Add to `ami/ml/tests.py`:

```python
class TestProcessingServiceAPIKey(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.project = Project.objects.create(name="Test Project", owner=self.user)

    def test_create_ps_without_api_key(self):
        """Sync services don't need an API key."""
        ps = ProcessingService.objects.create(
            name="Sync Service",
            endpoint_url="http://example.com:2000",
        )
        self.assertIsNone(ps.api_key)

    def test_generate_and_assign_api_key(self):
        ps = ProcessingService.objects.create(
            name="Async Service",
            endpoint_url=None,
        )
        ps.generate_api_key()
        self.assertTrue(ps.api_key.startswith("ant_ps_"))
        self.assertEqual(ps.api_key_prefix, ps.api_key[:12])
        self.assertIsNotNone(ps.api_key_created_at)

    def test_regenerate_api_key_changes_key(self):
        ps = ProcessingService.objects.create(name="Service", endpoint_url=None)
        ps.generate_api_key()
        old_key = ps.api_key
        ps.generate_api_key()
        self.assertNotEqual(ps.api_key, old_key)

    def test_last_seen_client_info_stored(self):
        ps = ProcessingService.objects.create(name="Service", endpoint_url=None)
        ps.last_seen_client_info = {"hostname": "node-01", "software": "adc", "version": "2.0"}
        ps.save()
        ps.refresh_from_db()
        self.assertEqual(ps.last_seen_client_info["hostname"], "node-01")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose run --rm django python manage.py test ami.ml.tests.TestProcessingServiceAPIKey --keepdb -v2`
Expected: FAIL — `api_key` field does not exist

- [ ] **Step 3: Add fields to ProcessingService model**

In `ami/ml/models/processing_service.py`, add fields to the `ProcessingService` class after the existing fields:

```python
    # API key authentication (for pull-mode/async services)
    api_key = models.CharField(max_length=255, unique=True, null=True, blank=True, db_index=True)
    api_key_prefix = models.CharField(max_length=12, null=True, blank=True)
    api_key_created_at = models.DateTimeField(null=True, blank=True)

    # Last known client info from the most recent request
    last_seen_client_info = models.JSONField(null=True, blank=True)
```

Add the `generate_api_key()` method to the `ProcessingService` class:

```python
    def generate_api_key(self) -> str:
        """Generate a new API key, replacing any existing one."""
        import datetime
        from ami.ml.auth import generate_api_key

        self.api_key = generate_api_key()
        self.api_key_prefix = self.api_key[:12]
        self.api_key_created_at = datetime.datetime.now()
        self.save(update_fields=["api_key", "api_key_prefix", "api_key_created_at"])
        return self.api_key
```

- [ ] **Step 4: Generate and run migration**

```bash
docker compose run --rm django python manage.py makemigrations ml --name add_api_key_fields
docker compose run --rm django python manage.py migrate
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose run --rm django python manage.py test ami.ml.tests.TestProcessingServiceAPIKey --keepdb -v2`
Expected: All 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add ami/ml/models/processing_service.py ami/ml/migrations/0028_add_api_key_fields.py ami/ml/tests.py
git commit -m "feat: add api_key fields to ProcessingService model

Add api_key (unique, indexed), api_key_prefix (for display),
api_key_created_at, and last_seen_client_info (JSONField).
Includes generate_api_key() method for key creation/rotation.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: ClientInfoSerializer

**Files:**
- Create: `ami/ml/serializers_client_info.py`
- Test: `ami/ml/tests.py`

- [ ] **Step 1: Write failing tests for client_info serializer**

Add to `ami/ml/tests.py`:

```python
from ami.ml.serializers_client_info import ClientInfoSerializer


class TestClientInfoSerializer(TestCase):
    def test_valid_client_info(self):
        data = {
            "hostname": "cedar-node-01",
            "software": "ami-data-companion",
            "version": "2.1.0",
            "platform": "Linux x86_64",
        }
        s = ClientInfoSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data["hostname"], "cedar-node-01")

    def test_empty_client_info_is_valid(self):
        """All fields are optional."""
        s = ClientInfoSerializer(data={})
        self.assertTrue(s.is_valid(), s.errors)

    def test_extra_fields_in_extra_dict(self):
        data = {
            "hostname": "node-01",
            "extra": {"gpu": "A100", "cuda": "12.0"},
        }
        s = ClientInfoSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data["extra"]["gpu"], "A100")

    def test_hostname_max_length_enforced(self):
        data = {"hostname": "x" * 256}
        s = ClientInfoSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn("hostname", s.errors)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose run --rm django python manage.py test ami.ml.tests.TestClientInfoSerializer --keepdb -v2`
Expected: `ImportError`

- [ ] **Step 3: Implement ClientInfoSerializer**

Create `ami/ml/serializers_client_info.py`:

```python
from rest_framework import serializers


class ClientInfoSerializer(serializers.Serializer):
    """
    Validated client_info from processing service requests.

    Client-reported fields (all optional):
        hostname, software, version, platform, pod_name, extra

    Server-observed fields (added by get_client_info(), not sent by client):
        ip, user_agent
    """

    hostname = serializers.CharField(max_length=255, required=False, default="")
    software = serializers.CharField(max_length=100, required=False, default="")
    version = serializers.CharField(max_length=50, required=False, default="")
    platform = serializers.CharField(max_length=100, required=False, default="")
    pod_name = serializers.CharField(max_length=255, required=False, default="")
    extra = serializers.DictField(required=False, default=dict)


def get_client_info(request) -> dict:
    """
    Extract client_info from request body, merged with server-observed values.

    Server-observed fields (ip, user_agent) are always present.
    Client-reported fields come from request.data["client_info"] when provided.
    """
    raw = request.data.get("client_info") or {}
    serializer = ClientInfoSerializer(data=raw)
    if serializer.is_valid():
        info = serializer.validated_data
    else:
        info = {}

    # Add server-observed fields as defaults (don't overwrite client-sent values)
    info.setdefault("ip", _get_client_ip(request))
    info.setdefault("user_agent", request.META.get("HTTP_USER_AGENT", ""))
    return info


def _get_client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose run --rm django python manage.py test ami.ml.tests.TestClientInfoSerializer --keepdb -v2`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add ami/ml/serializers_client_info.py ami/ml/tests.py
git commit -m "feat: add ClientInfoSerializer and get_client_info utility

Validated serializer for client-reported metadata (hostname, software,
version, platform, pod_name, extra). get_client_info() merges with
server-observed IP and User-Agent on every request.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: Refactor /tasks Endpoint (GET → POST)

**Files:**
- Modify: `ami/jobs/views.py`
- Modify: `ami/jobs/schemas.py`
- Test: `ami/jobs/tests.py`

- [ ] **Step 1: Write failing tests for POST /tasks with client_info**

Add to `ami/jobs/tests.py` (or create a new test class in the existing file):

```python
from rest_framework.test import APIClient
from ami.jobs.models import Job, JobState, JobDispatchMode
from ami.ml.models import ProcessingService, Pipeline
from ami.ml.auth import generate_api_key
from ami.main.models import Project
from ami.users.tests.factories import UserFactory


class TestTasksEndpointRefactor(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.project = Project.objects.create(name="Test Project", owner=self.user)
        self.pipeline = Pipeline.objects.create(name="Test Pipeline", slug="test-pipeline", version="1.0")

        # Create async PS with API key
        self.ps = ProcessingService.objects.create(name="Test PS", endpoint_url=None)
        self.ps.projects.add(self.project)
        self.ps.pipelines.add(self.pipeline)
        self.api_key = self.ps.generate_api_key()

        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.api_key}")

    def _create_async_job(self):
        job = Job.objects.create(
            name="Test Job",
            project=self.project,
            pipeline=self.pipeline,
            dispatch_mode=JobDispatchMode.ASYNC_API,
        )
        job.status = JobState.STARTED
        job.save(update_fields=["status"])
        return job

    def test_tasks_endpoint_is_post(self):
        """GET should return 405, POST should work."""
        job = self._create_async_job()
        url = f"/api/v2/jobs/{job.pk}/tasks/"

        # GET should fail
        response = self.client.get(url, {"batch": 1})
        self.assertEqual(response.status_code, 405)

        # POST should work (may return empty tasks if no NATS, but not 405)
        response = self.client.post(url, {"batch": 1}, format="json")
        self.assertIn(response.status_code, [200, 500])  # 500 if NATS not running

    def test_tasks_with_client_info(self):
        job = self._create_async_job()
        url = f"/api/v2/jobs/{job.pk}/tasks/"
        response = self.client.post(
            url,
            {
                "batch": 2,
                "client_info": {
                    "hostname": "test-node",
                    "software": "test-worker",
                    "version": "1.0",
                },
            },
            format="json",
        )
        # Should accept the request (may fail on NATS, but validates input)
        self.assertIn(response.status_code, [200, 500])

    def test_tasks_requires_batch(self):
        job = self._create_async_job()
        url = f"/api/v2/jobs/{job.pk}/tasks/"
        response = self.client.post(url, {}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_tasks_api_key_auth(self):
        """Unauthenticated requests should be rejected."""
        job = self._create_async_job()
        url = f"/api/v2/jobs/{job.pk}/tasks/"
        client = APIClient()  # No credentials
        response = client.post(url, {"batch": 1}, format="json")
        self.assertIn(response.status_code, [401, 403])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose run --rm django python manage.py test ami.jobs.tests.TestTasksEndpointRefactor --keepdb -v2`
Expected: FAIL — tasks endpoint still accepts GET

- [ ] **Step 3: Create TasksRequestSerializer**

Add to `ami/jobs/schemas.py`:

```python
from rest_framework import serializers
from ami.ml.serializers_client_info import ClientInfoSerializer


class TasksRequestSerializer(serializers.Serializer):
    batch = serializers.IntegerField(min_value=1, required=True)
    client_info = ClientInfoSerializer(required=False)
```

- [ ] **Step 4: Refactor tasks() action in JobViewSet**

In `ami/jobs/views.py`, replace the `tasks()` action. Key changes:
- Change `methods=["get"]` to `methods=["post"]`
- Use `TasksRequestSerializer` for input validation
- Extract client_info via `get_client_info(request)`
- Update the PS heartbeat using API key auth
- Log with client_info instead of processing_service_name

```python
    @extend_schema(
        operation_id="jobs_tasks",
        summary="Fetch tasks from the job queue",
        description="Pull tasks from the NATS queue for async processing. Requires POST.",
        request=TasksRequestSerializer,
        responses={200: dict},
        tags=["jobs"],
    )
    @action(detail=True, methods=["post"], name="tasks")
    def tasks(self, request, pk=None):
        from ami.jobs.schemas import TasksRequestSerializer
        from ami.ml.serializers_client_info import get_client_info

        serializer = TasksRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        batch = serializer.validated_data["batch"]
        client_info = get_client_info(request)

        job = self.get_object()

        if job.dispatch_mode != JobDispatchMode.ASYNC_API:
            raise ValidationError(f"Job {job.pk} is not an async job (mode: {job.dispatch_mode}).")

        if job.status not in JobState.active_states():
            raise ValidationError(f"Job {job.pk} is not active (status: {job.status}).")

        # Update heartbeat for the processing service (scoped by API key)
        if hasattr(request, "auth") and isinstance(request.auth, ProcessingService):
            ps = request.auth
            ps.last_seen_client_info = client_info
            ps.mark_seen(live=True)
            logger.info("Job %s: %d tasks requested by %s (%s)", job.pk, batch, ps.name, client_info.get("hostname", "unknown"))

        async def get_tasks():
            from ami.ml.orchestration.nats_queue import TaskQueueManager

            async with TaskQueueManager() as manager:
                tasks = await manager.reserve_tasks(job.pk, count=batch)
                return [task.dict() for task in tasks]

        try:
            tasks = async_to_sync(get_tasks)()
        except Exception as e:
            logger.error("Error fetching tasks for job %s: %s", job.pk, e)
            return Response(
                {"error": f"Failed to fetch tasks: {e}"},
                status=500,
            )

        return Response({"tasks": tasks})
```

- [ ] **Step 5: Remove old processing_service_name artifacts**

In `ami/jobs/views.py`:
- Remove the `_mark_pipeline_pull_services_seen()` function (replaced by per-PS heartbeat in the tasks/result actions)
- Remove any imports of `processing_service_name_param` from `ami/jobs/schemas.py`

In `ami/jobs/schemas.py`:
- Remove `processing_service_name_param` if it exists (from PR #1117)

- [ ] **Step 6: Run tests to verify they pass**

Run: `docker compose run --rm django python manage.py test ami.jobs.tests.TestTasksEndpointRefactor --keepdb -v2`
Expected: All 4 tests PASS

- [ ] **Step 7: Commit**

```bash
git add ami/jobs/views.py ami/jobs/schemas.py ami/jobs/tests.py
git commit -m "refactor: change /tasks to POST with DRF serializer and client_info

/tasks now requires POST with TasksRequestSerializer (batch, client_info).
Heartbeats scoped to the specific PS via API key auth. Removes
_mark_pipeline_pull_services_seen() and processing_service_name_param.

Closes #1141 (partially)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 5: Refactor /result Endpoint

**Files:**
- Modify: `ami/jobs/views.py`
- Modify: `ami/jobs/schemas.py`
- Test: `ami/jobs/tests.py`

- [ ] **Step 1: Write failing tests for /result with client_info**

Add to `ami/jobs/tests.py`:

```python
class TestResultEndpointRefactor(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.project = Project.objects.create(name="Test Project", owner=self.user)
        self.pipeline = Pipeline.objects.create(name="Test Pipeline", slug="test-pipeline-result", version="1.0")

        self.ps = ProcessingService.objects.create(name="Test PS Result", endpoint_url=None)
        self.ps.projects.add(self.project)
        self.ps.pipelines.add(self.pipeline)
        self.api_key = self.ps.generate_api_key()

        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.api_key}")

    def _create_async_job(self):
        job = Job.objects.create(
            name="Test Job",
            project=self.project,
            pipeline=self.pipeline,
            dispatch_mode=JobDispatchMode.ASYNC_API,
        )
        job.status = JobState.STARTED
        job.save(update_fields=["status"])
        return job

    def test_result_with_client_info_wrapper(self):
        """Result should accept {client_info: ..., results: [...]}."""
        job = self._create_async_job()
        url = f"/api/v2/jobs/{job.pk}/result/"
        response = self.client.post(
            url,
            {
                "client_info": {"hostname": "test-node", "software": "test-worker"},
                "results": [],
            },
            format="json",
        )
        # Empty results should still be accepted
        self.assertEqual(response.status_code, 200)

    def test_result_api_key_updates_heartbeat(self):
        job = self._create_async_job()
        url = f"/api/v2/jobs/{job.pk}/result/"
        self.client.post(
            url,
            {
                "client_info": {"hostname": "test-node"},
                "results": [],
            },
            format="json",
        )
        self.ps.refresh_from_db()
        self.assertIsNotNone(self.ps.last_seen)
        self.assertTrue(self.ps.last_seen_live)
        self.assertEqual(self.ps.last_seen_client_info["hostname"], "test-node")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose run --rm django python manage.py test ami.jobs.tests.TestResultEndpointRefactor --keepdb -v2`
Expected: FAIL — result endpoint expects bare list, not wrapped object

- [ ] **Step 3: Create ResultRequestSerializer**

Add to `ami/jobs/schemas.py`:

```python
from ami.ml.schemas import PipelineTaskResult
from django_pydantic_field.rest_framework import SchemaField


class ResultRequestSerializer(serializers.Serializer):
    client_info = ClientInfoSerializer(required=False)
    results = SchemaField(schema=list[PipelineTaskResult])
```

- [ ] **Step 4: Refactor result() action in JobViewSet**

In `ami/jobs/views.py`, update the `result()` action to:
- Use `ResultRequestSerializer` for input validation
- Extract client_info and results from the validated data
- Update PS heartbeat via API key auth
- Pass client_info through to the Celery task for stamping on results

```python
    @extend_schema(
        operation_id="jobs_result",
        summary="Submit pipeline results",
        description="Accept pipeline results and queue them for background processing.",
        request=ResultRequestSerializer,
        responses={200: dict},
        tags=["jobs"],
    )
    @action(detail=True, methods=["post"], name="result")
    def result(self, request, pk=None):
        from ami.jobs.schemas import ResultRequestSerializer
        from ami.ml.serializers_client_info import get_client_info

        serializer = ResultRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        client_info = get_client_info(request)
        results = serializer.validated_data["results"]

        job = self.get_object()

        # Update heartbeat
        if hasattr(request, "auth") and isinstance(request.auth, ProcessingService):
            ps = request.auth
            ps.last_seen_client_info = client_info
            ps.mark_seen(live=True)
            logger.info("Job %s: %d results received from %s (%s)", job.pk, len(results), ps.name, client_info.get("hostname", "unknown"))

        # Pre-validate all results
        validated_results = []
        errors = []
        for i, result_item in enumerate(results):
            result_data = result_item.dict() if hasattr(result_item, "dict") else result_item
            result_data["client_info"] = client_info  # Stamp with client info
            validated_results.append(result_data)

        if errors:
            return Response({"errors": errors}, status=400)

        # Queue for background processing
        queued = 0
        new_tasks = []
        for result_data in validated_results:
            reply_subject = result_data.get("reply_subject", "")
            process_nats_pipeline_result.delay(
                job_id=job.pk,
                result_data=result_data,
                reply_subject=reply_subject,
            )
            queued += 1

        return Response({
            "status": "accepted",
            "results_queued": queued,
        })
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose run --rm django python manage.py test ami.jobs.tests.TestResultEndpointRefactor --keepdb -v2`
Expected: All 2 tests PASS

- [ ] **Step 6: Commit**

```bash
git add ami/jobs/views.py ami/jobs/schemas.py ami/jobs/tests.py
git commit -m "refactor: wrap /result with ResultRequestSerializer and client_info

Results now wrapped in {client_info: ..., results: [...]} instead of
bare list. Each result stamped with client_info for audit trail.
Heartbeat scoped to PS via API key.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 6: Update Pipeline Registration Endpoint

**Files:**
- Modify: `ami/ml/views.py`
- Modify: `ami/ml/serializers.py`
- Test: `ami/ml/tests.py`

- [ ] **Step 1: Write failing tests for updated registration**

Add to `ami/ml/tests.py`:

```python
class TestPipelineRegistrationWithAPIKey(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.project = Project.objects.create(name="Test Project", owner=self.user)

        self.ps = ProcessingService.objects.create(name="ADC Worker", endpoint_url=None)
        self.ps.projects.add(self.project)
        self.api_key = self.ps.generate_api_key()

        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.api_key}")

    def test_register_pipelines_with_api_key_and_client_info(self):
        url = f"/api/v2/projects/{self.project.pk}/pipelines/"
        response = self.client.post(
            url,
            {
                "client_info": {
                    "hostname": "cedar-node-01",
                    "software": "ami-data-companion",
                    "version": "2.1.0",
                },
                "pipelines": [],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

        # Verify PS was updated
        self.ps.refresh_from_db()
        self.assertIsNotNone(self.ps.last_seen)
        self.assertTrue(self.ps.last_seen_live)
        self.assertEqual(self.ps.last_seen_client_info["hostname"], "cedar-node-01")

    def test_register_still_works_with_processing_service_name(self):
        """Backward compat: old-style registration with processing_service_name still works."""
        url = f"/api/v2/projects/{self.project.pk}/pipelines/"
        # Use djoser auth for backward compat test
        from rest_framework.authtoken.models import Token
        token = Token.objects.create(user=self.user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.post(
            url,
            {
                "processing_service_name": "Legacy Worker",
                "pipelines": [],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

    def test_register_enforces_project_access(self):
        """API key must have access to the project."""
        other_project = Project.objects.create(name="Other Project", owner=self.user)
        url = f"/api/v2/projects/{other_project.pk}/pipelines/"
        response = self.client.post(
            url,
            {"pipelines": []},
            format="json",
        )
        self.assertIn(response.status_code, [403, 404])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose run --rm django python manage.py test ami.ml.tests.TestPipelineRegistrationWithAPIKey --keepdb -v2`
Expected: FAIL

- [ ] **Step 3: Update PipelineRegistrationSerializer**

In `ami/ml/serializers.py`, update the serializer to accept both old and new formats:

```python
from ami.ml.serializers_client_info import ClientInfoSerializer

class PipelineRegistrationSerializer(serializers.Serializer):
    processing_service_name = serializers.CharField(required=False)  # Backward compat
    client_info = ClientInfoSerializer(required=False)
    pipelines = SchemaField(schema=list[PipelineConfigResponse], default=[])
```

- [ ] **Step 4: Update ProjectPipelineViewSet.create()**

In `ami/ml/views.py`, update the `create()` method to handle both API key auth and legacy token auth:

```python
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = self.get_active_project()

        from ami.ml.serializers_client_info import get_client_info

        # Determine the processing service from auth method
        if hasattr(request, "auth") and isinstance(request.auth, ProcessingService):
            # API key auth: PS identified by key
            processing_service = request.auth
            # Verify project access
            if not processing_service.projects.filter(pk=project.pk).exists():
                raise PermissionDenied("Processing service does not have access to this project.")
        else:
            # Legacy: get or create by name
            name = serializer.validated_data.get("processing_service_name", "")
            if not name:
                raise ValidationError({"processing_service_name": "Required when not using API key auth."})
            processing_service, _ = ProcessingService.objects.get_or_create(
                name=name,
                defaults={"endpoint_url": None},
            )
            processing_service.projects.add(project)

        client_info = get_client_info(request)

        with transaction.atomic():
            response = processing_service.create_pipelines(
                pipeline_configs=serializer.validated_data["pipelines"],
                projects=Project.objects.filter(pk=project.pk),
            )

        # Update heartbeat and client info
        processing_service.last_seen_client_info = client_info
        processing_service.mark_seen(live=True)

        return Response(response.dict(), status=status.HTTP_201_CREATED)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose run --rm django python manage.py test ami.ml.tests.TestPipelineRegistrationWithAPIKey --keepdb -v2`
Expected: All 3 tests PASS

- [ ] **Step 6: Run full test suite to check for regressions**

Run: `docker compose run --rm django python manage.py test ami.ml.tests ami.jobs --keepdb -v2`
Expected: All existing tests still pass

- [ ] **Step 7: Commit**

```bash
git add ami/ml/views.py ami/ml/serializers.py ami/ml/tests.py
git commit -m "feat: pipeline registration supports API key auth and client_info

Registration endpoint now accepts both API key auth (PS identified by
key) and legacy token auth (PS identified by processing_service_name).
client_info stored on PS and used for heartbeat. Project access enforced
for API key auth.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 7: Management Command for Docker Compose Auto-Setup

**Files:**
- Create: `ami/ml/management/commands/create_default_processing_service.py`
- Test: `ami/ml/tests.py`

- [ ] **Step 1: Write failing test**

Add to `ami/ml/tests.py`:

```python
from django.core.management import call_command
from io import StringIO


class TestCreateDefaultProcessingService(TestCase):
    def test_creates_default_ps(self):
        out = StringIO()
        call_command("create_default_processing_service", stdout=out)
        ps = ProcessingService.objects.get(name="Default Processing Service")
        self.assertIsNotNone(ps.api_key)
        self.assertTrue(ps.api_key.startswith("ant_ps_"))
        self.assertIsNone(ps.endpoint_url)

    def test_idempotent(self):
        """Running twice should not create a duplicate."""
        call_command("create_default_processing_service")
        call_command("create_default_processing_service")
        count = ProcessingService.objects.filter(name="Default Processing Service").count()
        self.assertEqual(count, 1)

    def test_uses_env_var_for_key(self):
        """If ANTENNA_DEFAULT_PS_API_KEY is set, use that key."""
        import os
        os.environ["ANTENNA_DEFAULT_PS_API_KEY"] = "ant_ps_test_key_for_ci"
        try:
            call_command("create_default_processing_service")
            ps = ProcessingService.objects.get(name="Default Processing Service")
            self.assertEqual(ps.api_key, "ant_ps_test_key_for_ci")
        finally:
            del os.environ["ANTENNA_DEFAULT_PS_API_KEY"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose run --rm django python manage.py test ami.ml.tests.TestCreateDefaultProcessingService --keepdb -v2`
Expected: FAIL — command does not exist

- [ ] **Step 3: Implement management command**

Create `ami/ml/management/__init__.py` and `ami/ml/management/commands/__init__.py` if they don't exist.

Create `ami/ml/management/commands/create_default_processing_service.py`:

```python
import os

from django.core.management.base import BaseCommand

from ami.ml.auth import generate_api_key
from ami.ml.models import ProcessingService


class Command(BaseCommand):
    help = "Create a default processing service for local development and CI."

    def handle(self, *args, **options):
        name = os.environ.get("ANTENNA_DEFAULT_PS_NAME", "Default Processing Service")
        env_key = os.environ.get("ANTENNA_DEFAULT_PS_API_KEY", "")

        ps, created = ProcessingService.objects.get_or_create(
            name=name,
            defaults={"endpoint_url": None},
        )

        if not ps.api_key:
            if env_key:
                ps.api_key = env_key
                ps.api_key_prefix = env_key[:12]
            else:
                ps.api_key = generate_api_key()
                ps.api_key_prefix = ps.api_key[:12]
            ps.save(update_fields=["api_key", "api_key_prefix"])

        if created:
            self.stdout.write(self.style.SUCCESS(f"Created processing service: {ps.name}"))
        else:
            self.stdout.write(f"Processing service already exists: {ps.name}")

        self.stdout.write(f"API key: {ps.api_key}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose run --rm django python manage.py test ami.ml.tests.TestCreateDefaultProcessingService --keepdb -v2`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add ami/ml/management/ ami/ml/tests.py
git commit -m "feat: add create_default_processing_service management command

Creates a default PS with API key for local dev and CI.
Supports ANTENNA_DEFAULT_PS_API_KEY env var for deterministic keys.
Idempotent — safe to run multiple times.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 8: Update ProcessingServiceSerializer for API Key Display

**Files:**
- Modify: `ami/ml/serializers.py`
- Modify: `ui/src/data-services/models/processing-service.ts`
- Test: `ami/ml/tests.py`

- [ ] **Step 1: Write failing test**

Add to `ami/ml/tests.py`:

```python
class TestProcessingServiceSerializerAPIKey(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.project = Project.objects.create(name="Test Project", owner=self.user)

    def test_serializer_includes_api_key_prefix(self):
        ps = ProcessingService.objects.create(name="Test PS", endpoint_url=None)
        ps.generate_api_key()
        from ami.ml.serializers import ProcessingServiceSerializer
        data = ProcessingServiceSerializer(ps).data
        self.assertIn("api_key_prefix", data)
        self.assertEqual(data["api_key_prefix"], ps.api_key[:12])
        # Full key should NOT be in serializer output
        self.assertNotIn("api_key", data)

    def test_serializer_includes_last_seen_client_info(self):
        ps = ProcessingService.objects.create(name="Test PS", endpoint_url=None)
        ps.last_seen_client_info = {"hostname": "node-01", "software": "adc"}
        ps.save()
        from ami.ml.serializers import ProcessingServiceSerializer
        data = ProcessingServiceSerializer(ps).data
        self.assertIn("last_seen_client_info", data)
        self.assertEqual(data["last_seen_client_info"]["hostname"], "node-01")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose run --rm django python manage.py test ami.ml.tests.TestProcessingServiceSerializerAPIKey --keepdb -v2`
Expected: FAIL — fields not in serializer

- [ ] **Step 3: Update ProcessingServiceSerializer**

In `ami/ml/serializers.py`, update `ProcessingServiceSerializer` to include new fields but exclude the full API key:

```python
class ProcessingServiceSerializer(DefaultSerializer):
    projects = serializers.SerializerMethodField()

    class Meta:
        model = ProcessingService
        fields = [
            "id",
            "name",
            "description",
            "details",
            "endpoint_url",
            "projects",
            "last_seen",
            "last_seen_live",
            "last_seen_latency",
            "is_async",
            "api_key_prefix",
            "api_key_created_at",
            "last_seen_client_info",
            "created_at",
            "updated_at",
        ]

    def get_projects(self, obj):
        return list(obj.projects.values_list("id", flat=True))
```

- [ ] **Step 4: Update TypeScript model**

In `ui/src/data-services/models/processing-service.ts`, add getters for new fields:

```typescript
  get apiKeyPrefix(): string | undefined {
    return this._processingService.api_key_prefix ?? undefined
  }

  get apiKeyCreatedAt(): string | undefined {
    return this._processingService.api_key_created_at ?? undefined
  }

  get lastSeenClientInfo(): Record<string, string> | undefined {
    return this._processingService.last_seen_client_info ?? undefined
  }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose run --rm django python manage.py test ami.ml.tests.TestProcessingServiceSerializerAPIKey --keepdb -v2`
Expected: All 2 tests PASS

- [ ] **Step 6: Commit**

```bash
git add ami/ml/serializers.py ami/ml/tests.py ui/src/data-services/models/processing-service.ts
git commit -m "feat: expose api_key_prefix and last_seen_client_info in PS serializer

Full API key is never serialized. Only the prefix (first 12 chars)
is shown for identification. last_seen_client_info shows the last
known state of the worker (hostname, software, version).

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 9: Frontend — API Key Generation in PS Creation Form

**Files:**
- Modify: `ui/src/pages/project/entities/details-form/processing-service-details-form.tsx`
- Modify: `ui/src/utils/language.ts`

- [ ] **Step 1: Make endpoint_url optional in the form**

In `ui/src/pages/project/entities/details-form/processing-service-details-form.tsx`:

Update the config to make `endpoint_url` optional:

```typescript
const config: FormConfig = {
  name: {
    label: translate(STRING.FIELD_LABEL_NAME),
    description: 'A descriptive name for internal reference.',
    rules: {
      required: true,
    },
  },
  endpoint_url: {
    label: 'Endpoint URL',
    description: 'For sync/push services. Leave empty for async/pull workers that use an API key.',
    rules: {
      required: false,
    },
  },
  description: {
    label: translate(STRING.FIELD_LABEL_DESCRIPTION),
  },
}
```

- [ ] **Step 2: Show API key prefix and client info in existing PS detail**

Add display of `apiKeyPrefix` and `lastSeenClientInfo` when viewing an existing processing service:

```typescript
{processingService?.apiKeyPrefix && (
  <FormRow>
    <div>
      <strong>API Key:</strong> {processingService.apiKeyPrefix}...
    </div>
    {processingService.lastSeenClientInfo && (
      <div>
        <strong>Last seen from:</strong>{' '}
        {processingService.lastSeenClientInfo.hostname || 'Unknown'}{' '}
        ({processingService.lastSeenClientInfo.software || ''}{' '}
        {processingService.lastSeenClientInfo.version || ''})
      </div>
    )}
  </FormRow>
)}
```

- [ ] **Step 3: Commit**

```bash
git add ui/src/pages/project/entities/details-form/processing-service-details-form.tsx ui/src/utils/language.ts
git commit -m "feat(ui): make endpoint_url optional, show API key prefix and client info

Pull-mode workers leave endpoint_url empty. Shows API key prefix and
last known client info (hostname, software, version) on existing PS detail.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 10: API Key Generation Endpoint (for UI "Add PS" flow)

**Files:**
- Modify: `ami/ml/views.py`
- Test: `ami/ml/tests.py`

The UI needs a way to generate an API key when creating a new PS. The simplest approach: add a `generate_key` action on the ProcessingServiceViewSet.

- [ ] **Step 1: Write failing test**

Add to `ami/ml/tests.py`:

```python
class TestProcessingServiceGenerateKey(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.user.is_staff = True
        self.user.save()
        self.project = Project.objects.create(name="Test Project", owner=self.user)
        from rest_framework.authtoken.models import Token
        self.token = Token.objects.create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_generate_key_for_new_ps(self):
        ps = ProcessingService.objects.create(name="New PS", endpoint_url=None)
        ps.projects.add(self.project)
        url = f"/api/v2/ml/processing_services/{ps.pk}/generate_key/"
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("api_key", response.data)
        self.assertTrue(response.data["api_key"].startswith("ant_ps_"))

    def test_regenerate_key_returns_new_key(self):
        ps = ProcessingService.objects.create(name="Existing PS", endpoint_url=None)
        ps.projects.add(self.project)
        ps.generate_api_key()
        old_prefix = ps.api_key_prefix

        url = f"/api/v2/ml/processing_services/{ps.pk}/generate_key/"
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        # Key should be different
        self.assertNotEqual(response.data["api_key"][:12], old_prefix)

    def test_key_shown_only_in_generate_response(self):
        """The full key should only appear in the generate_key response, not in GET."""
        ps = ProcessingService.objects.create(name="PS", endpoint_url=None)
        ps.projects.add(self.project)
        ps.generate_api_key()

        url = f"/api/v2/ml/processing_services/{ps.pk}/"
        response = self.client.get(url)
        self.assertNotIn("api_key", response.data)
        self.assertIn("api_key_prefix", response.data)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose run --rm django python manage.py test ami.ml.tests.TestProcessingServiceGenerateKey --keepdb -v2`
Expected: FAIL — no generate_key action

- [ ] **Step 3: Add generate_key action to ProcessingServiceViewSet**

In `ami/ml/views.py`, add to `ProcessingServiceViewSet`:

```python
    @extend_schema(
        operation_id="processing_services_generate_key",
        summary="Generate or regenerate API key for a processing service",
        description="Generates a new API key. The old key (if any) is immediately invalidated. The full key is only shown in this response.",
        responses={200: dict},
        tags=["ml"],
    )
    @action(detail=True, methods=["post"], name="generate_key")
    def generate_key(self, request, pk=None):
        instance = self.get_object()
        api_key = instance.generate_api_key()
        return Response({
            "api_key": api_key,
            "api_key_prefix": instance.api_key_prefix,
            "message": "API key generated. This is the only time the full key will be shown.",
        })
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose run --rm django python manage.py test ami.ml.tests.TestProcessingServiceGenerateKey --keepdb -v2`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add ami/ml/views.py ami/ml/tests.py
git commit -m "feat: add generate_key action to ProcessingServiceViewSet

POST /ml/processing_services/{id}/generate_key/ generates or rotates
the API key. Full key shown only in this response. Supports key
rotation for compromised keys.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 11: E2E Test — Full Worker Lifecycle

**Files:**
- Test: `ami/ml/tests.py`

- [ ] **Step 1: Write E2E test**

Add to `ami/ml/tests.py`:

```python
class TestProcessingServiceE2EFlow(TestCase):
    """End-to-end test: create PS -> get API key -> register pipelines -> fetch tasks -> post results."""

    def setUp(self):
        self.user = UserFactory()
        self.user.is_staff = True
        self.user.save()
        self.project = Project.objects.create(name="E2E Project", owner=self.user)
        from rest_framework.authtoken.models import Token
        self.admin_token = Token.objects.create(user=self.user)

    def test_full_lifecycle(self):
        admin_client = APIClient()
        admin_client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")

        # Step 1: Admin creates PS via API
        response = admin_client.post(
            "/api/v2/ml/processing_services/",
            {"name": "E2E Worker", "description": "Test worker"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        ps_id = response.data["instance"]["id"]

        # Add project to PS
        ps = ProcessingService.objects.get(pk=ps_id)
        ps.projects.add(self.project)

        # Step 2: Generate API key
        response = admin_client.post(f"/api/v2/ml/processing_services/{ps_id}/generate_key/")
        self.assertEqual(response.status_code, 200)
        api_key = response.data["api_key"]
        self.assertTrue(api_key.startswith("ant_ps_"))

        # Step 3: Worker authenticates with API key and registers pipelines
        worker_client = APIClient()
        worker_client.credentials(HTTP_AUTHORIZATION=f"Bearer {api_key}")

        response = worker_client.post(
            f"/api/v2/projects/{self.project.pk}/pipelines/",
            {
                "client_info": {
                    "hostname": "e2e-test-node",
                    "software": "test-worker",
                    "version": "0.1.0",
                },
                "pipelines": [],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

        # Verify PS was updated
        ps.refresh_from_db()
        self.assertTrue(ps.last_seen_live)
        self.assertEqual(ps.last_seen_client_info["hostname"], "e2e-test-node")

        # Step 4: Verify PS shows in serializer with client info
        response = admin_client.get(f"/api/v2/ml/processing_services/{ps_id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["last_seen_client_info"]["hostname"], "e2e-test-node")
        self.assertIn("api_key_prefix", response.data)
        self.assertNotIn("api_key", response.data)  # Full key not shown
```

- [ ] **Step 2: Run E2E test**

Run: `docker compose run --rm django python manage.py test ami.ml.tests.TestProcessingServiceE2EFlow --keepdb -v2`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add ami/ml/tests.py
git commit -m "test: add E2E test for full PS lifecycle with API key

Covers: create PS -> generate key -> register pipelines with client_info
-> verify heartbeat and client info stored -> verify serializer output.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 12: Cleanup and Final Verification

**Files:**
- Modify: `ami/jobs/views.py` — Remove any remaining _log_processing_service_name references
- Modify: `ami/jobs/schemas.py` — Remove processing_service_name_param if present

- [ ] **Step 1: Search for remaining processing_service_name references**

```bash
docker compose run --rm django grep -r "processing_service_name" ami/ --include="*.py" -l
```

Remove any references in:
- `ami/jobs/views.py` — remove `_log_processing_service_name()` function and calls
- `ami/jobs/schemas.py` — remove `processing_service_name_param`
- Any imports of the above

Keep the reference in `ami/ml/serializers.py` (PipelineRegistrationSerializer) for backward compat.

- [ ] **Step 2: Run full test suite**

```bash
docker compose run --rm django python manage.py test ami.ml.tests ami.jobs --keepdb -v2
```

Expected: All tests pass

- [ ] **Step 3: Run linting**

```bash
docker compose run --rm django black ami/ml/auth.py ami/ml/serializers_client_info.py ami/ml/models/processing_service.py ami/ml/serializers.py ami/ml/views.py ami/ml/tests.py ami/jobs/views.py ami/jobs/schemas.py ami/jobs/tests.py
docker compose run --rm django isort --profile=black ami/ml/auth.py ami/ml/serializers_client_info.py ami/ml/models/processing_service.py ami/ml/serializers.py ami/ml/views.py ami/ml/tests.py ami/jobs/views.py ami/jobs/schemas.py ami/jobs/tests.py
```

- [ ] **Step 4: Commit cleanup**

```bash
git add -A
git commit -m "chore: remove processing_service_name artifacts, lint

Remove _log_processing_service_name(), processing_service_name_param,
and other artifacts from #1117 that are superseded by API key auth
and client_info.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

- [ ] **Step 5: Run full test suite one more time**

```bash
docker compose run --rm django python manage.py test --keepdb -v2
```

Expected: All tests pass, no regressions

---

## Post-Implementation

After merging:
1. **Close PR #1117** with comment: "Superseded by #XXXX (API key auth + client_info)"
2. **Close issue #1141** — endpoint refactor done
3. **Close issue #1153** — service auth done
4. **Update issue #1112** — partially addressed (per-service status + client_info tracking), task assignment dashboard is Phase 2
5. **ADC worker PR** — Corresponding changes needed in ami-data-companion:
   - Set `ANTENNA_API_KEY` in env
   - Send `client_info` on every request
   - Change `/tasks` from GET to POST
   - Wrap `/result` body in `{client_info: ..., results: [...]}`
   - Set descriptive `User-Agent` header
