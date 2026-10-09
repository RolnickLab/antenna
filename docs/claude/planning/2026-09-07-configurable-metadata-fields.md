# Configurable metadata fields on stations and device types

Date: 2026-09-07
Status: backend implemented, frontend not started
Scope: the backend half of issue #507 ("Add generic metadata JSON fields"). The text
field with syntax validation and highlighting that the issue also asks for is a
frontend change and is not part of this work.

## Goal

Antenna models natively only the attributes that every project shares. Real deployments
carry more: the height a camera was mounted at, a description of the habitat, the make
of a light, the serial number of a controller. Today there is nowhere to record any of
that except free text in the description, where nothing can be searched or exported.

This change gives a station (`Deployment`) and a device type (`Device`) a `metadata`
field, an open JSON object that the people who may already edit the record can write
whatever they need into. Because the column is stored as Postgres `jsonb`, individual
keys inside it can be queried in SQL, and because each entry is a named key rather than
a sentence, an entry can later be mapped onto a term when records are published to GBIF.

## The one rule: metadata is an object

The contents are deliberately unconstrained. No fixed schema would fit, because the
attributes worth recording differ from one project to the next, which is the premise of
the issue. What is constrained is the shape: the value must be a JSON object of
key/value pairs. A bare array, string, number or boolean is refused.

The reason is that the shape is what makes the field useful rather than a matter of
taste. A value with no field names in it leaves a Postgres key lookup nothing to match
and a published term nothing to map onto, so accepting one would quietly produce rows
that no later feature can read. Refusing it at the point of writing keeps every stored
value queryable.

Refusing an array is a decision, not an oversight. The discussion on issue #307 floated
modelling metadata as an array of `{title, value}` pairs, and that shape is deliberately
closed off. An object gives Postgres a key to index and look up, and gives a published
term something to map onto. An array of pairs gives neither unless the reader already
knows a private convention for what `title` and `value` mean. Anyone who genuinely needs
ordered pairs can still hold them in an array *under a key* —
`{"attributes": [{"title": ..., "value": ...}]}` — which keeps the outer shape queryable
and loses nothing.

This is a deliberate departure from `Project.feature_flags`, the other JSON column on
these models' neighbours. That field is a `SchemaField` backed by the pydantic model
`ProjectFeatureFlags` (`ami/main/models.py`, `ProjectFeatureFlags`, around line 271),
because its keys are a closed set that the code itself reads by name. Metadata is the
opposite case — the keys belong to the operator, not to the code — so it is a plain
`models.JSONField` with a single shape check rather than a schema.

## Where the code is

- `ami/main/models.py`, `validate_metadata_object` (around line 647) — the shape check,
  raising a `ValidationError` that names the JSON type it received. `_JSON_TYPE_NAMES`
  just above it turns a Python type into the word a JSON author would recognise, so the
  API error reads "not an array" rather than "not a list".
- `ami/main/models.py`, `metadata_field` (around line 664) — builds the column. Both
  models call it rather than repeating the keyword arguments, so the two columns cannot
  drift apart in their default, their validation or the help text an API client reads.
- `ami/main/models.py`, `Device.metadata` (around line 694) and `Deployment.metadata`
  (around line 822) — the two columns.
- `ami/main/api/serializers.py`, `DeviceSerializer.Meta.fields` (around line 1791) and
  `DeploymentSerializer.Meta.fields` (around line 538) — the exposure.
- `ami/main/migrations/0096_deployment_metadata_device_metadata.py` — one migration
  adding both columns.

**Known merge step:** three open branches each number their migration `0096` — this one,
the deployment status heartbeat work, and a model-coverage backfill. Whichever lands
second and third has to be renumbered onto the new head. Renumbering ahead of time only
moves the collision, so it is left for merge time. The heartbeat branch also adds columns
to `Deployment`, so it may merge cleanly against this file while still needing that
rename; a clean merge is not evidence of a correct one here.

## Two decisions worth knowing about

**The field is on the deployment detail endpoint, not the list.** `DeploymentSerializer`
extends `DeploymentListSerializer`, so adding a field to the parent would have put every
station's metadata blob into every row of the stations list. The field has no size limit
by design, and the list endpoints in this codebase have repeatedly been the ones with
performance problems, so the metadata is served from `GET /api/v2/deployments/{id}/` and
written there too. `Device` has a single serializer and no such split, so its metadata
appears on both its list and its detail response.

**No new permission was introduced.** Both `DeploymentViewSet` and `DeviceViewSet` use
`ObjectPermission` (`ami/base/permissions.py`, `ObjectPermission`), which delegates to
`BaseModel.check_permission` and thence to the existing `update_deployment` and
`update_device` guardian permissions. A writable serializer field is therefore covered
by the same rule that already governs renaming a station: a project manager may write
metadata, a basic member may read it and gets a 403 if they try to write. The test suite
pins this rather than assuming it.

