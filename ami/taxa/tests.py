from django.test import TestCase

from ami.main.models import Occurrence, Taxon, group_images_into_events
from ami.taxa.models import TaxonObserved, update_taxa_observed_for_project
from tests.fixtures.main import create_captures, create_occurrences, create_taxa, setup_test_project


class TaxonObservedTestCase(TestCase):
    """
    Taxon are the underlying Species / Genus / Family taxon record available in the system
    TaxonObserved are the actual sightings of these taxa in a Project / Deployment
    """

    def setUp(self):
        self.project_one, self.deployment_one = setup_test_project(reuse=True)
        self.project_two, self.deployment_two = setup_test_project(reuse=False)
        create_captures(deployment=self.deployment_one)
        create_captures(deployment=self.deployment_two)
        group_images_into_events(deployment=self.deployment_one)
        group_images_into_events(deployment=self.deployment_two)
        create_taxa(project=self.project_one)
        create_taxa(project=self.project_two)
        create_occurrences(deployment=self.deployment_one, num=5)
        create_occurrences(deployment=self.deployment_two, num=5)
        return super().setUp()

    def test_taxa_observed_existence(self):
        """
        Test that TaxonObserved are zero initially and are updated after calling update_taxa_observed_for_project

        Once we implement a signal to update TaxonObserved records when Occurrence records change, this test will fail.
        """
        self.assertEqual(TaxonObserved.objects.count(), 0)
        update_taxa_observed_for_project(self.project_one)
        self.assertGreater(TaxonObserved.objects.count(), 0)

    def test_taxa_observed_num(self):
        """
        Test that TaxonObserved counts are updated correctly
        """
        update_taxa_observed_for_project(self.project_one)
        occurred_count = Taxon.objects.filter(occurrences__project=self.project_one).distinct().count()
        observed_count = TaxonObserved.objects.filter(project=self.project_one).count()

        # Assert they are greater than zero
        self.assertGreater(occurred_count, 0)

        # Assert they are equal
        self.assertEqual(occurred_count, observed_count)

    def test_taxa_observed_moved(self):
        """
        Move an Occurrence from one project to another and check if the TaxonObserved counts are updated correctly
        """

        # Update TaxonObserved for both projects
        update_taxa_observed_for_project(self.project_one)
        update_taxa_observed_for_project(self.project_two)

        # Create an Occurrence in project_one
        occurrences = Occurrence.objects.filter(project=self.project_one)

        taxa_occurred_in_project_one = (
            Occurrence.objects.filter(project=self.project_one).values_list("determination", flat=True).distinct()
        )
        taxa_occurred_in_project_two = (
            Occurrence.objects.filter(project=self.project_two).values_list("determination", flat=True).distinct()
        )
        for occurrence in occurrences:
            # Move all occurrences to project_two
            occurrence.project = self.project_two  # type: ignore
            occurrence.save()

        # Update TaxonObserved for both projects
        update_taxa_observed_for_project(self.project_one)
        update_taxa_observed_for_project(self.project_two)

        taxa_observed_in_project_one = TaxonObserved.objects.filter(project=self.project_one)
        taxa_observed_in_project_two = TaxonObserved.objects.filter(project=self.project_two)

        # Assert that the counts are updated correctly
        self.assertEqual(taxa_observed_in_project_one.count(), 0)
        self.assertEqual(
            taxa_observed_in_project_two.count(),
            (taxa_occurred_in_project_two.count() + taxa_occurred_in_project_one.count()),
        )
