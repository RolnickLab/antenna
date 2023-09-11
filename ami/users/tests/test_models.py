from ami.users.models import User


def test_user_get_absolute_url(user: User):
    assert user.get_absolute_url() == f"/api/v2/users/{user.pk}/"