One consequence worth stating, because it is easy to miss: Django model validators are
copied onto the serializer field by DRF's `get_field_kwargs`, so the single validator on
the model governs the API write path, the Django admin and any direct `full_clean()`
alike. There is no separate serializer-level check to keep in step.

## The form-encoded seam, and why the field is left auto-generated

A station is edited through a form submitted as `multipart/form-data`, because the record
carries a cover image. Multipart has no JSON types, so `metadata` reaches the server as a
string containing JSON rather than as an object. Storing that string verbatim would look
like a success at the time and surface much later, when something reads the row back and
finds text where a mapping should be.

The field is therefore left for `ModelSerializer` to generate from the model, which makes
it a plain `serializers.JSONField`. That class marks a value taken from form input as a
JSON string and runs `json.loads` on it, so an object is what reaches the column. Anything
that overrides how the value is read — a `CharField`, or a subclass with its own
`get_value` — takes the plain-string branch instead and stores the text. Declaring
`metadata` explicitly is safe only as `serializers.JSONField`; declaring it as anything
else silently changes what is stored, which is why it is not declared at all.

The shape rule is enforced on the server rather than in the form. The station form
refuses a bare array, a quoted string, a number, `true` and `null` before they leave the
browser, but the Django admin, the browsable API and any other client bypass that form
entirely. The validator on the model is what makes "an object, or nothing" an invariant
instead of one client's good manners, and the tests exercise all five shapes against the
endpoint itself.

## Testing

`ami/main/tests.py`, `TestConfigurableMetadataFields` (around line 6602), seven tests
covering both models:

1. A nested object containing numbers, strings, a sub-object and an array is written
   through the API and read back on a fresh request unchanged.
2. An array, a string, a number and a boolean are each refused with a 400 that blames
   the `metadata` field, and the stored value is confirmed untouched afterwards.
3. A basic member can read the record but is refused the write with a 403, and the
   stored value is again confirmed untouched.
4. A record created without metadata holds `{}`; `null` is refused by the API, and the
   column itself raises `IntegrityError` on a null, so no code path can leave one behind
   for a reader to guard against.
5. `null` is refused on both write paths, which reject it by different mechanisms: as
   JSON it is stopped before the shape check because the field is not nullable, while
   through the form it arrives as the text `null`, is parsed to `None`, and the shape
   check refuses it. A change to either mechanism would leave the other looking correct,
   so both are pinned.
6. A station update submitted as `multipart/form-data` with metadata as JSON text stores
   an object, asserted by type rather than by value so that a stored string cannot pass.
7. The same form-encoded path refuses an array, a quoted string, a number, `true`, `null`
   and text that is not JSON at all, and leaves the stored value untouched.

Run them the way the rest of the suite is run against a worktree, per
`docs/claude/reference/worktree-testing.md`:

```
python manage.py test ami.main.tests.TestConfigurableMetadataFields
```

## Not done here

- **The frontend text field.** Issue #507 asks for a text field that validates and
  ideally highlights JSON syntax. Nothing in the UI has been touched.
- **A GIN index on either column.** `jsonb` is queryable without one, which satisfies
  what the issue asks for. An index is a performance question that should be answered by
  a real query pattern rather than added speculatively.
- **The GBIF mapping itself.** This change makes a published mapping possible by giving
  the values names; it does not decide which keys map onto which terms. That decision
  belongs with the export work.
- **`Site`.** Issue #507 names deployments and device types only. Sites are the natural
  next candidate; see the section below for what issue #307 wants of them.

## Relationship to issue #307

Issue #307 ("Allow meta data to be configured for Deployments") asks for the same
capability and supplies the motivating examples — hardware, habitat, camera height —
that this change serves. Those examples are now recordable, so the part of #307 that is
about deployment owners having somewhere to put this information is covered.

Three things it asks for are not, and #307 should stay open for them rather than being
closed by #507.

- **Standard fields alongside the generic object.** The discussion on #307 settles on
  "some of both": a few standard fields that the interface can filter and chart on, plus
  a generic object for everything else. This change ships only the generic object. Which
  attributes graduate into native fields is a question for the standards and metadata
  working group, not for the backend.
- **Ecological Metadata Language, and Site.** #307 proposes describing a research site's
  ecology with EML, on the `Site` model. That is a schema question rather than a
  free-form one, and this change adds no `Site` column and takes no position on EML.
- **Tagging as an alternative route.** #307 raises a tagging system as a possible answer
  instead, one that would extend to occurrences and captures as well. Nothing here
  forecloses that, and nothing here delivers it.

One shape decision is worth flagging to anyone returning to #307, because a different
one was floated there: the discussion included an example that modelled metadata as an
array of `{title, value}` pairs. This change refuses arrays. Named keys in an object are
what make a Postgres key lookup and a term mapping possible, and an array of pairs would
have to be unpacked before either could work.
