import logging
import typing
import urllib.parse

from django.db import models
from rest_framework import exceptions as api_exceptions
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.reverse import reverse

from .permissions import add_object_level_permissions

logger = logging.getLogger(__name__)


def reverse_with_params(viewname: str, args=None, kwargs=None, request=None, params: dict = {}, **extra) -> str:
    query_string = urllib.parse.urlencode(params)
    base_url = reverse(viewname, request=request, args=args, kwargs=kwargs, **extra)
    url = urllib.parse.urlunsplit(("", "", base_url, query_string, ""))
    return url


def add_format_to_url(url: str, format: typing.Literal["json", "html", "csv"]) -> str:
    """
    Add a format suffix to a URL.

    This is a workaround for the DRF `format_suffix_patterns` decorator not working
    with the `reverse` function.
    """
    url_parts = urllib.parse.urlsplit(url)
    url_parts = url_parts._replace(path=f"{url_parts.path.rstrip('/')}.{format}")
    return urllib.parse.urlunsplit(url_parts)


def get_current_user(request: Request | None):
    if request:
        return request.user
    else:
        return None


class DefaultSerializer(serializers.HyperlinkedModelSerializer):
    url_field_name = "details"
    id = serializers.IntegerField(read_only=True)

    def get_permissions(self, instance, instance_data):
        request: Request = self.context["request"]
        user = request.user

        return add_object_level_permissions(
            user=user,
            instance=instance,
            response_data=instance_data,
        )

    def to_representation(self, instance):
        instance_data = super().to_representation(instance)
        instance_data = self.get_permissions(instance=instance, instance_data=instance_data)
        return instance_data

    def get_instance_for_permission_check(self):
        """
        Returns an unsaved model instance built from validated_data,
        excluding ManyToMany fields and any non-model fields (like 'project').
        Safe to use for permission checking before saving.
        """
        validated_data = getattr(self, "validated_data", {})
        if not validated_data:
            raise ValueError("Serializer must be validated before calling this method.")

        model_cls = self.Meta.model
        model_field_names = {f.name for f in model_cls._meta.get_fields()}
        m2m_fields = {f.name for f in model_cls._meta.many_to_many}

        safe_data = {}
        for key, value in validated_data.items():
            # skip many-to-many and non-model fields
            if key in m2m_fields:
                continue
            if key not in model_field_names:
                continue
            safe_data[key] = value

        return model_cls(**safe_data)


class MinimalNestedModelSerializer(DefaultSerializer):
    """
    A nested serializer that only includes the id and the hyperlinked identity field.

    This way we do not need an extra join or query to get the details of the related model,
    but the client can still access the data as a nested object rather than just an ID.

    For example, an Event with a related Project that is serialized with the `MinimalNestedModelSerializer`:
    {
        "id": 1,
        "details": "http://example.org/api/events/1/",
        "name": "Minimal Birthday",
        "project": {
            "id": 1,
            "details": "http://example.org/api/projects/1/"
        }
    }

    IMPORTANT: this class is meant to work with the _id of the related model, not the actual model instance.
    make sure to set the source field to the _id of the related model, not the model instance.
    """

    class Meta:
        fields = ["id", "details"]

    def to_representation(self, instance):
        # If the instance is just an ID, create a dummy object
        if isinstance(instance, self.Meta.model):  # type: ignore
            raise ValueError(
                "The instance should be an ID, not an instance of the related model. "
                "Specify the _id field with the `source` parameter."
            )
        else:
            dummy_instance = self.Meta.model(pk=instance)  # type: ignore
            return super().to_representation(dummy_instance)
        return super().to_representation(instance)

    @classmethod
    def create_for_model(cls, model: type[models.Model]) -> type["MinimalNestedModelSerializer"]:
        class_name = f"MinimalNestedModelSerializer_{model.__name__}"
        return type(class_name, (cls,), {"Meta": type("Meta", (), {"model": model, "fields": cls.Meta.fields})})


T = typing.TypeVar("T")


class SingleParamSerializer(serializers.Serializer, typing.Generic[T]):
    """
    A serializer for validating individual GET parameters in DRF views/filters.

    This class provides a reusable way to validate single parameters using DRF's
    serializer fields, while maintaining type hints and clean error handling.

    Example:
        >>> field = serializers.IntegerField(required=True, min_value=1)
        >>> value = SingleParamSerializer[int].validate_param('page', field, request.query_params)
    """

    @classmethod
    def clean(
        cls,
        param_name: str,
        field: serializers.Field,
        data: dict[str, typing.Any],
    ) -> T:
        """
        Validate a single parameter using the provided field configuration.

        Args:
            param_name: The name of the parameter to validate
            field: The DRF Field instance to use for validation
            data: Dictionary containing the parameter value (typically request.query_params)

        Returns:
            The validated and transformed parameter value

        Raises:
            ValidationError: If the parameter value is invalid according to the field rules
        """
        instance = cls(param_name, field, data=data)
        if instance.is_valid(raise_exception=True):
            return typing.cast(T, instance.validated_data.get(param_name))

        # This shouldn't be reached due to raise_exception=True, but keeps type checker happy
        raise api_exceptions.ValidationError(f"Invalid value for parameter: {param_name}")

    def __init__(
        self,
        param_name: str,
        field: serializers.Field,
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> None:
        """
        Initialize the serializer with a single field for the given parameter.

        Args:
            param_name: The name of the parameter to validate
            field: The DRF Field instance to use for validation
            *args: Additional positional arguments passed to parent
            **kwargs: Additional keyword arguments passed to parent
        """
        super().__init__(*args, **kwargs)
        self.fields[param_name] = field


class FilterParamsSerializer(serializers.Serializer):
    """
    Serializer for validating query parameters in DRF views.
    Typically in filters for list views.

    A normal serializer with one helpful method to:
    1) run .is_valid()
    2) raise any validation exceptions
    3) then return the cleaned data.
    """

    def clean(self) -> dict[str, typing.Any]:
        if self.is_valid(raise_exception=True):
            return self.validated_data
        raise api_exceptions.ValidationError("Invalid filter parameters")
