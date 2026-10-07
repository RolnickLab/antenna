# Mobile upload API (A1, A5, A2-docs) — #1379

Branch: `feat/mobile-upload-api-a1-a5`. Migration-free. Deploy is the owner's step.

## A1 — `POST /api/v2/deployments/{id}/upload-request/`

Mints short-lived presigned PUT URLs so the mobile client uploads captures
directly to the deployment's storage source, then calls `sync` to ingest them.

- `ami/utils/s3.py`
  - `get_presigned_put_url(config, key, content_type, checksum_sha256_b64, expires_in)`
    → `(url, headers)`. Not cached (per-file, short-lived). The AWS flexible-checksum
    header (`x-amz-checksum-sha256`) is emitted **only** when `endpoint_url is None`
    (real AWS); suppressed for MinIO/Swift because Swift's s3api rejects it.
    `checksum_sha256_b64` is base64 of the raw digest, not hex.
  - `derive_upload_key(config, filename, subdirs)` — builds the full object key
    directly (prefix + cleaned subdir parts + filename). Deliberately NOT
    `key_with_prefix`, whose `split(subdir)` dedup heuristic mangles filenames
    containing the subdir string. The result is exactly the Key `sync_captures`
    stores as `SourceImage.path`, so re-request/re-upload is idempotent
    (uniqueness on `(deployment, path)`).
- `ami/main/models.py` — `Deployment.check_custom_permission` maps
  `"upload_request"` → `SYNC_DEPLOYMENT`. **Load-bearing**: a `detail=True` action
  runs `get_object()` → object permission check, which would otherwise probe the
  nonexistent `upload_request_deployment` guardian perm and 403 every non-superuser.
  Reuses an existing perm — no new perm, no migration.
- `ami/main/api/serializers.py` — `UploadRequest*` request/response serializers.
  `subdir` and per-file `sha256`/`content_type` optional. `MAX_UPLOAD_REQUEST_FILES = 1000`.
- `ami/main/api/views.py` — `upload_request` `@action` on `DeploymentViewSet`.
  Per-file validation → `errors[]` (no URL minted) for: unparseable timestamp,
  non-image extension, path traversal / bad chars, key length > 255, regex mismatch,
  size ≤ 0. 400 for no data source, invalid subdir, or > 1000 files.

## A5 — filters

- `DeploymentFilterSet` exposes `research_site_id` / `device_id` (the exact param
  names the Swift client sends). Set as `filterset_class` on `DeploymentViewSet`.
- `ProjectViewSet` gains `?role=manager` / `?writable=true` → filters to projects
  the user can write via `get_objects_for_user(user, "update_project", Project)`
  (covers ProjectManagers AND owners). Superusers see all; anonymous sees none.
- Sites/devices `?project_id=` already worked (via `get_active_project`); added
  confirming tests only.

## A2 — sync completion (docs only)

`@extend_schema` on the existing `sync` action documents the `{job_id, project_id}`
response, the polling endpoint (`GET /api/v2/jobs/{id}/`), and the THREE terminal
states: `SUCCESS`, `FAILURE`, `REVOKED`. The ≤1/min auto-sync cadence is a
separate follow-up PR (not built here).

## Findings

- **HEIC not supported.** `IMAGE_FILE_EXTENSIONS` (`ami/utils/storages.py`) is
  `jpg/jpeg/png/gif/webp/svg/bmp/ico/tiff/tif` — no `heic`/`heif`. If the mobile
  client uploads HEIC, `upload-request` rejects it with `invalid_extension` (and
  sync would drop it too). Add the extensions if HEIC uploads are required.
- **MinIO checksum:** because the test/MinIO config sets `endpoint_url`, the
  checksum header is never sent to MinIO — the E2E upload path does not exercise
  the checksum branch. That branch only activates against real AWS.

## Tests

- `ami/tests/test_storage.py`: `derive_upload_key` unit tests (incl. None/`/`-only
  subdirs and the filename-matching-subdir regression) and `get_presigned_put_url`
  header/checksum-gating tests (all offline — local signing, no MinIO).
- `ami/main/tests.py`:
  - `TestDeploymentUploadRequest` — permission matrix, no-data-source 400,
    each validation error code, deterministic key, >1000 files, invalid subdir.
    Runs offline (fake AWS source; signing is local).
  - `TestDeploymentUploadRequestE2E` — flagship: mint PUT → `requests.put` →
    `sync_captures()` → assert `SourceImage.path == minted key`. **Needs MinIO.**
  - `TestDeploymentAndProjectFilters`, `TestProjectWritableFilter` — A5 filters.
