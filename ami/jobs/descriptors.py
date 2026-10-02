"""
Describe job types to the Create Job dialog, so a form can be generated for any of them.

A job type's settings are a pydantic model; the dialog renders its JSON Schema as is. Labels and
help text are the fields' ``title`` and ``description`` (wrap them in ``gettext_lazy`` and they are
served in the request's language), and a picker is requested with extra ``Field`` keywords, which
pydantic copies into the schema. Use ``typing.Literal`` for choices: pydantic inlines it as an
``enum``, whereas an ``Enum`` class becomes a ``$ref`` the dialog does not follow. See
``docs/claude/reference/jobs-panel.md``.
"""

import dataclasses
import inspect

import pydantic

# Extra ``pydantic.Field`` keywords the dialog reads. ``ami_widget="entity"`` with
# ``ami_entity="<api route>"`` renders a picker over that list endpoint, and the server checks the
# id belongs to the job's project. ``ami_widget="hidden"`` keeps a field out of the form.
# ``ami_advanced=True`` puts a field in the form's collapsed "More settings" group.
ENTITY_KEY = "ami_entity"


@dataclasses.dataclass(frozen=True)
class ScopeField:
    """A Job column the dialog asks for before the settings, such as the pipeline or the station.

    ``field`` is the serializer field the dialog sends; ``entity`` is the API list route the
    picker pages through, relative to ``/api/v2/``.
    """

    field: str
    label: str
    entity: str
    required: bool = True

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


PIPELINE_SCOPE = ScopeField(field="pipeline_id", label="Pipeline", entity="ml/pipelines")
CAPTURE_SET_SCOPE = ScopeField(field="source_image_collection_id", label="Capture set", entity="captures/collections")
STATION_SCOPE = ScopeField(field="deployment_id", label="Station", entity="deployments")


def describe(obj) -> str:
    """The help text shown for a job type or task: its ``description`` attribute, else its docstring."""
    description = getattr(obj, "description", "")
    if description:
        return description
    doc = inspect.getdoc(obj) or ""
    return doc.split("\n\n")[0].replace("\n", " ").strip()


def entity_fields(model: type[pydantic.BaseModel]) -> dict[str, str]:
    """Map each settings field that names a project's rows to its API entity."""
    return {
        name: prop[ENTITY_KEY]
        for name, prop in model.schema().get("properties", {}).items()
        if isinstance(prop, dict) and ENTITY_KEY in prop
    }
