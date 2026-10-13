"""Round trips against the minimal processing service, the ``ml_backend`` container of the CI stack.

These pin the processing-service contract end to end, with no mocked HTTP: what Antenna sends
(including a project's pipeline config) and how it stores what comes back (including feature
vectors). The service's output is deterministic; see processing_services/README.md.
"""

from urllib.parse import urljoin

from django.test import TestCase

from ami.main.models import Classification, Detection
from ami.ml.embeddings.writer import save_embedding_results
from ami.ml.models import DetectionEmbedding, ProjectPipelineConfig
from ami.ml.models.pipeline import process_detections, save_results
from ami.tests.fixtures.main import create_captures_from_files, create_processing_service, setup_test_project

EXTRACTOR_KEY = "constant-feature-extractor"
EXTRACTOR_VECTOR_LENGTH = 8


class TestMinimalProcessingServiceContract(TestCase):
    def setUp(self):
        self.project, self.deployment = setup_test_project()
        self.images = [image for image, _ in create_captures_from_files(self.deployment, skip_existing=False)]
        self.service = create_processing_service(self.project)
        self.extractor_pipeline = self.service.pipelines.get(slug="constant-with-feature-extractor")

    def detections(self):
        return Detection.objects.filter(source_image__in=self.images)

    def test_vectors_from_a_synchronous_request_are_stored_on_every_detection(self):
        save_results(self.extractor_pipeline.process_images(self.images, project_id=self.project.pk))

        vectors = DetectionEmbedding.objects.filter(detection__in=self.detections())
        self.assertTrue(self.detections().exists())
        self.assertEqual(vectors.count(), self.detections().count())
        self.assertEqual(
            {(vector.algorithm.key, len(vector.vector)) for vector in vectors},
            {(EXTRACTOR_KEY, EXTRACTOR_VECTOR_LENGTH)},
        )
        self.assertTrue(Classification.objects.filter(detection__in=self.detections()).exists())

    def test_the_projects_pipeline_config_is_sent_with_the_request(self):
        # The extractor runs by default (previous test); the project's config turns it off.
        ProjectPipelineConfig.objects.update_or_create(
            project=self.project, pipeline=self.extractor_pipeline, defaults={"config": {"embedding_extractor": ""}}
        )
        response = self.extractor_pipeline.process_images(self.images, project_id=self.project.pk)

        self.assertTrue(response.detections)
        self.assertTrue(all(not detection.embeddings for detection in response.detections))

    def test_stored_detections_get_vectors_from_a_feature_only_pipeline_without_new_rows(self):
        save_results(
            self.service.pipelines.get(slug="constant").process_images(self.images, project_id=self.project.pk)
        )
        detections = list(
            self.detections().select_related("source_image__deployment__data_source", "detection_algorithm")
        )
        classification_count = Classification.objects.filter(detection__in=detections).count()
        feature_only = self.service.pipelines.get(slug="constant-feature-extractor-only")

        response = process_detections(
            feature_only, urljoin(self.service.endpoint_url, "/process"), detections, self.project.pk
        )
        result = save_embedding_results(response, None, feature_only)

        self.assertTrue(detections)
        self.assertEqual((result.written, result.unmatched), (len(detections), 0))
        self.assertEqual(self.detections().count(), len(detections))
        self.assertEqual(Classification.objects.filter(detection__in=detections).count(), classification_count)
        self.assertEqual(
            DetectionEmbedding.objects.filter(detection__in=detections, algorithm__key=EXTRACTOR_KEY).count(),
            len(detections),
        )
