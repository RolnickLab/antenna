from unittest import mock

from django.conf import settings
from django.core.cache.backends.locmem import LocMemCache
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle
from rest_framework.views import APIView

PROXY_ADDR = "10.0.0.1"


@override_settings(REST_FRAMEWORK={**settings.REST_FRAMEWORK, "NUM_PROXIES": 1})
class TestAnonymousRateLimit(TestCase):
    """
    Anonymous API clients behind the reverse proxy are limited per client IP address.

    Production settings enable the limit (config/settings/production.py); here it is
    switched on for one test class, with a small rate and a private cache.
    """

    def setUp(self):
        patches = [
            mock.patch.object(APIView, "throttle_classes", [AnonRateThrottle]),
            mock.patch.object(AnonRateThrottle, "THROTTLE_RATES", {"anon": "2/minute"}),
            mock.patch.object(SimpleRateThrottle, "cache", LocMemCache("throttle-tests", {})),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.client = APIClient(REMOTE_ADDR=PROXY_ADDR)

    def get_projects(self, client_ip: str):
        return self.client.get("/api/v2/projects/", headers={"x-forwarded-for": client_ip})

    def test_client_over_the_limit_gets_429(self):
        self.assertEqual(self.get_projects("203.0.113.5").status_code, status.HTTP_200_OK)
        self.assertEqual(self.get_projects("203.0.113.5").status_code, status.HTTP_200_OK)
        self.assertEqual(self.get_projects("203.0.113.5").status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_clients_behind_the_same_proxy_are_counted_apart(self):
        for _ in range(2):
            self.get_projects("203.0.113.5")
        self.assertEqual(self.get_projects("198.51.100.7").status_code, status.HTTP_200_OK)

    def test_forged_forwarded_addresses_do_not_reset_the_count(self):
        # The proxy appends the real client address; anything before it is client-supplied.
        statuses = [self.get_projects(f"192.0.2.{n}, 203.0.113.5").status_code for n in range(3)]
        self.assertEqual(statuses[-1], status.HTTP_429_TOO_MANY_REQUESTS)
