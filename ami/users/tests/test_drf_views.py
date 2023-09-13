import pytest
from djoser.views import UserViewSet
from rest_framework.test import APIRequestFactory

from ami.users.models import User


# Djoser has its own tests for the UserViewSet, so we only need to test our own code.
class TestUserViewSet:
    @pytest.fixture
    def api_rf(self) -> APIRequestFactory:
        return APIRequestFactory()

    def test_get_queryset(self, user: User, api_rf: APIRequestFactory):
        view = UserViewSet()
        view.action = "list"
        request = api_rf.get("/fake-url/")
        request.user = user

        view.request = request

        assert user in view.get_queryset()
