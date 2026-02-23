from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework import serializers

from ami.main.api.serializers import DefaultSerializer
from ami.main.models import UserProjectMembership

User = get_user_model()


class UserListSerializer(DefaultSerializer):
    """General user serializer - excludes email for privacy."""

    class Meta:
        model = User
        fields = [
            "id",
            "name",
            "details",
            "image",
        ]

        extra_kwargs = {
            "details": {"view_name": "api:user-detail", "lookup_field": "pk", "lookup_url_kwarg": "id"},
        }


class MemberUserSerializer(UserListSerializer):
    """User serializer for membership context - includes email for management purposes."""

    class Meta(UserListSerializer.Meta):
        fields = UserListSerializer.Meta.fields + ["email"]


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
    """
    Serializer for project roles.

    Note:
        Roles are NOT database-backed models. They are defined as Python classes
        (subclasses of the base `Role` class) and represent permission sets rather
        than persisted records.

        The list of roles serialized by this serializer is obtained by inspecting
        `Role.__subclasses__()` (via `Role.get_supported_roles()` in the view),
        and each `obj` passed to this serializer is a role class, not a model
        instance.

        Because roles are class-based:
        - `id` corresponds to the role class name
        - `name` and `description` are class attributes
    """

    id = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()

    def get_id(self, obj):
        """Get role class name as ID."""
        return obj.__name__

    def get_name(self, obj):
        """Get role display name."""
        return obj.display_name

    def get_description(self, obj):
        """Get role description."""
        return obj.description


class UserProjectMembershipSerializer(DefaultSerializer):
    email = serializers.EmailField(write_only=True)
    role_id = serializers.CharField(write_only=True)

    user = MemberUserSerializer(read_only=True)
    role = serializers.SerializerMethodField(read_only=True)
    role_display_name = serializers.SerializerMethodField(read_only=True)
    role_description = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = UserProjectMembership
        fields = [
            "id",
            "email",
            "role_id",
            "user",
            "project",
            "role",
            "role_display_name",
            "role_description",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "project",
            "user",
            "created_at",
            "updated_at",
            "role",
            "role_display_name",
            "role_description",
        ]

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

    def get_role(self, obj):
        from ami.users.roles import Role

        role_cls = Role.get_primary_role(obj.project, obj.user)
        return role_cls.__name__ if role_cls else None

    def get_role_display_name(self, obj):
        from ami.users.roles import Role

        role_cls = Role.get_primary_role(obj.project, obj.user)
        return role_cls.display_name if role_cls else None

    def get_role_description(self, obj):
        from ami.users.roles import Role

        role_cls = Role.get_primary_role(obj.project, obj.user)
        return role_cls.description if role_cls else None

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
        else:  # updating
            # Check if another membership with same project+user exists
            # Only check if user is being changed
            if user != self.instance.user:
                exists = UserProjectMembership.objects.filter(project=project, user=user).exists()
                if exists:
                    raise serializers.ValidationError("User is already a member of this project.")

        attrs.pop("email", None)
        attrs.pop("role_id", None)
        if user:
            attrs["user"] = user
        attrs["project"] = project
        return attrs


class UserProjectMembershipListSerializer(UserProjectMembershipSerializer):
    user = MemberUserSerializer(read_only=True)
    role = serializers.SerializerMethodField()
    role_display_name = serializers.SerializerMethodField()
    role_description = serializers.SerializerMethodField()

    class Meta:
        model = UserProjectMembership
        fields = [
            "id",
            "user",
            "role",
            "role_display_name",
            "role_description",
            "created_at",
            "updated_at",
        ]
