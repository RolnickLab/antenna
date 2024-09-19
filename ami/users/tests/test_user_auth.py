from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError
from django.urls import reverse
from rest_framework.test import APIRequestFactory, APITestCase

User = get_user_model()


class UserAuthTestCase(APITestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        # self.client.force_authenticate(user=self.user)
        self.user = User.objects.create_user(email="TEST@example.com", password="testpassword")  # type: ignore

    def test_case_insensitive_login(self):
        login_url = reverse("api:login")  # Assuming you're using django-allauth

        # Test lowercase email
        response = self.client.post(login_url, {"email": "test@example.com", "password": "testpassword"})
        self.assertEqual(response.status_code, 200)

        self.client.logout()

        # Test mixed case email
        response = self.client.post(login_url, {"email": "TeSt@ExAmPlE.cOm", "password": "testpassword"})
        self.assertEqual(response.status_code, 200)

        self.client.logout()

    def test_email_stored_lowercase(self):
        user = User.objects.create_user(email="UPPER@EXAMPLE.COM", password="testpassword")  # type: ignore
        self.assertEqual(user.email, "upper@example.com")

        user.email = "MiXeD@ExAmPlE.cOm"
        user.save()
        user.refresh_from_db()
        self.assertEqual(user.email, "mixed@example.com")

    def test_change_user_email(self):
        user = User.objects.create_user(email="testEXAMPL@example.com", password="testpassword")  # type: ignore
        user.email = "TESTexample@example.com"
        user.save()
        user.refresh_from_db()
        self.assertEqual(user.email, "testexample@example.com")

    def test_uniqueness(self):
        with self.assertRaises(IntegrityError):
            User.objects.create_user(email="testemail@example.com")  # type: ignore
            User.objects.create_user(email="testEMAIL@example.com")  # type: ignore
            User.objects.create_user(email="TESTemail@example.com")  # type: ignore
