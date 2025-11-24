from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework import serializers

from ami.main.api.serializers import DefaultSerializer

User = get_user_model()


class UserListSerializer(DefaultSerializer):
    class Meta:
        model = User
        fields = ["id", "name", "details", "image", "email"]

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


# Roles management api serializers
class ProjectRoleSerializer(serializers.Serializer):
    id = serializers.CharField(source="role")
    display_name = serializers.CharField()


class ProjectMemberSerializer(serializers.Serializer):
    user = UserListSerializer(read_only=True)
    role = serializers.CharField(read_only=True)

    user_id = serializers.IntegerField(write_only=True, required=False)
    role_id = serializers.CharField(write_only=True, required=True)

    def validate_user_id(self, value):
        try:
            user = User.objects.get(pk=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found.")
        # store user object for use in .validate()
        self._validated_user = user
        return value

    def validate_role_id(self, value):
        from ami.users.roles import Role

        role_map = {r.__name__: r for r in Role.__subclasses__()}

        if value not in role_map:
            raise serializers.ValidationError(f"Invalid role_id. Must be one of: {list(role_map.keys())}")

        # store role class for use in .validate()
        self._validated_role = role_map[value]
        return value

    def validate(self, data):
        """
        Attach validated user + role onto validated_data
        so the viewset can use serializer.validated_data["user"]
        and serializer.validated_data["role"].
        """
        if hasattr(self, "_validated_user"):
            data["user"] = self._validated_user

        if hasattr(self, "_validated_role"):
            data["role"] = self._validated_role

        return data
