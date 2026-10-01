# InvokeAI: how a graph-execution app stores sessions, intermediate tensors, images and models

**Question.** InvokeAI is a node/graph image-generation app with SQLite plus disk storage. How
does it store a workflow execution and per-node outputs, where do intermediate tensors live,
how do images keep provenance back to the run, how are model records and lineage kept, how does
its schema evolve, and is there anything review-like? What transfers to a platform storing ML
outputs, intermediate results and derived models?

**Produced by.** A research agent (Claude Sonnet), 2026-10-01, supervised. Source files were
read directly through raw fetches at commit `a51e26fe24a1d680feba35d3309c14002115d200`
(main); permalink prefix `https://github.com/invoke-ai/InvokeAI/blob/a51e26fe/`.

## 1. Session and graph execution storage

- One row per execution request: `session_queue`
  (`invokeai/app/services/shared/sqlite_migrator/migrations/migration_1.py#L208`) with an integer
  `item_id` primary key, `batch_id`, `queue_id`, unique `session_id`, `status`, `priority`,
  error fields, timestamps.
- The whole session is one JSON text column (`session TEXT NOT NULL`, `migration_1.py#L214`),
  plus `field_values` and later `workflow` (`migration_2.py#L43`).
- That JSON is the full execution state: `GraphExecutionState`
  (`invokeai/app/services/shared/graph.py#L2356`) holds `graph`, `execution_graph`, `executed`,
  `executed_history`, `results: dict[node_id, output]`, `errors`, `prepared_source_mapping`;
  written with `model_dump_json(exclude_none=True)` (`session_queue_sqlite.py#L1163`); the code
  comment says persisted sessions are used to resume execution.
- Per-node outputs have no table or column; each sits inside the session JSON under its node id.
  The key is (queue item, node id).
- A separate `graph_executions` table was dropped in `migration_5.py` because graph storage went
  purely in-memory. A `migration_1.py` comment says a foreign key was avoided because
  `INSERT OR REPLACE` triggers `ON DELETE CASCADE`.
- Later columns added one `ALTER` at a time: `error_type`, `origin`, `destination`,
  `retried_from_item_id`, `user_id`, `status_sequence`, `device`, workflow-call parent/root ids
  (migrations 10, 15, 16, 27, 30 and the 2026_07_01 modules).
- Retention is bounded: startup cancels in-progress items and prunes terminal items to
  `max_queue_history` (`session_queue_sqlite.py#L133-L148`).

## 2. Intermediate results (tensors, latents, conditioning)

- On disk, not in the DB: `ObjectSerializerDisk`
  (`invokeai/app/services/object_serializer/object_serializer_disk.py#L25`) saves with
  `torch.save` and returns a generated name `"{ClassName}_{uuid}"`.
- Two stores (`invokeai/app/api/dependencies.py#L152-L170`): `outputs/tensors` for
  `torch.Tensor` and `outputs/conditioning` for `ConditioningFieldData`, both wrapped in
  `ObjectSerializerForwardCache`, a write-through LRU with a default of 20 items
  (`object_serializer_forward_cache.py#L19`).
- The tensors store is ephemeral: a temp directory removed on stop; stale `tmp*` directories
  from a crash are deleted at startup (`object_serializer_disk.py#L43-L50`). The conditioning
  store was not marked ephemeral in the lines read.
- Node outputs hold only a name: `TensorField.tensor_name`, `LatentsField.latents_name`
  (`invokeai/app/invocations/fields.py#L289-L298`).
- Names are treated as untrusted input: loads use `weights_only=True` and reject non-plain
  filenames (`object_serializer_disk.py#L60-L80`).
- An in-memory node cache keys on `hash(invocation.model_dump_json(exclude={"id"}))`
  (`invocation_cache_memory.py#L93`); not persisted.

## 3. Images and provenance

- `images` table (`migration_1.py#L99`): `image_name` PK, `image_origin`, `image_category`,
  `width`, `height`, `session_id`, `node_id`, `metadata` TEXT, `is_intermediate`; later `starred`
  (`#L144`), `has_workflow` (`migration_2.py`), `user_id` (`migration_27`), `image_subfolder`
  (`migration_31`).
