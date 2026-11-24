"""
Tests for the tags API.

The list must be scoped to a project: without one it returns every tag on the
platform, and each tag's taxa are serialized too.
"""

from cachalot.api import cachalot_disabled
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework import status
from rest_framework.test import APITestCase

from ami.main.models_future.taxonomy import Tag, Taxon
from ami.tests.fixtures.main import setup_test_project
from ami.users.models import User


class TestTagListAPI(APITestCase):
    def setUp(self) -> None:
        self.project, _ = setup_test_project()
        self.other_project, _ = setup_test_project(reuse=False)
        taxa = [Taxon.objects.create(name=f"Tag Test Taxon {i}") for i in range(3)]
        for i in range(3):
            tag = Tag.objects.create(name=f"Project tag {i}", project=self.project)
            tag.taxa.set(taxa)
        Tag.objects.create(name="Global tag")
        Tag.objects.create(name="Other project tag", project=self.other_project)
        self.user = User.objects.create_user(email="tags@insectai.org", is_staff=True, is_superuser=True)
        self.client.force_authenticate(user=self.user)

    def test_list_without_project_is_rejected(self):
        response = self.client.get("/api/v2/tags/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_returns_project_and_global_tags_with_their_taxa(self):
        response = self.client.get(f"/api/v2/tags/?project_id={self.project.pk}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = {tag["name"] for tag in response.data["results"]}
        self.assertEqual(names, {"Project tag 0", "Project tag 1", "Project tag 2", "Global tag"})
        tagged = next(tag for tag in response.data["results"] if tag["name"] == "Project tag 0")
        self.assertEqual(len(tagged["taxa"]), 3)

    def test_taxa_and_projects_are_not_queried_per_tag(self):
        """Taxa and projects load in a fixed number of queries, however many tags there are.

        Per-tag permission lookups still grow with the page; see #1430.
        """
        url = f"/api/v2/tags/?project_id={self.project.pk}"

        def related_queries() -> tuple[int, int]:
            with cachalot_disabled(), CaptureQueriesContext(connection) as ctx:
                self.client.get(url)
            sqls = [q["sql"] for q in ctx.captured_queries]
            taxa = sum('FROM "main_taxon"' in sql for sql in sqls)
            projects = sum(sql.startswith('SELECT "main_project"') for sql in sqls)
            return taxa, projects

        before = related_queries()
        for i in range(3, 8):
            Tag.objects.create(name=f"Project tag {i}", project=self.project).taxa.set(Taxon.objects.all()[:2])
        self.assertEqual(related_queries(), before)
        self.assertEqual(before[0], 1)
