# Processing service registration flow

Branch `feat/processing-service-registration-flow`, based on `integration/taxa-lists`.
Written 2026-09-18.

## The problem

Adding a processing service in the UI is a two-step operation that looks like a one-step
operation. The user fills in the name and endpoint, saves, and the dialog closes. Nothing
on screen says that the service has no pipelines yet, and nothing says that the row action
called "Register pipelines" is what creates them. Users reasonably assume that saving the
service was the whole job, and then find that no pipeline is available to run.

Registration matters more on this branch than it used to. It is now also the moment when
each classifier's taxa list is built from its category map, so skipping it leaves both the
pipelines and the taxa lists missing.

## The current flow

**Backend.** `ProcessingServiceViewSet.create` (`ami/ml/views.py`) saves the service, links
it to the active project in `perform_create`, immediately calls `get_status()` to test the
connection, and returns `{"instance": <serialized service>, "status": <status response>}`
with a 201. Note the envelope: the created entity is nested under `instance`, unlike every
other collection the frontend's generic create hook serves.

`ProcessingServiceViewSet.register_pipelines` is a separate `POST` detail action. It calls
`ProcessingService.create_pipelines()` (`ami/ml/models/processing_service.py`), which fetches
the service's `/info` endpoint, creates or finds a `Pipeline` per configuration, creates a
`ProjectPipelineConfig` per project, registers each algorithm and its category map, and
returns a `PipelineRegistrationResponse`. `project_id` is optional on this action, because
the frontend's row action calls it without one.

The same `create_pipelines()` is reached from two other places: `ProjectPipelineViewSet.create`,
which is how a pull-mode service registers itself and which wraps the call in
`transaction.atomic()`, and `get_or_create_default_processing_service()`, which runs when a
project is created.

**Frontend.** `NewEntityDialog` (`ui/src/pages/project/entities/new-entity-dialog.tsx`) is
generic over entity types and is what the processing-services page opens with `type="service"`.
On success it closed itself after a one-second delay. `usePopulateProcessingService` is the
hook behind the "Register pipelines" row action; it POSTs to `register_pipelines` and
previously discarded the response body.

## The proposed flow

Saving the create form no longer closes the dialog. The dialog switches to a second step,
"Registering pipelines", which fires the registration call straight away for the service
that was just created, shows a spinner while it runs, and then shows what happened: how many
pipelines and algorithms were registered, and one line per classifier saying which taxa list
it was synced into and how many of its labels matched a taxon Antenna already knows. A "Done"
button closes the dialog. On failure the step shows the error with a "Retry" button beside a
"Close" button, so a service saved against a temporarily unreachable endpoint can be
registered without being deleted and recreated.

The "Register pipelines" row action is unchanged, and remains the way to re-register a
service after its pipelines change.

## API contract

`POST /api/v2/ml/processing_services/{id}/register_pipelines/?project_id={id}` returns a
`PipelineRegistrationResponse` (`ami/ml/schemas.py`). This schema is also the contract with
external processing services, which read it when they self-register, so this work only adds
fields and changes none.

The new field is `taxa_lists`, a list of `TaxaListSyncSummary`:

| Field | Meaning |
|----|----|
| `algorithm_key`, `algorithm_name` | which classifier this row describes |
| `status` | `synced`, `queued` (category map too large, handed to a task) or `failed` |
| `labels` | how many labels the category map holds |
| `taxa_list_id`, `taxa_list_name` | the list the algorithm is linked to, once synced |
| `matched` | labels that resolved to a taxon already in Antenna |
| `created_taxa` | always 0 on this path, see the decision below |
| `removed` | taxa dropped because the category map no longer lists them |
| `unresolved` | labels that match no taxon in Antenna yet |
| `error` | the failure message when `status` is `failed` |

Rows appear only for algorithms whose task type is a classification type and whose category
map has labels. A detector produces no row, so a detector-only service returns an empty list.
An algorithm shared by several pipelines in one registration is reported once.

A failure to reach the service's `/info` endpoint still raises and surfaces as an HTTP error,
because nothing was registered. A failure to sync one algorithm's taxa list does not: the
pipelines and algorithms are already written by that point, so that partial success is real
and is reported in the row's `error` rather than discarding the rest of the work. This is a
deliberate, narrow exception to the repository's "raise, don't return sentinels" rule and is
commented as such at the call site.

## Synchronous or background

