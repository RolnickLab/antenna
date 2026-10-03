from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core import mail
from django.db.utils import IntegrityError
from django.test import override_settings
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


class PasswordResetEmailTestCase(APITestCase):
    """The reset email must name the product and link to the frontend, not to the API host."""

    def setUp(self):
        self.user = User.objects.create_user(email="reset@example.com", password="testpassword")  # type: ignore
        self.url = reverse("api:user-reset-password")

    def test_subject_uses_site_name_setting(self):
        response = self.client.post(self.url, {"email": "reset@example.com"})
        self.assertEqual(response.status_code, 204)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Password reset on Antenna")

    @override_settings(DOMAIN="antenna.example.org")
    def test_link_uses_domain_setting_instead_of_site_record(self):
        Site.objects.update_or_create(id=settings.SITE_ID, defaults={"domain": "api.example.org"})
        self.client.post(self.url, {"email": "reset@example.com"})
        self.assertIn("//antenna.example.org/auth/reset-password-confirm?uid=", mail.outbox[0].body)
        self.assertNotIn("api.example.org", mail.outbox[0].body)
