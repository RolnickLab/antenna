"""
Building a training set from an occurrence set.

A run learns from a named set rather than from whatever happened to be verified that day,
so these tests are mostly about the set deciding what goes in.
"""

import datetime
import uuid

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

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
from ami.users.roles import ProjectManager

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


class TestTheSummaryTheFormShows(TrainingSetFixture):
    """
    The numbers the training job form puts in front of someone before they start a run.

    A form that asked for a split ratio without saying how many occurrences it would split
    would be asking blind, so these cover what changes when the set or the ratio changes.
    """

    def setUp(self) -> None:
        super().setUp()
        ProjectManager.assign_user(self.user, self.project)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.url = reverse("api:training-data-summary")

    def _summary(self, **params):
        response = self.client.get(
            self.url,
            {"project_id": self.project.pk, "algorithm": self.algorithm.key, **params},
        )
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def test_without_a_set_it_counts_every_verified_occurrence(self):
        for taxon in self.taxa:
            self.make_occurrence(taxon)

        summary = self._summary()

        self.assertIsNone(summary["occurrence_set"])
        self.assertEqual(summary["occurrences"], 2)
        self.assertEqual(summary["rows"], 2)

    def test_a_set_narrows_the_counts_and_is_named_back(self):
        mine = self.make_set("Mine", [self.make_occurrence(self.taxa[0])])
        self.make_occurrence(self.taxa[1])

        summary = self._summary(occurrence_set=mine.pk)

        self.assertEqual(summary["occurrence_set"], {"id": mine.pk, "name": "Mine"})
        self.assertEqual(summary["occurrences"], 1)

    def test_a_set_from_another_project_is_not_counted(self):
        other = Project.objects.create(name="Someone else", owner=self.user)
        theirs = OccurrenceSet.objects.create(name="Theirs")
        theirs.projects.add(other)

        response = self.client.get(
            self.url,
            {"project_id": self.project.pk, "algorithm": self.algorithm.key, "occurrence_set": theirs.pk},
        )

        self.assertEqual(response.status_code, 404)

    def test_the_split_ratio_moves_the_counts(self):
        """
        Compared across two ratios rather than asserted exactly.

        Which side a given occurrence falls on is a hash of its id, so with a handful of
        rows a particular ratio does not produce a particular count.
        """
        for taxon in self.taxa:
            self.make_occurrence(taxon)
            self.make_occurrence(taxon)

        mostly_train = self._summary(test_fraction=0.01)
        mostly_test = self._summary(test_fraction=0.99)

        self.assertEqual(mostly_test["rows"], mostly_train["rows"])
        self.assertGreater(mostly_test["test"], mostly_train["test"])
        self.assertEqual(mostly_test["settings"]["test_fraction"], 0.99)

    def test_a_ratio_no_run_could_use_is_refused(self):
        response = self.client.get(
            self.url,
            {"project_id": self.project.pk, "algorithm": self.algorithm.key, "test_fraction": 1.5},
        )

        self.assertEqual(response.status_code, 400)

    def test_species_without_enough_crops_are_reported_as_dropped(self):
        self.make_occurrence(self.taxa[0])
        self.make_occurrence(self.taxa[1])
        self.make_occurrence(self.taxa[1])

        summary = self._summary(min_per_species=2)

        self.assertEqual(summary["classes"], 2)
        self.assertEqual(summary["trainable_classes"], 1)
        self.assertEqual(summary["dropped_species"], [self.taxa[0].name])

    def test_someone_who_cannot_retrain_cannot_read_the_training_set(self):
        """
        A non-draft project is readable by anyone, so visibility alone would hand every
        verified label and vector to any account. The permission is the gate.
        """
        self.make_occurrence(self.taxa[0])
        outsider = User.objects.create_user(email="outsider@example.com", password="testpass123")
        self.client.force_authenticate(user=outsider)

        response = self.client.get(self.url, {"project_id": self.project.pk, "algorithm": self.algorithm.key})

        self.assertEqual(response.status_code, 403)


