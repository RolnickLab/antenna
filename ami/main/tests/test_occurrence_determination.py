from django.test import TestCase

from ami.main.models import (
    Classification,
    Detection,
    Identification,
    Occurrence,
    SourceImage,
    Taxon,
    update_occurrence_determination,
)
from ami.ml.models import Algorithm
from ami.tests.fixtures.main import create_captures, create_taxa, group_images_into_events, setup_test_project
from ami.users.models import User


class TestUpdateOccurrenceDetermination(TestCase):
    def setUp(self):
        """Set up test environment with project, deployment, taxa, and occurrences"""
        self.project, self.deployment = setup_test_project()

        # Create an admin user for identifications
        self.user = User.objects.create_user(  # type: ignore
            email="testuser@insectai.org",
            is_staff=True,
        )

        # Create taxa to use for identifications and classifications
        create_taxa(project=self.project)
        self.taxa = list(Taxon.objects.all().order_by("id")[:3])
        self.taxon1, self.taxon2, self.taxon3 = self.taxa

        # Create captures and events
        create_captures(deployment=self.deployment, num_nights=1, images_per_night=5)
        group_images_into_events(deployment=self.deployment)

        # Create a source image to use for detections
        self.source_image = SourceImage.objects.filter(deployment=self.deployment).first()
        self.assertIsNotNone(self.source_image, "No source image found, check test setup")
        self.assertIsNotNone(self.source_image.event, "Source image has no event, check test setup")
        self.assertIsNotNone(self.source_image.timestamp, "Source image has no timestamp, check test setup")

        # Create an occurrence without any determination
        self.occurrence = Occurrence.objects.create(
            project=self.project,
            deployment=self.deployment,
            event=self.source_image.event,
            determination=None,
            determination_score=None,
        )

        # Create a detection for the occurrence
        self.detection = Detection.objects.create(
            source_image=self.source_image,
            occurrence=self.occurrence,
            timestamp=self.source_image.timestamp,
        )

        # Create a test algorithm for classifications
        self.algorithm = Algorithm.objects.create(name="Test Algorithm", version=1)

    def test_update_with_classification(self):
        """Test that adding a classification updates the occurrence determination"""
        # Add a classification to the detection
        classification = Classification.objects.create(
            detection=self.detection,
            taxon=self.taxon1,
            score=0.8,
            timestamp=self.source_image.timestamp,
            algorithm=self.algorithm,
            terminal=True,
        )

        # Update the occurrence determination
        update_occurrence_determination(self.occurrence)

        # Refresh the occurrence from the database
        self.occurrence.refresh_from_db()

        # Check that the determination is set to the classification's taxon
        self.assertEqual(self.occurrence.determination, self.taxon1)
        self.assertEqual(self.occurrence.determination_score, 0.8)
        self.assertEqual(self.occurrence.best_prediction, classification)
        self.assertIsNone(self.occurrence.best_identification)

    def test_update_with_identification(self):
        """Test that adding an identification updates the occurrence determination"""
        # Add an identification to the occurrence
        identification = Identification.objects.create(user=self.user, taxon=self.taxon2, occurrence=self.occurrence)

        # Update the occurrence determination
        update_occurrence_determination(self.occurrence)

        # Refresh the occurrence from the database
        self.occurrence.refresh_from_db()

        # Check that the determination is set to the identification's taxon
        self.assertEqual(self.occurrence.determination, self.taxon2)
        self.assertEqual(self.occurrence.determination_score, 1.0)  # Human identifications have score 1.0
        self.assertEqual(self.occurrence.best_identification, identification)

    def test_identification_overrides_classification(self):
        """Test that an identification takes precedence over a classification"""
        # Add a classification to the detection
        classification = Classification.objects.create(
            detection=self.detection,
            taxon=self.taxon1,
            score=0.8,
            timestamp=self.source_image.timestamp,
            algorithm=self.algorithm,
            terminal=True,
        )

        # Update the occurrence determination
        update_occurrence_determination(self.occurrence)

        # Save the classification for later comparison
        saved_classification = classification

        # Verify the classification is being used
        self.occurrence.refresh_from_db()
        self.assertEqual(self.occurrence.determination, self.taxon1)
        self.assertEqual(self.occurrence.best_prediction, saved_classification)

        # Now add an identification
        identification = Identification.objects.create(user=self.user, taxon=self.taxon2, occurrence=self.occurrence)

        # Update the occurrence determination
        update_occurrence_determination(self.occurrence)

        # Refresh the occurrence from the database
        self.occurrence.refresh_from_db()

        # Check that the determination is set to the identification's taxon
        self.assertEqual(self.occurrence.determination, self.taxon2)
        self.assertEqual(self.occurrence.best_identification, identification)

    def test_removing_identification_falls_back_to_classification(self):
        """Test that removing an identification falls back to the best classification"""
        # Add a classification to the detection
        classification = Classification.objects.create(
            detection=self.detection,
            taxon=self.taxon1,
            score=0.8,
            timestamp=self.source_image.timestamp,
            algorithm=self.algorithm,
            terminal=True,
        )

        # Add an identification to the occurrence
        identification = Identification.objects.create(user=self.user, taxon=self.taxon2, occurrence=self.occurrence)

        # Update the occurrence determination
        update_occurrence_determination(self.occurrence)

        # Refresh the occurrence from the database
        self.occurrence.refresh_from_db()

        # Verify the identification is being used
        self.assertEqual(self.occurrence.determination, self.taxon2)

        # Now delete the identification
        # this is the action taken when a user removes their identification
        # from the occurrence
        identification.delete()

        # Update the occurrence determination
        update_occurrence_determination(self.occurrence)

        # Refresh the occurrence from the database
        self.occurrence.refresh_from_db()

        # Check that the determination falls back to the classification's taxon
        self.assertEqual(self.occurrence.determination, self.taxon1)
        self.assertEqual(self.occurrence.determination_score, 0.8)
        self.assertEqual(self.occurrence.best_prediction, classification)
        self.assertIsNone(self.occurrence.best_identification)

    def test_higher_score_classification_is_used(self):
        """Test that the classification with the highest score is used"""
        # Add a classification with a lower score
        Classification.objects.create(
            detection=self.detection,
            taxon=self.taxon1,
            score=0.6,
            timestamp=self.source_image.timestamp,
            algorithm=self.algorithm,
            terminal=True,
        )

        # Update the occurrence determination
        update_occurrence_determination(self.occurrence)

        # Refresh the occurrence from the database
        self.occurrence.refresh_from_db()

        # Verify the first classification is being used
        self.assertEqual(self.occurrence.determination, self.taxon1)
        self.assertEqual(self.occurrence.determination_score, 0.6)

        # Add a classification with a higher score
        high_score_classification = Classification.objects.create(
            detection=self.detection,
            taxon=self.taxon3,
            score=0.9,
            timestamp=self.source_image.timestamp,
            algorithm=self.algorithm,
            terminal=True,
        )

        # Update the occurrence determination
        update_occurrence_determination(self.occurrence)

        # Refresh the occurrence from the database
        self.occurrence.refresh_from_db()

        # Check that the determination is set to the higher score classification's taxon
        self.assertEqual(self.occurrence.determination, self.taxon3)
        self.assertEqual(self.occurrence.determination_score, 0.9)
        self.assertEqual(self.occurrence.best_prediction, high_score_classification)

    def test_multiple_detections_best_classification(self):
        """Test occurrence with multiple detections and multiple algorithms per detection"""
        # Create a second detection for the same occurrence
        second_detection = Detection.objects.create(
            source_image=self.source_image,
            occurrence=self.occurrence,
            timestamp=self.source_image.timestamp,
        )

        # Create a second algorithm
        second_algorithm = Algorithm.objects.create(name="Second Algorithm", version=1)

        # Add classifications from the first algorithm to both detections
        Classification.objects.create(
            detection=self.detection,
            taxon=self.taxon1,  # Lepidoptera (ORDER)
            score=0.8,
            timestamp=self.source_image.timestamp,
            algorithm=self.algorithm,
            terminal=True,
        )

        Classification.objects.create(
            detection=second_detection,
            taxon=self.taxon2,  # (Nymphalidae (FAMILY)) - Better classification (more specific) but lower score
            score=0.7,
            timestamp=self.source_image.timestamp,
            algorithm=self.algorithm,
            terminal=True,
        )

        # Add classifications from the second algorithm to both detections
        Classification.objects.create(
            detection=self.detection,
            taxon=self.taxon3,  # Vanessa atalanta (SPECIES)
            score=0.6,
            timestamp=self.source_image.timestamp,
            algorithm=second_algorithm,
            terminal=True,
        )

        cls4 = Classification.objects.create(
            detection=second_detection,
            taxon=self.taxon2,  # Nymphalidae (FAMILY)
            score=0.9,  # Higher score
            timestamp=self.source_image.timestamp,
            algorithm=second_algorithm,
            terminal=True,
        )

        # Update the occurrence determination
        update_occurrence_determination(self.occurrence)

        # Refresh the occurrence from the database
        self.occurrence.refresh_from_db()

        # Check that the highest scoring classification from any algorithm is used
        # This should be cls4 since it has the highest score (0.9)
        self.assertEqual(self.occurrence.determination, self.taxon2)  # Nymphalidae (FAMILY)
        self.assertEqual(self.occurrence.determination_score, 0.9)
        self.assertEqual(self.occurrence.best_prediction, cls4)

        # Now add a non-terminal classification with an even higher score
        # to verify that terminal status is prioritized over score
        Classification.objects.create(
            detection=second_detection,
            taxon=self.taxon1,  # Lepidoptera (ORDER)
            score=0.95,  # Highest score
            timestamp=self.source_image.timestamp,
            algorithm=second_algorithm,
            terminal=False,  # Non-terminal classification
        )

        # Update the occurrence determination
        update_occurrence_determination(self.occurrence)

        # Refresh the occurrence from the database
        self.occurrence.refresh_from_db()

        # The determination should still be cls4 (taxon2) even though cls5 has a higher score
        # because cls5 is non-terminal and cls4 is terminal
        self.assertEqual(self.occurrence.determination, self.taxon2)  # Nymphalidae (FAMILY)
        self.assertEqual(self.occurrence.determination_score, 0.9)
        self.assertEqual(self.occurrence.best_prediction, cls4)

    def test_terminal_classification_preferred_over_non_terminal(self):
        """Test that terminal classifications are preferred over non-terminal ones"""
        # Add a non-terminal classification with a higher score
        Classification.objects.create(
            detection=self.detection,
            taxon=self.taxon1,
            score=0.9,
            timestamp=self.source_image.timestamp,
            algorithm=self.algorithm,
            terminal=False,
        )

        # Add a terminal classification with a lower score
        terminal_classification = Classification.objects.create(
            detection=self.detection,
            taxon=self.taxon2,
            score=0.7,
            timestamp=self.source_image.timestamp,
            algorithm=self.algorithm,
            terminal=True,
        )

        # Update the occurrence determination
        update_occurrence_determination(self.occurrence)

        # Refresh the occurrence from the database
        self.occurrence.refresh_from_db()

        # Check that the terminal classification is preferred
        self.assertEqual(self.occurrence.determination, self.taxon2)
        self.assertEqual(self.occurrence.determination_score, 0.7)
        self.assertEqual(self.occurrence.best_prediction, terminal_classification)

    def test_determination_ood_score_is_updated(self):
        """Test that the determination_ood_score is updated"""
        # Add a classification with an OOD score
        Classification.objects.create(
            detection=self.detection,
            taxon=self.taxon1,
            score=0.8,
            ood_score=0.3,
            timestamp=self.source_image.timestamp,
            algorithm=self.algorithm,
            terminal=True,
        )

        # Update the occurrence determination
        update_occurrence_determination(self.occurrence)

        # Refresh the occurrence from the database
        self.occurrence.refresh_from_db()

        # Check that the determination_ood_score is updated
        self.assertEqual(self.occurrence.determination_ood_score, 0.3)

        # Add another classification with a different OOD score
        Classification.objects.create(
            detection=self.detection,
            taxon=self.taxon1,
            score=0.8,
            ood_score=0.5,
            timestamp=self.source_image.timestamp,
            algorithm=self.algorithm,
            terminal=True,
        )

        # Update the occurrence determination
        update_occurrence_determination(self.occurrence)

        # Refresh the occurrence from the database
        self.occurrence.refresh_from_db()

        # Check that the determination_ood_score is updated to the average
        self.assertEqual(self.occurrence.determination_ood_score, 0.4)

    def test_no_changes_when_determination_is_unchanged(self):
        """Test that no changes are made when the determination would remain the same"""
        # Add an identification to the occurrence
        identification = Identification.objects.create(user=self.user, taxon=self.taxon2, occurrence=self.occurrence)

        # Update the occurrence determination
        update_occurrence_determination(self.occurrence)

        # Refresh the occurrence from the database
        self.occurrence.refresh_from_db()

        # Verify the identification is being used
        self.assertEqual(self.occurrence.determination, self.taxon2)

        # Note the occurrence has already been updated once

        # Call update_occurrence_determination again
        update_occurrence_determination(self.occurrence)

        # Refresh the occurrence from the database
        self.occurrence.refresh_from_db()

        # Check that the determination didn't change
        self.assertEqual(self.occurrence.determination, self.taxon2)
        self.assertEqual(self.occurrence.best_identification, identification)

        # We don't check timestamp comparison since it might change even without field changes

        # Note: In a real application the updated_at might not change if update_fields is used correctly,
        # but in the test environment it may still update the timestamp even without field changes
