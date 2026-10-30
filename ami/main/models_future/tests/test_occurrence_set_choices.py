from django.test import TestCase
from rest_framework.test import APIClient

from ami.main.models import OccurrenceSet, Project
from ami.users.models import User

URL = "/api/v2/occurrences/sets/choices/"


class TestOccurrenceSetChoices(TestCase):
    """The picker on the retraining form lists one project's sets, and nothing else."""

    def setUp(self):
        self.user = User.objects.create_user(email="choices@insectai.org", is_superuser=True)
        self.project = Project.objects.create(name="Mine", owner=self.user)
        self.other = Project.objects.create(name="Theirs", owner=self.user)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_lists_only_the_projects_sets(self):
        mine = OccurrenceSet.objects.create(name="Spring review", project=self.project)
        OccurrenceSet.objects.create(name="Someone else's", project=self.other)

        response = self.client.get(URL, {"project_id": self.project.pk})

        self.assertEqual(response.status_code, 200)
        self.assertEqual([(r["id"], r["name"]) for r in response.json()["results"]], [(mine.pk, "Spring review")])

    def test_a_project_is_required(self):
        self.assertEqual(self.client.get(URL).status_code, 400)