class TestTheJobsOccurrenceSet(TrainingSetFixture):
    def _job(self, **params):
        from ami.jobs.models import Job, TrainClassifierJob

        return Job.objects.create(
            project=self.project,
            name="Retrain",
            job_type_key=TrainClassifierJob.key,
            params={"algorithm_key": self.algorithm.key, **params},
        )

    def test_a_job_without_a_set_learns_from_everything_verified(self):
        from ami.jobs.models import TrainClassifierJob

        self.assertIsNone(TrainClassifierJob.target_occurrence_set(self._job()))

    def test_a_set_from_another_project_is_refused(self):
        from ami.jobs.models import TrainClassifierJob

        other = Project.objects.create(name="Someone else", owner=self.user)
        theirs = OccurrenceSet.objects.create(name="Theirs")
        theirs.projects.add(other)

        with self.assertRaises(ValueError) as caught:
            TrainClassifierJob.target_occurrence_set(self._job(occurrence_set_id=theirs.pk))

        self.assertIn("in this project", str(caught.exception))

    def test_a_set_in_this_project_is_used(self):
        from ami.jobs.models import TrainClassifierJob

        mine = self.make_set("Mine", [self.make_occurrence(self.taxa[0])])

        self.assertEqual(TrainClassifierJob.target_occurrence_set(self._job(occurrence_set_id=mine.pk)), mine)


class TestTheTrainingStageFollowsTheEpochs(TrainingSetFixture):
    """
    Training is the long stage and the service is silent while it fits, so the epochs it
    reports are the only thing that can move the stage while a run is going.
    """

    def setUp(self) -> None:
        super().setUp()
        from ami.jobs.models import Job, TrainClassifierJob

        self.job = Job.objects.create(
            project=self.project,
            name="Retrain",
            job_type_key=TrainClassifierJob.key,
            params={"algorithm_key": self.algorithm.key},
        )
        self.job.progress.add_stage("Training", TrainClassifierJob.STAGE_TRAIN)
        self.url = reverse("api:job-training-progress", args=[self.job.pk])

    def _stage(self):
        from ami.jobs.models import Job, TrainClassifierJob

        job = Job.objects.get(pk=self.job.pk)
        return job.progress.get_stage(TrainClassifierJob.STAGE_TRAIN)

    def _param(self, name: str):
        from ami.jobs.models import Job, TrainClassifierJob

        job = Job.objects.get(pk=self.job.pk)
        return job.progress.get_stage_param(TrainClassifierJob.STAGE_TRAIN, job.progress.make_key(name)).value

    def _post(self, **payload):
        from ami.ml.training import make_callback_token

        return APIClient().post(
            self.url,
            payload,
            format="json",
            HTTP_AUTHORIZATION=f"Token {make_callback_token(self.job)}",
        )

    def test_a_ping_moves_the_stage(self):
        from ami.jobs.models import TrainClassifierJob

        response = self._post(epoch=150, total_epochs=300)

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self._param(TrainClassifierJob.PARAM_EPOCH), 150)
        self.assertEqual(self._param(TrainClassifierJob.PARAM_TOTAL_EPOCHS), 300)
        self.assertEqual(self._stage().progress, 0.5)

    def test_the_stage_is_never_finished_by_an_epoch(self):
        """The result finishes it: the service still has to score the head and upload it."""
        self._post(epoch=300, total_epochs=300)

        self.assertEqual(self._stage().progress, 0.99)

    def test_a_ping_that_arrives_late_is_ignored(self):
        self._post(epoch=200, total_epochs=300)
        self._post(epoch=100, total_epochs=300)

        from ami.jobs.models import TrainClassifierJob

        self.assertEqual(self._param(TrainClassifierJob.PARAM_EPOCH), 200)

    def test_a_ping_without_the_token_is_refused(self):
        response = APIClient().post(self.url, {"epoch": 10}, format="json")

        self.assertEqual(response.status_code, 403)

    def test_a_ping_after_the_job_finished_changes_nothing(self):
        from ami.jobs.models import JobState, TrainClassifierJob

        self.job.status = JobState.SUCCESS
        self.job.save()

        response = self._post(epoch=10, total_epochs=300)

        self.assertEqual(response.status_code, 200)
        with self.assertRaises(ValueError):
            self._param(TrainClassifierJob.PARAM_EPOCH)


