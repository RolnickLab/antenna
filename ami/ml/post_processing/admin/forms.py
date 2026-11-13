"""Form base for admin actions that trigger post-processing tasks.

Each post-processing task surfaces its tunable knobs as a Django form. The
form's ``cleaned_data`` becomes the ``config`` payload on the resulting Job
(after validation against the task's pydantic ``config_schema``).

Algorithm scope (which queryset/events/collection the action runs against)
lives outside the form because it varies per admin entry-point.
"""
from __future__ import annotations

from collections.abc import Collection
from typing import Any

import pydantic
from django import forms


class BasePostProcessingActionForm(forms.Form):
    """Marker base for post-processing admin action forms.

    Subclasses declare task-specific fields. Override ``to_config()`` if the
    1:1 ``cleaned_data → config`` mapping needs adjustment (e.g. drop empty
    optional fields, derive computed values, rename keys).
    """

    def __init__(self, *args, scope_queryset=None, **kwargs):
        """Capture the admin selection the action will run on.

        ``scope_queryset`` is the queryset of rows the operator picked (e.g. the
        chosen occurrences or collections). Subclasses may use it to constrain
        their fields to that selection; forms that don't need it ignore it.
        """
        self.scope_queryset = scope_queryset
        super().__init__(*args, **kwargs)

    def to_config(self) -> dict:
        """Return ``cleaned_data`` shaped for ``Job.params['config']``."""
        return dict(self.cleaned_data)


def schema_form_fields(schema: type[pydantic.BaseModel], exclude: Collection[str] = ()) -> dict[str, forms.Field]:
    """Build Django form fields from a pydantic (v1) config schema.

    The schema stays the single source of truth for defaults, titles, help text and numeric bounds.
    Supports ``bool``, ``int`` and ``float`` fields and optional versions of them; an optional field is
    not required and a blank value becomes ``None``. Strict limits (``gt``/``lt``) are left to the
    schema, whose error the admin action shows on the field.
    """
    fields: dict[str, forms.Field] = {}
    for name, model_field in schema.__fields__.items():
        if name in exclude:
            continue
        info = model_field.field_info
        kwargs: dict[str, Any] = {
            "label": info.title or name.replace("_", " ").capitalize(),
            "help_text": info.description or "",
            "initial": model_field.default,
        }
        python_type = model_field.type_
        if python_type is bool:  # bool is checked first because it subclasses int
            fields[name] = forms.BooleanField(required=False, **kwargs)
            continue
        if issubclass(python_type, int):
            field_class: type[forms.Field] = forms.IntegerField
        elif issubclass(python_type, float):
            field_class = forms.FloatField
        else:
            raise TypeError(f"No form field for {schema.__name__}.{name} of type {python_type!r}")
        if info.ge is not None:
            kwargs["min_value"] = info.ge
        if info.le is not None:
            kwargs["max_value"] = info.le
        fields[name] = field_class(required=model_field.required is True and not model_field.allow_none, **kwargs)
    return fields


class SchemaActionForm(BasePostProcessingActionForm):
    """Action form whose fields are generated from ``schema``, minus the scope fields in ``exclude_fields``."""

    schema: type[pydantic.BaseModel]
    exclude_fields: Collection[str] = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.update(schema_form_fields(self.schema, self.exclude_fields))
