from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["name", "url"]

        extra_kwargs = {
            "url": {"view_name": "api:user-detail", "lookup_field": "pk"},
        }


class LoginSerializer(serializers.Serializer):
    """
    This serializer defines two fields for authentication:
      * email
      * password.
    It will try to authenticate the user with when validated.
    """

    email = serializers.CharField(label="Email", write_only=True)
    password = serializers.CharField(
        label="Password",
        # This will be used when the DRF browsable API is enabled
        style={"input_type": "password"},
        trim_whitespace=False,
        write_only=True,
    )

    def validate(self, attrs):
        # Take email and password from request
        email = attrs.get("email")
        password = attrs.get("password")

        if email and password:
            # Try to authenticate the user using Django auth framework.
            user = authenticate(request=self.context.get("request"), email=email, password=password)
            if not user:
                # If we don't have a regular user, raise a ValidationError
                msg = "Access denied: wrong email or password."
                raise serializers.ValidationError(msg, code="authorization")
        else:
            msg = 'Both "email" and "password" are required.'
            raise serializers.ValidationError(msg, code="authorization")
        # We have a valid user, put it in the serializer's validated_data.
        # It will be used in the view.
        attrs["user"] = user
        return attrs