class TestTheResultComingBackFromAService(TrainingSetFixture):
    """
    The callback is the one way a result arrives, so its shape is the contract.

    A service posts the result together with the training set's own metadata, echoed back
    from the file Antenna wrote. That echo is where a registered version learns which
    occurrence set it came from.
    """

    def setUp(self) -> None:
        super().setUp()
        from ami.jobs.models import Job, TrainClassifierJob

        self.occurrence_set = self.make_set("Mine", [self.make_occurrence(self.taxa[0])])
        self.job = Job.objects.create(
            project=self.project,
            name="Retrain",
            job_type_key=TrainClassifierJob.key,
            params={"algorithm_key": self.algorithm.key, "occurrence_set_id": self.occurrence_set.pk},
        )
        self.url = reverse("api:job-training-result", args=[self.job.pk])

    def _dataset_echo(self, **overrides) -> dict:
        """The metadata a service reads out of the training set and sends back."""
        from ami.ml.schemas import (
            NamedReference,
            TrainedAlgorithmReference,
            TrainingDatasetMetadata,
            TrainingDatasetSettings,
        )

        metadata = TrainingDatasetMetadata(
            url="/media/training/set.npz",
            project=NamedReference(id=self.project.pk, name=self.project.name),
            algorithm=TrainedAlgorithmReference(key=self.algorithm.key, name=self.algorithm.name, version=1),
            dimensions=VECTOR_LENGTH,
            dtype="float32",
            classes=[t.name for t in self.taxa],
            rows=6,
            train=5,
            test=1,
            occurrence_set=NamedReference(id=self.occurrence_set.pk, name=self.occurrence_set.name),
            settings=TrainingDatasetSettings(min_per_species=2, split_salt="antenna-head-v1", test_fraction=0.2),
        )
        return {**metadata.dict(), **overrides}

    def _post(self, payload: dict):
        from ami.ml.training import make_callback_token

        return APIClient().post(
            self.url,
            payload,
            format="json",
            HTTP_AUTHORIZATION=f"Token {make_callback_token(self.job)}",
        )

    def _result(self, **overrides) -> dict:
        return {
            "promote": False,
            "reason": "The new head did not beat the current one.",
            "warnings": ["Only 1 held-out row(s)."],
            "labels": [t.name for t in self.taxa],
            "rows": {"kept": 6, "dropped": 0},
            "candidate_metrics": {"top1": 0.8},
            "incumbent_metrics": {"top1": 0.9},
            "trained_at": "2026-10-08T23:00:00",
            "head_url": "/media/algorithms/head.npz",
            **overrides,
        }

    def test_a_result_registers_a_version_that_says_what_it_learned_from(self):
        from ami.jobs.models import Job
        from ami.ml.models import Algorithm

        response = self._post({"result": self._result(), "dataset": self._dataset_echo()})

        self.assertEqual(response.status_code, 200, response.data)
        version = Algorithm.objects.get(key=response.data["algorithm"])
        self.assertEqual(version.training_info.occurrence_set_id, self.occurrence_set.pk)
        self.assertEqual(version.training_info.occurrence_set_name, "Mine")
        self.assertEqual(version.training_info.dataset_rows, 6)
        self.assertEqual(version.training_info.metrics, {"top1": 0.8})
        self.assertEqual(version.training_info.previous_metrics, {"top1": 0.9})
        self.assertEqual(Job.objects.get(pk=self.job.pk).status, "SUCCESS")

    def test_an_echo_antenna_cannot_read_still_records_the_result(self):
        """
        A service echoing an older shape loses the provenance, not the run.

        Refusing the whole callback would throw away a head that was trained successfully.
        """
        from ami.ml.models import Algorithm

        response = self._post({"result": self._result(), "dataset": {"unexpected": "shape"}})

        self.assertEqual(response.status_code, 200, response.data)
        version = Algorithm.objects.get(key=response.data["algorithm"])
        self.assertIsNone(version.training_info.occurrence_set_id)

    def test_a_run_with_no_current_head_to_compare_against_is_recorded(self):
        """
        A service reports a null incumbent rather than leaving the field out.

        Refusing that would throw away the result of a first-ever retrain, which is the
        one run guaranteed to have nothing to compare against.
        """
        from ami.ml.models import Algorithm

        response = self._post({"result": self._result(incumbent_metrics=None), "dataset": self._dataset_echo()})

        self.assertEqual(response.status_code, 200, response.data)
        version = Algorithm.objects.get(key=response.data["algorithm"])
        self.assertEqual(version.training_info.previous_metrics, {})

    def test_a_result_antenna_cannot_read_is_refused(self):
        """The result is what the new version is built from, so a broken one is a 400."""
        response = self._post({"result": {"labels": "not a list"}, "dataset": self._dataset_echo()})

        self.assertEqual(response.status_code, 400)

    def test_a_second_callback_does_not_register_a_second_version(self):
        from ami.ml.models import Algorithm

        self._post({"result": self._result(), "dataset": self._dataset_echo()})
        before = Algorithm.objects.count()
        again = self._post({"result": self._result(), "dataset": self._dataset_echo()})

        self.assertEqual(again.status_code, 200)
        self.assertEqual(again.data["status"], "already recorded")
        self.assertEqual(Algorithm.objects.count(), before)
