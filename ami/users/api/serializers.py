from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework import serializers

from ami.main.api.serializers import DefaultSerializer, UserNestedSerializer
from ami.main.models import UserProjectMembership

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
    name = serializers.CharField()


class UserProjectMembershipSerializer(DefaultSerializer):
    email = serializers.EmailField(write_only=True)
    role_id = serializers.CharField(write_only=True)

    user = UserNestedSerializer(read_only=True)

    class Meta:
        model = UserProjectMembership
        fields = [
            "id",
            "email",
            "role_id",
            "user",
            "project",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["project", "user", "created_at", "updated_at"]

    def validate_email(self, value):
        """Validate user email and store actual user object."""
        try:
            user = User.objects.get(email=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User does not exist in the system.")

        # Save for use in .validate()
        self._validated_user = user
        return value

    def validate_role_id(self, value):
        from ami.users.roles import Role

        role_map = {cls.__name__: cls for cls in Role.__subclasses__()}
        if value not in role_map:
            raise serializers.ValidationError(f"Invalid role_id. Must be one of: {list(role_map.keys())}")

        self._validated_role_cls = role_map[value]
        return value

    def validate(self, attrs):
        project = self.context["project"]
        user = getattr(self, "_validated_user", None)
        role_cls = getattr(self, "_validated_role_cls", None)

        if not user or not role_cls:
            return attrs

        # Check if membership already exists
        if self.instance is None:  # creating
            exists = UserProjectMembership.objects.filter(project=project, user=user).exists()
            if exists:
                raise serializers.ValidationError("User is already a member of this project.")

        attrs.pop("email", None)
        attrs.pop("role_id", None)
        if user:
            attrs["user"] = user
        return attrs


class UserProjectMembershipListSerializer(DefaultSerializer):
    user = UserNestedSerializer(read_only=True)
    role = serializers.SerializerMethodField()
    role_display_name = serializers.SerializerMethodField()

    class Meta:
        model = UserProjectMembership
        fields = [
            "id",
            "user",
            "role",
            "role_display_name",
            "created_at",
            "updated_at",
            "details",
        ]
        extra_kwargs = {
            "details": {"view_name": "api:project-members-detail"},
        }

    def _get_primary_role_class(self, obj):
        """Return the role class with the most permissions."""
        from ami.users.roles import Role

        roles = Role.get_user_roles(obj.project, obj.user)
        if not roles:
            return None
        return max(roles, key=lambda r: len(r.permissions))

    def get_role(self, obj):
        role_cls = self._get_primary_role_class(obj)
        return role_cls.__name__ if role_cls else None

    def get_role_display_name(self, obj):
        role_cls = self._get_primary_role_class(obj)
        return role_cls.name if role_cls else None
