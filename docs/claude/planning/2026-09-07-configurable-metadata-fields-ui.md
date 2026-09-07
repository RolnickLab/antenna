# Metadata fields on the station and device-type forms

Date: 2026-09-07
Issue: RolnickLab/antenna#507, "Add generic metadata JSON fields"
Scope: the frontend half only. The API field itself is being added on a separate branch.

## What this gives an operator

A project can now record properties of a station or a device type that the platform has
no field of its own for — the height of a mast, the wattage of a lamp, a local site code —
without waiting for those to become columns in the database. Both the station form and the
device-type form gained a "Metadata" box that holds free-form JSON. It reads back whatever
is already stored, and a mistake in the JSON is reported next to the box during editing
rather than coming back as a server error after saving. A record with broken JSON in
that box cannot be saved at all.

The field is a monospace text box with inline errors. The syntax highlighting the ticket
offers as an optional extra is not part of it; see "What this does not do" below.

## The contract this is built against

The API exposes a writable `metadata` field on the station (deployment) and device-type
records. It is a free-form JSON object, and it is an empty object when the record has no
metadata. Nothing here assumes any particular key inside it.

## How it is put together

### The field itself

`ui/src/components/form/metadata-field.tsx` is a textarea wired to react-hook-form through
the existing `FormController`, in the same shape as `form-field.tsx`. It reuses
`InputContent` from `nova-ui-kit` for the label, description and inline error, so it looks
like every other field on those forms.

The form value is the JSON *text*, not a parsed object. That is the decision the rest of
the design follows from. A half-finished edit — an object with one quote missing — has no
object representation, so storing text is what lets the operator keep looking at their own
work while the error tells them what is wrong with it. It also preserves the key order and
indentation they chose rather than reformatting the box underneath them.

### The three helpers

All three live in `ui/src/utils/fieldProcessors.ts`, next to the existing
`parseIntegerList` / `formatIntegerList` / `validateIntegerList` trio, which solve exactly
the same "structured value edited as text" problem for comma-separated ID lists.

- `formatMetadata(value)` renders a stored object as indented JSON for the field, and
  renders a record with no metadata as an empty box rather than a bare `{}`.
- `parseMetadata(text)` turns the text back into the object the API stores. An empty box
  becomes `{}`, which is how the API represents "no metadata".
- `validateMetadata(text)` is the `validate` rule in each form's field config. It accepts
  an empty box, rejects text that does not parse, and rejects text that parses into
  something other than an object — a list, a number, a bare string — because the API
  stores an object and nothing else.

`ui/src/utils/fieldProcessors.test.ts` covers all three, including the accept cases as
well as the reject cases, so a rule that silently stopped rejecting anything would fail.

### The station form

The station form is the multi-section dialog under
`ui/src/pages/deployment-details/deployment-details-form/`. The field sits in the General
section, full width beneath the two-column rows.

- `config.ts` declares the label, the guidance text and the `validateMetadata` rule.
- `deployment-details-form.tsx` seeds the General section's stored value with
  `formatMetadata(deployment.metadata)`.
- `section-general/section-general.tsx` renders the field.
- `data-services/models/deployment-details.ts` adds the `metadata` getter that reads the
  stored object, and `metadata` to `DeploymentFieldValues` as the JSON text a submit
  carries.

Invalid JSON blocks the save because the dialog's Save button is already disabled while any
section reports itself invalid (`deployment-details-form.tsx`, the `allValid` check in
`SaveButton`), and `useSyncSectionStatus` feeds each section's validity into that.

The two halves of that check run on different schedules, which is worth knowing before
reading a bug report about it. The Save button goes dead the moment the JSON stops being
valid, because react-hook-form keeps `isValid` current on every keystroke, but the message
under the box appears only when the field loses focus, because the General section
validates on blur. That difference is deliberate and is explained under "What this does
not do".

The station endpoint takes a multipart request, because the form can also carry a cover
image. A multipart request can only carry text, so `data-services/hooks/deployments/utils.ts`
serialises the object and appends it as JSON. Django REST Framework's `JSONField` parses a
string back into an object when the request came in as form input, so the field arrives at
the serializer as the object it is meant to be. This is the one seam between the two halves
of the ticket that is worth checking on a running stack: it holds as long as the API's
`metadata` field is a plain DRF `JSONField`, which is what a `ModelSerializer` generates
for a `models.JSONField`.