- Provenance back to the run is plain string columns `session_id` and `node_id`, no foreign keys
  (`invokeai/app/services/image_records/image_records_sqlite.py#L375-L420`).
- The full graph is stored in the file: `image_files_disk.py#L168-L179` writes
  `invokeai_metadata`, `invokeai_workflow`, `invokeai_graph` PNG text chunks. The DB keeps
  metadata JSON and a `has_workflow` flag.
- Intermediates are flagged rows: `is_intermediate`, counted and bulk-deleted by
  `delete_intermediates` (`images_default.py#L476`; `image_records_sqlite.py#L310-L336`); the
  delete carries the predicate so a concurrent promotion is safe.
- Boards are one-to-many via `board_images` with `image_name` as the sole PK; a comment says it
  can become many-to-many later (`migration_1.py#L22`).

## 4. Model records and lineage

- `models` table: `config` TEXT holds the whole pydantic config; `hash`, `base`, `type`, `path`,
  `format`, `name`, `source`, `source_type`, `file_size` are `GENERATED ALWAYS AS
  (json_extract(config, '$.x')) VIRTUAL` columns (`migration_7.py`, `migration_22.py#L23`).
  `UNIQUE(path)` replaced `UNIQUE(name, base, type)` in migration 22.
- Typed configs are a Python class hierarchy: `Config_Base`
  (`invokeai/backend/model_manager/configs/base.py#L31`) with `key` (uuid), `hash`, `path`,
  `file_size`, `source`, `source_type`, `source_api_response`; one subclass per base/type/format
  with a discriminator (`base.py#L136`).
- Graph nodes reference models by value: `ModelIdentifierField`
  (`invokeai/app/invocations/model.py#L60`) carries `key`, BLAKE3 `hash`, `name`, `base`, `type`,
  `submodel_type`, so the hash lands in the session JSON.
- Lineage is shallow: `model_relationships` (`migration_20.py`) is a symmetric many-to-many
  (`model_key_1 < model_key_2`), read as "related models", not derivation.
- `migration_7` dropped `model_metadata`, `model_tags`, `tags`; metadata moved into the config.

## 5. Schema evolution

- Numbered modules `migration_1..33`, plus newer date-stamped modules with a `depends_on` graph
  (`docs/src/content/docs/development/Guides/sqlite-migrations.mdx`).
- The DB file is backed up before running (`sqlite_migrator_impl.py#L79`); callbacks must not
  commit; failure rolls back.
- Normalised: queue, images, boards, users, workflows. Kept as JSON: session, field_values,
  image metadata, model config.
- JSON fields promoted lazily with generated virtual columns (`workflow_library.tags` in
  `migration_17.py#L17`; the models table).
- Stated rationale only in code comments, e.g. "enum in python, unrestricted string here for
  flexibility" (`migration_1.py#L103`).

## 6. Human-in-the-loop

Thin: boolean `images.starred` and board membership; no ratings, approvals or annotation
tables. State sits on the image row, not on the producing node or queue item.

## Insights that transfer

1. Big arrays live outside the DB; the row or JSON holds only a generated name.
2. Raw execution record = one JSON blob keyed by a run id with a few queryable columns beside it:
   a good model for keeping raw service responses for replay.
3. Normalise only what you filter on; promote JSON fields later via generated or expression
   columns.
4. Their provenance is loose strings with no FK; a platform that joins outputs to reviews needs
   real FKs to a run table.
5. Embed the graph in the artifact (PNG text chunks); the equivalent is a sidecar JSON beside each
   object-storage array.
6. Ephemeral vs persistent is a flag plus a store choice; mark pruneable outputs explicitly.
7. Pin model identity by content hash inside each run; replays survive renames.
8. Naming is plain and role-based (`session_queue`, `images`, `models`, `boards`); they have no
   name for a per-node output, which is a gap for us.
9. Review state on the result row is their weak point; make review records their own table keyed
   to the output row.

## Could not verify

Cleanup of the conditioning store; whether model conversion or merging creates records linking
back to a source model; any PR or issue rationale (PR threads not searched); the 2026_07_03
round-robin index migration, workflow-call tables and video tables.
