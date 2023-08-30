from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    identifications = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["name", "url", "identifications"]

        extra_kwargs = {
            "url": {"view_name": "api:user-detail", "lookup_field": "pk"},
        }

    def get_identifications(self, obj):
        # return obj.identifications.all()
        return []
