from django.test import TestCase

from ami.main.models import Occurrence, Project, Taxon, group_images_into_events
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


class TestTaxonObservedViews(TestCase):
    def setUp(self) -> None:
        project_one, deployment_one = setup_test_project(reuse=False)
        project_two, deployment_two = setup_test_project(reuse=False)
        create_taxa(project=project_one)
        create_taxa(project=project_two)
        # Show project & deployment IDs
        print(f"Project One: {project_one}")
        print(f"Project Two: {project_two}")
        print(f"Deployment One: {deployment_one.pk}")
        print(f"Deployment Two: {deployment_two.pk}")
        create_captures(deployment=deployment_one)
        create_captures(deployment=deployment_two)
        group_images_into_events(deployment=deployment_one)
        group_images_into_events(deployment=deployment_two)
        create_occurrences(deployment=deployment_one, num=5)
        create_occurrences(deployment=deployment_two, num=5)
        update_taxa_observed_for_project(project_one)
        update_taxa_observed_for_project(project_two)
        self.project_one = project_one
        self.project_two = project_two
        return super().setUp()

    def test_occurrences_for_project(self):
        # Test that occurrences are specific to each project
        for project in [self.project_one, self.project_two]:
            response = self.client.get(f"/api/v2/occurrences/?project={project.pk}")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["count"], Occurrence.objects.filter(project=project).count())

    def _test_taxa_for_project(self, project: Project):
        """
        Ensure the annotation counts are specific to each project, not global counts
        of occurrences and detections.
        """
        response = self.client.get(f"/api/v2/taxa/observed/?project={project.pk}")
        self.assertEqual(response.status_code, 200)
        project_occurred_taxa = TaxonObserved.objects.filter(project=project)
        # project_any_taxa = Taxon.objects.filter(projects=project)
        self.assertGreater(project_occurred_taxa.count(), 0)
        self.assertEqual(response.json()["count"], project_occurred_taxa.count())

        # Check counts for each taxon
        results = response.json()["results"]
        for taxon_result in results:
            taxon: TaxonObserved = TaxonObserved.objects.get(pk=taxon_result["id"])
            project_occurrences = taxon.occurrences.filter(project=project).count()
            # project_detections = taxon.detections.filter(project=project).count()
            self.assertEqual(taxon_result["occurrences_count"], project_occurrences)

    def test_taxa_for_project(self):
        for project in [self.project_one, self.project_two]:
            self._test_taxa_for_project(project)

    def test_recursive_occurrence_counts_single(self):
        update_taxa_observed_for_project(self.project_one)
        # First, assert that we have taxa with parents and occurrences
        taxa_seen = TaxonObserved.objects.exclude(
            taxon__parent=None, project=self.project_one
        )  # .filter(occurrences__isnull=False)
        self.assertGreater(taxa_seen.count(), 0)
        for taxon_seen in taxa_seen:
            occurrence_count_direct = taxon_seen.occurrences.count()
            occurrence_count_total = taxon_seen.get_occurrences_count_recursive()
            self.assertGreaterEqual(occurrence_count_total, occurrence_count_direct)

            # Manually add up the occurrences for each taxon and its children, tarecursively:
            def _count_occurrences_recursive(taxon_seen: TaxonObserved) -> int:
                count = taxon_seen.occurrences_count
                for child in TaxonObserved.objects.filter(taxon__parent=taxon_seen.taxon, project=taxon_seen.project):
                    count += _count_occurrences_recursive(child)
                return count

            manual_count = _count_occurrences_recursive(taxon_seen)
            self.assertEqual(occurrence_count_total, manual_count)

        # The top level test taxa should have all occurrences
        top_level_taxa = Taxon.objects.root()
        top_level_taxon_seen, _created = TaxonObserved.objects.get_or_create(
            taxon=top_level_taxa, project=self.project_one
        )
        count = top_level_taxon_seen.get_occurrences_count_recursive()
        self.assertGreater(count, 0)
        total_occurrences = Occurrence.objects.filter(project=self.project_one).count()
        self.assertEqual(count, total_occurrences)
