"""
Building a training set from an occurrence set.

A run learns from a named set rather than from whatever happened to be verified that day,
so these tests are mostly about the set deciding what goes in.
"""

import datetime
import uuid

from django.test import TestCase

from ami.main.models import (
    Classification,
    Deployment,
    Detection,
    Event,
    Identification,
    Occurrence,
    OccurrenceSet,
    Project,
    S3StorageSource,
    SourceImage,
    Taxon,
    TaxonRank,
)
from ami.ml.models import Algorithm, AlgorithmCategoryMap
from ami.ml.models.embedding import DetectionEmbedding
from ami.ml.schemas import NamedReference
from ami.ml.training import NotEnoughVerifiedData, build_training_dataset, verified_training_rows
from ami.users.models import User

VECTOR_LENGTH = 8


class TrainingSetFixture(TestCase):
    """
    Occurrences, identifications and vectors built directly.

    The capture fixtures time their images from datetime.now() and group events by reading
    image dimensions from storage, neither of which is deterministic in a test.
    """

    def setUp(self) -> None:
        self.user = User.objects.create_user(email="curator@example.com", password="testpass123")
        self.project = Project.objects.create(name="Training Project", owner=self.user)
        storage = S3StorageSource.objects.create(name="src", project=self.project, bucket="test")
        self.deployment = Deployment.objects.create(name="station", project=self.project, data_source=storage)
        night = datetime.datetime(2026, 6, 1, 22, 0, 0, tzinfo=datetime.timezone.utc)
        self.event = Event.objects.create(deployment=self.deployment, project=self.project, start=night)
        self.night = night

        self.algorithm = Algorithm.objects.create(name="Backbone", key="backbone", trainable=True)
        self.taxa = [
            Taxon.objects.create(name=f"Trainus {name}", rank=TaxonRank.SPECIES.name) for name in ("alpha", "beta")
        ]
        for taxon in self.taxa:
            taxon.projects.add(self.project)
        self.algorithm.category_map = AlgorithmCategoryMap.objects.create(
            labels=[t.name for t in self.taxa],
            data=[{"index": i, "label": t.name} for i, t in enumerate(self.taxa)],
            version="training-test",
        )
        self.algorithm.save()

    def make_occurrence(self, taxon: Taxon, with_vector: bool = True) -> Occurrence:
        """One verified occurrence, optionally carrying a feature vector."""
        image = SourceImage.objects.create(
            deployment=self.deployment,
            project=self.project,
            event=self.event,
            timestamp=self.night,
            path=f"test/{uuid.uuid4().hex[:8]}.jpg",
        )
        detection = Detection.objects.create(source_image=image, timestamp=self.night, bbox=[0.1, 0.1, 0.2, 0.2])
        Classification.objects.create(detection=detection, taxon=taxon, score=0.9, timestamp=self.night)
        occurrence = detection.associate_new_occurrence()
        Identification.objects.create(occurrence=occurrence, taxon=taxon, user=self.user)
        if with_vector:
            DetectionEmbedding.objects.create(
                detection=detection,
                algorithm=self.algorithm,
                project=self.project,
                vector=[0.1] * VECTOR_LENGTH,
            )
        occurrence.refresh_from_db()
        return occurrence

    def make_set(self, name: str, occurrences: list[Occurrence]) -> OccurrenceSet:
        occurrence_set = OccurrenceSet.objects.create(name=name)
        occurrence_set.projects.add(self.project)
        occurrence_set.occurrences.set(occurrences)
        return occurrence_set


class TestTheSetDecidesWhatIsLearnedFrom(TrainingSetFixture):
    def test_only_the_sets_occurrences_are_used(self):
        inside = [self.make_occurrence(self.taxa[0]), self.make_occurrence(self.taxa[1])]
        outside = self.make_occurrence(self.taxa[0])
        occurrence_set = self.make_set("Spring review", inside)

        rows = verified_training_rows(self.project, self.algorithm, occurrence_set)
        used = {row.detection.occurrence_id for row in rows}

        self.assertEqual(used, {o.pk for o in inside})
        self.assertNotIn(outside.pk, used)

    def test_without_a_set_every_verified_occurrence_is_used(self):
        """The helper still answers without one; it is the job that insists on a set."""
        occurrences = [self.make_occurrence(self.taxa[0]), self.make_occurrence(self.taxa[1])]

        rows = verified_training_rows(self.project, self.algorithm)

        self.assertEqual({row.detection.occurrence_id for row in rows}, {o.pk for o in occurrences})

    def test_the_dataset_says_which_set_it_came_from(self):
        occurrences = [self.make_occurrence(self.taxa[0]) for _ in range(4)]
        occurrences += [self.make_occurrence(self.taxa[1]) for _ in range(4)]
        occurrence_set = self.make_set("Spring review", occurrences)

        # Half held out: the split is a hash of the occurrence, so a handful of rows at the
        # usual fifth can land entirely on one side, which the build refuses.
        dataset = build_training_dataset(
            project=self.project,
            algorithm=self.algorithm,
            min_per_species=1,
            test_fraction=0.5,
            occurrence_set=occurrence_set,
        )

        self.assertEqual(
            dataset["metadata"].occurrence_set,
            NamedReference(id=occurrence_set.pk, name="Spring review"),
        )
        self.assertEqual(dataset["metadata"].rows, 8)

    def test_an_empty_set_has_nothing_to_train_on(self):
        self.make_occurrence(self.taxa[0])
        empty = self.make_set("Nothing in here", [])

        with self.assertRaises(NotEnoughVerifiedData):
            build_training_dataset(
                project=self.project, algorithm=self.algorithm, min_per_species=1, occurrence_set=empty
            )

    def test_the_vector_width_comes_from_the_stored_vectors(self):
        """Nothing assumes a width: a backbone of another size is read, not truncated."""
        occurrences = [self.make_occurrence(self.taxa[0]) for _ in range(6)]
        occurrence_set = self.make_set("Spring review", occurrences)

        dataset = build_training_dataset(
            project=self.project,
            algorithm=self.algorithm,
            min_per_species=1,
            test_fraction=0.5,
            occurrence_set=occurrence_set,
        )

        self.assertEqual(dataset["metadata"].dimensions, VECTOR_LENGTH)

