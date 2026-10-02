"""Where a stored algorithm output records its project, its job and its vector.

These pin the rules every algorithm-output table follows: ``project`` is copied from the
row's parent by one helper (never guessed, never left null), the job that wrote a row is
recorded and outlives no row, and embeddings are written insert-mostly under one key.
"""

import datetime

from django.db.models import RestrictedError
from django.test import TestCase
from rest_framework.test import APITestCase

from ami.jobs.models import Job
from ami.main.models import Classification, Detection, DetectionEmbedding, Occurrence, Project, SourceImage
from ami.main.models_future.embeddings import algorithm_ids_with_vectors, vectors_for_detections
from ami.main.models_future.project_scope import ProjectScopeError, project_mismatch_counts
from ami.ml.exceptions import FeatureResultsStoredNothing
from ami.ml.models import Algorithm
from ami.ml.models.pipeline import save_results
from ami.ml.post_processing.small_size_filter import SmallSizeFilterTask
from ami.ml.post_processing.tracking_task import record_tracking_determination
from ami.ml.schemas import PipelineResultsResponse
from ami.ml.test_feature_extraction import BIOCLIP_DIMENSIONS, FeatureOnlyFixture
from ami.users.models import User


class TestEmbeddingProject(FeatureOnlyFixture, TestCase):
    """An embedding's project is its capture's, falling back to the capture's station's."""

    def setUp(self) -> None:
        self._set_up_project(images=2, boxes_per_image=1)
        self.detection = Detection.objects.filter(source_image=self.images[0], bbox__isnull=False).get()
        self.other_project = Project.objects.create(name="Another project")

    def _embedding(self, **fields) -> DetectionEmbedding:
        return DetectionEmbedding(
            detection=self.detection, algorithm=self.extractor, vector=[0.5] * BIOCLIP_DIMENSIONS, **fields
        )

    def test_save_and_bulk_create_take_the_captures_project_over_a_passed_one(self):
        saved = self._embedding(project=self.other_project)
        saved.save()
        self.assertEqual(saved.project_id, self.project.pk)

        DetectionEmbedding.objects.all().delete()
        DetectionEmbedding.objects.bulk_create([self._embedding(project=self.other_project)])
        self.assertEqual(DetectionEmbedding.objects.get().project_id, self.project.pk)
        self.assertEqual(project_mismatch_counts()["main.DetectionEmbedding"], 0)

    def test_a_capture_without_a_project_falls_back_to_its_station(self):
        SourceImage.objects.filter(pk=self.images[0].pk).update(project=None)
        DetectionEmbedding.objects.bulk_create([self._embedding()])
        self.assertEqual(DetectionEmbedding.objects.get().project_id, self.project.pk)

    def test_no_project_anywhere_refuses_the_write(self):
        SourceImage.objects.filter(pk=self.images[0].pk).update(project=None)
        self.deployment.__class__.objects.filter(pk=self.deployment.pk).update(project=None)
        with self.assertRaises(ProjectScopeError):
            DetectionEmbedding.objects.bulk_create([self._embedding()])
        with self.assertRaises(ProjectScopeError):
            self._embedding().save()
        self.assertFalse(DetectionEmbedding.objects.exists())

    def test_a_capture_disagreeing_with_its_station_keeps_its_own_project_and_warns(self):
        SourceImage.objects.filter(pk=self.images[0].pk).update(project=self.other_project)
        with self.assertLogs("ami.main.models_future.project_scope", level="WARNING") as logs:
            DetectionEmbedding.objects.bulk_create([self._embedding()])
        self.assertEqual(DetectionEmbedding.objects.get().project_id, self.other_project.pk)
        self.assertIn(f"({self.detection.pk}, {self.other_project.pk}, {self.project.pk})", logs.output[0])

    def test_the_mismatch_check_counts_rows_that_drifted_from_their_capture(self):
        self._embedding().save()
        self.assertEqual(project_mismatch_counts()["main.DetectionEmbedding"], 0)

        SourceImage.objects.filter(pk=self.images[0].pk).update(project=self.other_project)
        self.assertEqual(project_mismatch_counts()["main.DetectionEmbedding"], 1)


