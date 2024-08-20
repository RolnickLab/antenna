import typing
import urllib.parse

from django.db import models
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.reverse import reverse

from .permissions import add_object_level_permissions


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

    def get_permissions(self, instance_data):
        request = self.context.get("request")
        user = request.user if request else None
        return add_object_level_permissions(user, instance_data)

    def to_representation(self, instance):
        instance_data = super().to_representation(instance)
        instance_data = self.get_permissions(instance_data)
        return instance_data


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

    """

    class Meta:
        fields = ["id", "details"]

    @classmethod
    def create_for_model(cls, model: type[models.Model]) -> type["MinimalNestedModelSerializer"]:
        return type(
            f"MinimalNestedModelSerializer_{model.__name__}",
            (cls,),
            {"Meta": type("Meta", (), {"model": model, "fields": cls.Meta.fields})},
        )
