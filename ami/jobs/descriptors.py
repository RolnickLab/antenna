"""
Describe job types to the Create Job dialog, so a form can be generated for any of them.

A job type is described by its docstring (the help text), the scope it needs (which pipeline,
capture set, station or sessions it runs on) and an optional pydantic ``config_schema`` for its
settings. The dialog renders all three without knowing the job type in advance, which is what lets
a new job type or post-processing task appear in the UI with no frontend work. See
``docs/claude/reference/jobs-panel.md``.
"""

import copy
import dataclasses
import inspect
import typing

import pydantic

# Bumped when the shape of a normalized schema changes, so a deployed client can tell.
SCHEMA_VERSION = 1

# Widget hints a config field can carry, passed as extra keyword arguments to ``pydantic.Field``.
# Pydantic v1 copies unknown ``Field`` keywords into the field's JSON Schema unchanged.
WIDGET_KEY = "ami_widget"
ENTITY_KEY = "ami_entity"
ENTITY_FILTERS_KEY = "ami_entity_filters"


@dataclasses.dataclass(frozen=True)
class ScopeField:
    """One thing a job runs on, chosen before its settings.

    ``field`` is the name the dialog sends. ``target`` says where: ``"job"`` fields are top-level
    serializer fields backed by a Job column (``pipeline_id``, ``source_image_collection_id``),
    ``"config"`` fields go inside ``params["config"]`` because the job has no column for them.
    ``entity`` is the API list route the picker pages through, relative to ``/api/v2/``.
    """

    field: str
    label: str
    entity: str
    required: bool = True
    many: bool = False
    target: typing.Literal["job", "config"] = "job"
    entity_filters: dict[str, str] = dataclasses.field(default_factory=dict)

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


PIPELINE_SCOPE = ScopeField(field="pipeline_id", label="Pipeline", entity="ml/pipelines")
CAPTURE_SET_SCOPE = ScopeField(field="source_image_collection_id", label="Capture set", entity="captures/collections")
STATION_SCOPE = ScopeField(field="deployment_id", label="Station", entity="deployments")


def describe_docstring(obj) -> str:
    """Return the first paragraph of a class docstring, as the help text shown in the dialog."""
    doc = inspect.getdoc(obj) or ""
    return doc.split("\n\n")[0].replace("\n", " ").strip()


def _sentence_case(name: str) -> str:
    words = name.removesuffix("_ids").removesuffix("_id").replace("_", " ").strip()
    return words[:1].upper() + words[1:]


def _inline_refs(node, definitions: dict):
    """Replace ``$ref`` and single-element ``allOf`` with the definition they point to."""
    if isinstance(node, list):
        return [_inline_refs(item, definitions) for item in node]
    if not isinstance(node, dict):
        return node
    if "$ref" in node:
        target = definitions[node["$ref"].split("/")[-1]]
        merged = {**_inline_refs(copy.deepcopy(target), definitions), **{k: v for k, v in node.items() if k != "$ref"}}
        return merged
    if "allOf" in node and len(node["allOf"]) == 1:
        rest = {k: v for k, v in node.items() if k != "allOf"}
        return {**_inline_refs(node["allOf"][0], definitions), **rest}
    return {key: _inline_refs(value, definitions) for key, value in node.items()}


def normalize_config_schema(
    model: type[pydantic.BaseModel],
    exclude: typing.Iterable[str] = (),
) -> dict:
    """Turn a pydantic config model into the JSON Schema subset the dialog renders.

    Inlines definitions, drops the fields in ``exclude`` (scope fields the dialog asks for
    separately, and settings the user may not change), and replaces pydantic's generated
    title-case labels with a sentence-cased one when the task author did not write a title.
    """
    raw = model.schema()
    definitions = raw.pop("definitions", {})
    schema = _inline_refs(raw, definitions)
    excluded = set(exclude)
    properties = {}
    for name, prop in schema.get("properties", {}).items():
        if name in excluded:
            continue
        field_info = model.__fields__[name].field_info
        if field_info.title is None:
            prop["title"] = _sentence_case(name)
        properties[name] = prop
    return {
        "type": "object",
        "title": schema.get("title", model.__name__),
        "properties": properties,
        "required": [name for name in schema.get("required", []) if name in properties],
        "x-ami-schema-version": SCHEMA_VERSION,
    }