Measured on a category map of all-new labels, the worst case, a sync costs roughly 0.36 ms
per label: 500 labels took 0.17 s and 5,000 took 1.8 s. A 29,000-label classifier would
therefore hold an HTTP request open for something on the order of ten seconds, on top of the
`/info` fetch that already carries that whole category map over the wire.

The split is by size rather than all-or-nothing, because making every registration
asynchronous would mean the common case — a handful of small classifiers — could no longer
report a finished result in the dialog, which is the entire point of the feature.

`TAXA_LIST_SYNC_INLINE_MAX_LABELS` is 2,000. At or below that the sync runs inline and the
response carries the real counts. Above it, `ami.ml.tasks.sync_algorithm_taxa_list` is
dispatched and the row says `queued`. The dispatch goes through `transaction.on_commit`,
because `ProjectPipelineViewSet.create` calls `create_pipelines` inside an atomic block and a
worker would otherwise be able to pick up the task before the algorithm row is committed.

That 2,000 figure is conservative: it was measured with taxon creation enabled, which the
registration path no longer does, so the real inline cost is now lower. Lowering the constant
later is a one-line change and needs no migration.

## Registration links taxa, it does not create them

`Algorithm.sync_taxa_list()` creates a `Taxon` for every unmatched label by default, and the
`create_taxa_lists_from_category_maps` management command keeps that default. The registration
path deliberately does not.

The taxa it would create carry only the label as a name and whatever rank the category map
declares, with no parent and no GBIF key. Because taxa are matched by name, those bare rows
then shadow the properly structured taxon that a later taxonomy import brings in, and the
import silently leaves the placeholder in place. This is not hypothetical: it was caught in
this branch by fourteen failing class-masking tests in a module that never touched this code.
Creating a default project ran the default processing service's registration, which created
three parentless species, which `create_taxa()` then found by name and never gave a genus.

So registration links the labels the taxonomy already knows and reports the rest as
`unresolved`. The operator sees the count in the dialog and can run the management command,
which creates them deliberately. Linking is reversible; polluting the shared taxonomy is not.

## Open questions for the product owner

1. **Is "unresolved" actionable enough as a number?** A fresh Antenna with an empty taxonomy
   will register a 29,000-label classifier and see "0 of 29,000 labels matched". That is
   honest but it is not a next step. The dialog could link to the taxa list, or offer to run
   the import, but neither exists yet.
2. **Should the dialog wait for a queued sync?** A large classifier currently shows "being
   built in the background" and the user has no signal when it finishes. Polling would need a
   status endpoint or a Job; neither is built. It may be acceptable to leave it, since the
   taxa list appears on the algorithm page once it is ready.
3. **Should registration be automatic on create, with no button at all?** The intermediate
   step was the owner's request, and it does make the two-step nature visible. Running
   registration automatically and showing only the result would be simpler still, at the cost
   of removing the user's ability to skip it.
4. **Classifiers with a blank `task_type`.** Rows are selected by task type, and existing data
   contains algorithms whose task type was never set. Those will be skipped silently. Worth
   deciding whether to backfill the field or to widen the rule.

## Tests

Backend, in `ami/ml/tests.py`:

- a small classifier syncs inline, links a real taxa list, and reports matched counts
- registration links known taxa and creates none, leaving the rest unresolved
- a detector, and a classifier with an empty category map, produce no row
- an algorithm shared by two pipelines is reported once
- a category map above the threshold is queued and dispatches the task with that algorithm's id
- the inline path's query count does not scale with label count, with cachalot disabled
- the `register_pipelines` endpoint returns `taxa_lists` in its JSON body
- a pre-existing pipeline newly configured for a project is not reported as created, and a
  newly created pipeline is reported even when re-registered for a second project
- a newly registered algorithm lands in `algorithms_created`, not `pipelines_created`

Not covered, and worth adding if the flow grows: the frontend has no test for the dialog's
second step, since this area has no component tests to follow.

## Fixed along the way

`create_pipelines()` reused one `created` variable for the pipeline's own creation flag and
for each per-project `ProjectPipelineConfig`'s, so the per-project loop clobbered the
pipeline's value. A pre-existing pipeline was reported as newly created whenever a new
project happened to be configured for it, and a genuinely new pipeline was omitted when the
last project processed already had a config. Separately, newly registered algorithms were
appended to `pipelines_created` instead of `algorithms_created`, so `algorithms_created` was
always empty.

On the frontend, the generic create hook read the new entity's id off the top level of the
response. Processing services nest it under `instance`, so the id was `undefined` and the
registration step would have called `.../processing_services/undefined/register_pipelines/`.
