from django.urls import resolve, reverse

from ami.users.models import User


def test_user_detail(user: User):
    assert reverse("api:user-detail", kwargs={"id": user.pk}) == f"/api/v2/users/{user.pk}/"
    assert resolve(f"/api/v2/users/{user.pk}/").view_name == "api:user-detail"


def test_user_list():
    assert reverse("api:user-list") == "/api/v2/users/"
    assert resolve("/api/v2/users/").view_name == "api:user-list"


def test_user_me():
    assert reverse("api:user-me") == "/api/v2/users/me/"
    assert resolve("/api/v2/users/me/").view_name == "api:user-me"
