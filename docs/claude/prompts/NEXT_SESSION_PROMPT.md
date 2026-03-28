# Next Session: Processing Service API Keys — Frontend + Cleanup

## Branch
`feat/processing-service-auth-and-identity`

## Plan
`docs/superpowers/plans/2026-03-27-processing-service-api-keys.md`

## Status
Tasks 1–8 are committed. Backend is complete and all 109 tests pass. Remaining work is frontend (Task 9), optional management command (Task 10), and cleanup (Task 11).

## What to Do
Start from Task 9 in the plan: frontend changes for the processing service detail view.

Key things:
- Add `api_key_prefix`, `api_key_created_at`, `last_seen_client_info` to the TypeScript ProcessingService model
- Add "Generate API Key" button that calls `POST /api/v2/processing_services/{id}/generate_key/` and shows the full key once
- Make `endpoint_url` optional in the PS creation form (async/pull services don't have one)
- Show `last_seen_client_info` in the PS detail view

After frontend, do Task 11 (cleanup: remove unused schema params, linting, OpenAPI regen).

## Key Design Decisions
- Auth backend returns `(AnonymousUser(), ps)` — identity on `request.auth`, not `request.user`
- `HasProcessingServiceKey` permission class checks project membership via PS's `projects` M2M
- Follows `djangorestframework-api-key` pattern (permission class, not user object)
- See "Research: API Key Auth Patterns in DRF" section in the plan for rationale
