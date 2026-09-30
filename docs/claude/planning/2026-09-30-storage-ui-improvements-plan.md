# Storage source and deployment storage: UI improvements plan

Status: plan, 2026-09-30. Follow-up to the "connect existing files" work (rclone gateway docs, PR TBD).
Scope: a dedicated PR (or two: backend first, UI second). Survey references are `path:line` on `main` at `6740643a`.

## Why

Pointing a deployment at a folder served through a gateway exposed how blind the current forms are: the storage
form hides the `prefix` field the API already accepts, the deployment form only previews the *saved* sub-directory,
nothing validates a regex or a sub-directory before a sync, and creating one deployment per folder is manual.

## Current state (from the survey)

| Area | Today | Refs |
|---|---|---|
| Storage form fields | name, bucket, endpoint_url, public_base_url, access_key, secret_key. `prefix` hidden; `region` not in serializer or form. Secret-key field reads `config.access_key` (label/description bug). | `ui/src/pages/project/entities/details-form/storage-details-form.tsx:118-172`, `:162`; `ami/main/api/serializers.py:1870-1905` |
| Storage validation | only name + bucket required; no URL checks; server errors via `useFormError` → field error or banner | `storage-details-form.tsx:37,44,109-115`; `ui/src/utils/useFormError.ts` |
| Test connection (storage) | `POST /storage/{id}/test/` `{subdir?, regex_filter?}`; only for saved sources; 200 + `connection_successful=true` even for `NoFilesFound`; 400 only when the connection itself fails | `ui/src/pages/project/storage/connection-status.tsx`; `ami/main/api/views.py:2638-2693`; `ami/utils/s3.py:491-580` |
| Deployment form | Storage picker + plain text `Sub directory` / `Regex filter`, hardcoded English labels, no descriptions or rules; preview uses the deployment's **saved** subdir/regex, so live typing shows nothing | `section-source-images.tsx:64-106`; `deployment-details-form/config.ts:39-47` |
| Deployment validation | none server-side for subdir/regex (regex compiled lazily → 500 or opaque error); `data_source_id` queryset not scoped to project/user | `ami/main/models.py:785-786`; `ami/utils/s3.py:229`; `serializers.py:514-519` |
| Prefix listing | helpers `list_projects` (KeyError on empty bucket) and `list_deployments` exist, unexposed, ignore `config.prefix`, no pagination | `ami/utils/s3.py:190-206` |
| Reusable UI | `ComboBox` (cmdk, server-driven search, button-triggered select only); `EntityPicker`; taxon search pattern with `useDebounce` | `ui/src/nova-ui-kit/components/combo-box/combo-box.tsx`; `ui/src/components/taxon-search/` |
| Commands | no `--dry-run` anywhere; closest analogue `import_source_images <deployment_id>` | `ami/main/management/commands/` |

## Work items

### Backend (PR 1)

1. **List child prefixes endpoint.** `GET /storage/{id}/prefixes/?prefix=<sub>&cursor=…` → `{prefixes: [...], truncated: bool, next: cursor}`. ListObjectsV2 with `Delimiter="/"`, honours `config.prefix`, paginates with continuation tokens, returns names without trailing slash. Reuse/replace the two helpers. Permission: same as `test`. Test against MinIO and the rclone gateway (Delimiter support).
2. **Validation on serializers.** `DeploymentSerializer.validate_data_source_regex` (compile), `validate_data_source_subdir` (no leading `/`, no `..`, trim), `data_source_id` queryset scoped to the request's project (permission gap). `StorageSourceSerializer`: since #1449 the URL builder tolerates a missing trailing slash on `public_base_url`, but stored values are not rewritten; decide whether to normalise on save (saving a changed value re-queues `update_public_urls` for every deployment, so probably not). Light URL sanity for `endpoint_url` without rejecting `http://minio:9000`. Expose `region` if we keep it.
3. **Honest test-connection result.** Keep `connection_successful=true` whenever the connection and the listing succeed, including `NoFilesFound` / `NoMatchingFilesFound` (the UI uses that field for the connection pill, and the API only returns the full result when it is true). Surface those two outcomes through `error_code` and add `files_checked` + up to N sample keys so the UI can show a preview list. Add fields, never rename or change existing ones.
4. **`create_deployments_from_subdirs` management command.** Args: `storage_id` positional, `--prefix`, `--regex`, `--name-template "{subdir}"`, `--dry-run` (default on? no: explicit flag, prints a table of subdir → deployment name → file count from a bounded listing), `--sync` (run `sync_captures` per created deployment, or enqueue the sync job), idempotent via `get_or_create(project, data_source, data_source_subdir)`. Uses item 1's helper. `BaseCommand` style with `self.style.SUCCESS/WARNING`.

### UI (PR 2)

5. **Prefix field on the storage form**, with description ("folder inside the bucket; leave empty for the whole bucket"); fix the secret-key config key; add `prefix` getter to `storage.ts` and a typed `ServerStorage`.
6. **Sub-directory autocomplete** on the deployment form: new free-text combobox (Input + cmdd/Popover) fed by item 1 with `useDebounce`; typing filters, arrow keys select, free text still allowed. Same component reusable for the storage `prefix` field.
7. **Live preview** in the deployment form: run the test-connection call with the *form's* current subdir/regex (debounced), show file count + first thumbnail + sample keys; keep gating the Sync button on it. Translate the labels via `STRING`.
8. **Clearer errors**: map server codes (`NoSuchBucket`, `InvalidAccessKeyId`, `SignatureDoesNotMatch`, `NoFilesFound`, `InvalidRegex`, `EndpointConnectionError`) to plain-language messages with the field they belong to; drop the hardcoded `'Please provide a valid sub directory.'`.
9. **"Create deployments from folders"** dialog on the storage source page: preview table from item 1 (folder, proposed name, file count, already-exists flag), checkboxes, create; calls a DRF action that wraps item 4's logic. After the command has proven the flow.

### Other ideas noticed

- Storage form: "Test connection" before first save (needs an unsaved-config test endpoint or a two-step create).
- Show the resolved full URI (`s3://bucket/prefix/subdir/`) live under the deployment fields; `Deployment.data_source_uri()` already builds it.
- A "gateway preset" button on the storage form that fills endpoint/public URL for the `local-files` compose profile.

## Order

Backend PR first (items 1–4, all testable without UI, the command delivers value on day one), then UI PR (5–9). Items 5 and 6 are the biggest day-to-day win for people setting up many deployments.
