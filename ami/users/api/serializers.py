from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework import serializers

from ami.main.api.serializers import DefaultSerializer

User = get_user_model()


class UserSerializer(DefaultSerializer):
    identifications = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "name",
            "details",
            "image",
            "identifications",
        ]

        extra_kwargs = {
            "details": {"view_name": "api:user-detail", "lookup_field": "pk", "lookup_url_kwarg": "id"},
        }

    def get_identifications(self, obj):
        # return obj.identifications.all()
        return []


class GroupSerializer(DefaultSerializer):
    class Meta:
        model = Group
        fields = ["id", "details", "name"]