### The device-type form

Device types are edited through the shared entity dialog, which picks a form per entity
type from `customFormMap` in
`ui/src/pages/project/entities/details-form/constants.ts`. Storage sources, capture sets,
exports and processing services already have their own forms there; device types were still
using the default name-and-description form.

- `device-details-form.tsx` is a new entry in that map, keyed `device`. It is the default
  entity form plus the metadata field.
- `data-services/models/device.ts` adds a `Device` model with the `metadata` getter, and
  `data-services/hooks/entities/useEntities.ts` constructs it for the devices collection.
  Reading the field through a model of its own keeps `Entity` — the base class sites,
  exports and everything else share — free of a field only device types have.

That endpoint takes a JSON body, so the object goes over the wire as an object, through the
existing `customFields` mechanism in `data-services/hooks/entities/utils.ts`. No change was
needed there. Invalid JSON blocks the save because react-hook-form only runs the submit
handler once every field has passed its rules.

### Strings

`FIELD_LABEL_METADATA`, `MESSAGE_METADATA_DESCRIPTION`, `MESSAGE_METADATA_INVALID` and
`MESSAGE_METADATA_NOT_OBJECT` were added to `ui/src/utils/language.ts`, in both the `STRING`
enum and the English display map.

## What still needs to be verified

Everything below needs the API field, so none of it could be checked while writing this.

1. **A round trip through the station endpoint.** Save metadata on a station, reload the
   dialog, confirm the box shows the same keys. This is what proves the multipart JSON
   parsing described above, and it is the single most likely place for the two halves of
   the ticket to disagree.
2. **A round trip through the device-type endpoint**, the same way.
3. **Clearing the box.** Emptying the field should leave the record with an empty object,
   not a literal empty string and not the previous value.
4. **A station saved from the "new station" dialog**, which goes through
   `useCreateDeployment` rather than `useUpdateDeployment`.

## What this does not do

Each of these was considered and left out on purpose. None of them is an oversight, and
none needs re-deciding unless the reason underneath it changes.

- **Metadata is not displayed anywhere outside the edit dialogs.** It is absent from the
  station's info view (`ui/src/pages/deployment-details/deployment-details-info.tsx`) and
  from the tables that list device types, so someone browsing stations cannot tell which
  ones carry metadata without opening each one to edit it. Putting raw JSON into a table
  column is a layout question with several defensible answers — truncate the text, show a
  key count, show a badge — and choosing one silently seemed worse than leaving it for
  whoever picks up that decision.
- **The field does not highlight JSON syntax**, which the ticket offers as an optional
  extra. Every route to it means adding a code-editor dependency such as CodeMirror or
  Monaco to a bundle that has no code editor today, and that is too large a cost for an
  optional nicety. The field uses a monospace face and reports its errors inline instead,
  and only `ui/src/components/form/metadata-field.tsx` would have to change if the team
  later decides the dependency is worth it.
- **The two forms do not report errors on the same schedule.** The station form shows the
  message when the field loses focus and the device-type form shows it as you type,
  because each section keeps the validation mode of the fields around it and the station's
  General section validates on blur. Making metadata the one live-validating field there
  would leave it the odd one out, and switching the whole section to on-change validation
  would change the behaviour of fields this work has no business touching — the required
  name would start flashing an error at somebody halfway through typing one. Both forms
  disable Save on the keystroke that breaks the JSON, which is the half that actually
  prevents a bad save.
- **Nothing here has an opinion about what goes inside the object.** The ticket mentions
  that metadata should be queryable in PostgreSQL and publishable to GBIF. Both are
  backend concerns and neither constrains what this form accepts.

One thing that is a limit rather than a choice: rejecting a non-object is a guard on this
one client, not an enforcement of the contract. The form refuses a bare list, string or
number before it can be saved, but the admin, the browsable API and any future uploader
all bypass this form, so the API has to make the same check for itself.

## Related

- `docs/claude/reference/react-form-to-drf-values.md` — how form values reach DRF, and why
  empty strings and nulls are not interchangeable. The `{}`-for-empty rule here is the
  JSON-object version of the same question.
