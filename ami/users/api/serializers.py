from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework import serializers

from ami.main.api.serializers import DefaultSerializer
from ami.users.models import User as UserType

User = get_user_model()


class UserListSerializer(DefaultSerializer[UserType]):
    class Meta:
        model = User
        fields = ["id", "name", "details", "image"]

        extra_kwargs = {
            "details": {"view_name": "api:user-detail", "lookup_field": "pk", "lookup_url_kwarg": "id"},
        }


class UserSerializer(UserListSerializer):
    identifications = serializers.SerializerMethodField()

    class Meta(UserListSerializer.Meta):
        fields = UserListSerializer.Meta.fields + [
            "identifications",
        ]

    def get_identifications(self, obj):
        # return obj.identifications.all()
        return []


class CurrentUserSerializer(UserSerializer):
    """
    Make additional private fields available for the current user.

    This is used for the `/users/me/` endpoint.
    `email` is read-only because it needs be changed via the `/users/set_email/` endpoint.
    `password` must be changed via the `/users/reset_password/` endpoint.
    """

    email = serializers.EmailField(read_only=True)

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ["email"]


class GroupSerializer(DefaultSerializer):
    class Meta:
        model = Group
        fields = ["id", "details", "name"]