class TestEmbeddingWrites(FeatureOnlyFixture, TestCase):
    """Embeddings are written insert-mostly, one row per (detection, algorithm, key)."""

    def setUp(self) -> None:
        self._set_up_project(images=1, boxes_per_image=2)
        self.boxes = [(self.images[0], detection.bbox) for detection in self._real_detections()]

    def _real_detections(self) -> list[Detection]:
        return list(Detection.objects.filter(source_image=self.images[0], bbox__isnull=False).order_by("pk"))

    def _save(self, value: float, job: Job | None = None) -> None:
        response = self._response(self.boxes).dict()
        for detection in response["detections"]:
            detection["embeddings"][0]["features"] = [value] * BIOCLIP_DIMENSIONS
        save_results(PipelineResultsResponse.parse_obj(response), job_id=job.pk if job else None)

    def test_an_identical_vector_is_not_rewritten_and_a_new_one_replaces_the_row(self):
        self._save(0.25)
        first = dict(DetectionEmbedding.objects.values_list("detection_id", "pk"))

        self._save(0.25)
        self.assertEqual(dict(DetectionEmbedding.objects.values_list("detection_id", "pk")), first)

        self._save(0.75)
        replaced = dict(DetectionEmbedding.objects.values_list("detection_id", "pk"))
        self.assertEqual(replaced.keys(), first.keys())
        self.assertTrue(set(replaced.values()).isdisjoint(first.values()))
        vectors = vectors_for_detections(first.keys(), self.extractor.pk)
        self.assertEqual({float(v[0]) for v in vectors.values()}, {0.75})

    def test_a_vector_half_precision_cannot_hold_is_skipped(self):
        with self.assertRaises(FeatureResultsStoredNothing):
            self._save(1e6)
        self.assertFalse(DetectionEmbedding.objects.exists())

    def test_readers_compare_one_key_only(self):
        detection = self._real_detections()[0]
        DetectionEmbedding.objects.bulk_create(
            [
                DetectionEmbedding(detection=detection, algorithm=self.extractor, vector=[0.25] * 4),
                DetectionEmbedding(detection=detection, algorithm=self.extractor, key="projection", vector=[0.5] * 2),
            ]
        )
        self.assertEqual(len(vectors_for_detections([detection.pk], self.extractor.pk)[detection.pk]), 4)
        self.assertEqual(
            len(vectors_for_detections([detection.pk], self.extractor.pk, key="projection")[detection.pk]), 2
        )
        self.assertEqual(algorithm_ids_with_vectors(key="other", pk=detection.pk), set())

    def test_a_job_with_vectors_is_kept_until_its_project_goes(self):
        job = Job.objects.create(project=self.project, name="Feature job", pipeline=self.pipeline)
        self._save(0.25, job=job)
        self.assertEqual(set(DetectionEmbedding.objects.values_list("job_id", flat=True)), {job.pk})

        with self.assertRaises(RestrictedError):
            job.delete()

        self.project.delete()
        self.assertFalse(DetectionEmbedding.objects.exists())
        self.assertFalse(Job.objects.filter(pk=job.pk).exists())


class TestJobDeleteEndpoint(FeatureOnlyFixture, APITestCase):
    """Deleting a job whose outputs still name it hides the job, so their provenance stays."""

    def setUp(self) -> None:
        self._set_up_project(images=1, boxes_per_image=1)
        self.client.force_authenticate(User.objects.create_superuser(email="emb-admin@example.org", password="x"))

    def _delete(self, job: Job):
        return self.client.delete(f"/api/v2/jobs/{job.pk}/?project_id={self.project.pk}")

    def _listed_ids(self, *params: str) -> set[int]:
        query = "&".join([f"project_id={self.project.pk}", *params])
        return {row["id"] for row in self.client.get(f"/api/v2/jobs/?{query}").json()["results"]}

    def test_a_job_with_stored_vectors_is_hidden_not_deleted(self):
        job = Job.objects.create(project=self.project, name="Feature job", pipeline=self.pipeline)
        detection = Detection.objects.filter(bbox__isnull=False).first()
        DetectionEmbedding.objects.create(detection=detection, algorithm=self.extractor, vector=[0.5] * 4, job=job)

        response = self._delete(job)

        self.assertEqual(response.status_code, 204, response.content)
        job.refresh_from_db()
        self.assertTrue(job.hidden)
        self.assertNotIn(job.pk, self._listed_ids())
        self.assertIn(job.pk, self._listed_ids("include_hidden=true"))
        self.assertEqual(self.client.get(f"/api/v2/jobs/{job.pk}/?project_id={self.project.pk}").status_code, 200)

    def test_a_job_named_only_by_classifications_is_hidden_too(self):
        job = Job.objects.create(project=self.project, name="Classifier job", pipeline=self.pipeline)
        Classification.objects.filter(detection__source_image__project=self.project).update(job=job)

        self.assertEqual(self._delete(job).status_code, 204)
        self.assertTrue(Job.objects.get(pk=job.pk).hidden)

    def test_a_job_without_outputs_is_deleted(self):
        job = Job.objects.create(project=self.project, name="Empty job", pipeline=self.pipeline)

        self.assertEqual(self._delete(job).status_code, 204)
        self.assertFalse(Job.objects.filter(pk=job.pk).exists())


class TestOutputsRecordTheirJob(FeatureOnlyFixture, TestCase):
    """Detections and classifications name the job that saved them, so a run's output can be found."""

    def setUp(self) -> None:
        self._set_up_project(images=1, boxes_per_image=1)
        self.job = Job.objects.create(project=self.project, name="Outputs job", job_type_key="post_processing")
        self.job.progress.add_stage("Post-processing", key="post_processing")
        self.job.save()

    def test_the_size_filter_records_its_job_on_the_classifications_it_adds(self):
        SourceImage.objects.filter(pk=self.images[0].pk).update(width=10_000, height=10_000)
        occurrence = Occurrence.objects.filter(detections__bbox__isnull=False).first()
        before = set(Classification.objects.values_list("pk", flat=True))

        SmallSizeFilterTask(job=self.job, occurrence_id=occurrence.pk, size_threshold=0.5).run()

        added = Classification.objects.exclude(pk__in=before)
        self.assertTrue(added.exists())
        self.assertEqual(set(added.values_list("job_id", flat=True)), {self.job.pk})

    def test_tracking_records_its_job_on_the_determination_it_leaves(self):
        occurrence = Occurrence.objects.filter(detections__bbox__isnull=False).first()
        classification = Classification.objects.get(detection__occurrence=occurrence)
        taxon = self._taxon()
        Classification.objects.filter(pk=classification.pk).update(taxon=taxon)
        occurrence.save(update_determination=True)
        tracker = Algorithm.objects.create(name="Tracker", key="test-tracker", task_type="tracking")

        recorded = record_tracking_determination(occurrence, tracker, job=self.job)

        self.assertIsNotNone(recorded)
        self.assertEqual(recorded.job_id, self.job.pk)

    @staticmethod
    def _taxon():
        from ami.main.models import Taxon

        return Taxon.objects.create(name=f"Tracked taxon {datetime.datetime.now().timestamp()}")
