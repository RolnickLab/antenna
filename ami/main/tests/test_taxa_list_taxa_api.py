"""
Tests for TaxaList taxa management API endpoints (without through model).
"""

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from ami.main.models import Project, TaxaList, Taxon
from ami.users.models import User


class TaxaListTaxonAPITestCase(TestCase):
    """Test TaxaList taxa management operations via API."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(email="test@example.com", password="testpass")
        self.project = Project.objects.create(name="Test Project", owner=self.user)
        self.taxa_list = TaxaList.objects.create(name="Test Taxa List", description="Test description")
        self.taxa_list.projects.add(self.project)
        self.taxon1 = Taxon.objects.create(name="Taxon 1", rank="species")
        self.taxon2 = Taxon.objects.create(name="Taxon 2", rank="species")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.base_url = f"/api/v2/taxa/lists/{self.taxa_list.pk}/taxa/?project_id={self.project.pk}"

    def test_add_taxon_returns_201(self):
        """Test adding taxon to taxa list returns 201."""
        response = self.client.post(self.base_url, {"taxon_id": self.taxon1.pk})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(self.taxa_list.taxa.filter(pk=self.taxon1.pk).exists())
        self.assertEqual(response.data["id"], self.taxon1.pk)

    def test_add_duplicate_returns_400(self):
        """Test adding duplicate taxon returns 400."""
        self.taxa_list.taxa.add(self.taxon1)
        response = self.client.post(self.base_url, {"taxon_id": self.taxon1.pk})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already in this taxa list", str(response.data).lower())

    def test_add_nonexistent_taxon_returns_400(self):
        """Test adding non-existent taxon returns 400."""
        response = self.client.post(self.base_url, {"taxon_id": 999999})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_taxa_in_list(self):
        """Test listing taxa in a taxa list."""
        self.taxa_list.taxa.add(self.taxon1, self.taxon2)

        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        taxon_ids = [item["id"] for item in response.data["results"]]
        self.assertIn(self.taxon1.pk, taxon_ids)
        self.assertIn(self.taxon2.pk, taxon_ids)

    def test_delete_by_taxon_id(self):
        """Test deleting by taxon ID returns 204."""
        self.taxa_list.taxa.add(self.taxon1)
        url = f"/api/v2/taxa/lists/{self.taxa_list.pk}/taxa/{self.taxon1.pk}/?project_id={self.project.pk}"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(self.taxa_list.taxa.filter(pk=self.taxon1.pk).exists())

    def test_delete_nonexistent_returns_404(self):
        """Test deleting non-existent taxon returns 404."""
        url = f"/api/v2/taxa/lists/{self.taxa_list.pk}/taxa/{self.taxon1.pk}/?project_id={self.project.pk}"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_empty_taxa_list(self):
        """Test listing taxa in an empty taxa list."""
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(response.data["results"], [])

    def test_m2m_relationship_works(self):
        """Test that M2M relationship still works correctly."""
        self.taxa_list.taxa.add(self.taxon1)
        # Should be accessible via M2M relationship
        self.assertEqual(self.taxa_list.taxa.count(), 1)
        self.assertIn(self.taxon1, self.taxa_list.taxa.all())
        # Test reverse relationship
        self.assertIn(self.taxa_list, self.taxon1.lists.all())

    def test_add_multiple_taxa(self):
        """Test adding multiple taxa to the same list."""
        response1 = self.client.post(self.base_url, {"taxon_id": self.taxon1.pk})
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)

        response2 = self.client.post(self.base_url, {"taxon_id": self.taxon2.pk})
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)

        self.assertEqual(self.taxa_list.taxa.count(), 2)

    def test_remove_one_taxon_keeps_others(self):
        """Test that removing one taxon doesn't affect others."""
        self.taxa_list.taxa.add(self.taxon1, self.taxon2)

        url = f"/api/v2/taxa/lists/{self.taxa_list.pk}/taxa/{self.taxon1.pk}/?project_id={self.project.pk}"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # taxon1 should be removed
        self.assertFalse(self.taxa_list.taxa.filter(pk=self.taxon1.pk).exists())
        # taxon2 should still be there
        self.assertTrue(self.taxa_list.taxa.filter(pk=self.taxon2.pk).exists())
        self.assertEqual(self.taxa_list.taxa.count(), 1)


class TaxaListTaxonValidationTestCase(TestCase):
    """Test validation and error cases."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(email="test@example.com", password="testpass")
        self.project = Project.objects.create(name="Test Project", owner=self.user)
        self.taxa_list = TaxaList.objects.create(name="Test Taxa List")
        self.taxa_list.projects.add(self.project)
        self.taxon = Taxon.objects.create(name="Test Taxon", rank="species")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.base_url = f"/api/v2/taxa/lists/{self.taxa_list.pk}/taxa/?project_id={self.project.pk}"

    def test_add_without_taxon_id_returns_400(self):
        """Test adding without taxon_id returns 400."""
        response = self.client.post(self.base_url, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_add_with_invalid_taxon_id_returns_400(self):
        """Test adding with invalid taxon_id returns 400."""
        response = self.client.post(self.base_url, {"taxon_id": "invalid"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_nonexistent_taxa_list_returns_404(self):
        """Test accessing non-existent taxa list returns 404."""
        url = f"/api/v2/taxa/lists/999999/taxa/?project_id={self.project.pk}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
