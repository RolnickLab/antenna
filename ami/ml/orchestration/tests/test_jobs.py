from unittest.mock import AsyncMock, patch

from django.test import TestCase

from ami.jobs.models import Job, JobDispatchMode, MLJob
from ami.main.models import Deployment, Project, S3StorageSource, SourceImage, SourceImageCollection
from ami.ml.models import Pipeline
from ami.ml.orchestration.jobs import NATS_PUBLISH_FANOUT_CHUNK_SIZE, queue_images_to_nats


def _stub_manager(mock_manager_cls, publish_results=None):
    """Return an AsyncMock TaskQueueManager instance with publish_task pre-stubbed.

    publish_results is an optional iterable of bools matching publish_task call
    order. Defaults to always-True.
    """
    instance = mock_manager_cls.return_value
    instance.__aenter__ = AsyncMock(return_value=instance)
    instance.__aexit__ = AsyncMock(return_value=False)
    instance.ensure_job_resources = AsyncMock()
    instance._ensure_stream = AsyncMock()
    instance._ensure_consumer = AsyncMock()
    instance.log_async = AsyncMock()
    if publish_results is None:
        instance.publish_task = AsyncMock(return_value=True)
    else:
        instance.publish_task = AsyncMock(side_effect=list(publish_results))
    return instance


@patch("ami.ml.orchestration.jobs.AsyncJobStateManager")
@patch("ami.ml.orchestration.jobs.TaskQueueManager")
class TestQueueImagesToNatsFanout(TestCase):
    """Unit-test the chunk+gather behaviour of queue_images_to_nats.

    The integration test in test_cleanup.py uses a real NATS server. These
    tests instead mock TaskQueueManager so they run without infrastructure and
    can assert on call counts.
    """

    def setUp(self):
        self.project = Project.objects.create(name="fanout test")
        self.data_source = S3StorageSource.objects.create(
            name="ds",
            bucket="b",
            access_key="x",
            secret_key="y",
            public_base_url="https://example.invalid/",
            project=self.project,
        )
        self.deployment = Deployment.objects.create(name="d", project=self.project, data_source=self.data_source)
        self.pipeline = Pipeline.objects.create(name="p", slug="p", version="1")
        self.collection = SourceImageCollection.objects.create(name="c", project=self.project)

    def _make_images(self, n: int) -> list[SourceImage]:
        # public_base_url is set so SourceImage.url() returns a truthy URL —
        # otherwise queue_images_to_nats skips the image and the inner loop
        # we're trying to test never runs.
        rows = [
            SourceImage(
                path=f"fanout/{i}.jpg",
                deployment=self.deployment,
                project=self.project,
                public_base_url="https://example.invalid/",
            )
            for i in range(n)
        ]
        SourceImage.objects.bulk_create(rows)
        return list(SourceImage.objects.filter(project=self.project).order_by("pk"))

    def _make_job(self) -> Job:
        return Job.objects.create(
            name="fanout",
            job_type_key=MLJob.key,
            project=self.project,
            pipeline=self.pipeline,
            source_image_collection=self.collection,
            dispatch_mode=JobDispatchMode.ASYNC_API,
        )

    def test_warms_stream_and_consumer_once_before_publishing(self, mock_mgr_cls, _state_cls):
        instance = _stub_manager(mock_mgr_cls)
        images = self._make_images(5)
        job = self._make_job()

        queue_images_to_nats(job, images)

        self.assertEqual(instance.ensure_job_resources.await_count, 1)
        self.assertEqual(instance.publish_task.await_count, 5)

    def test_chunks_across_fanout_boundary(self, mock_mgr_cls, _state_cls):
        instance = _stub_manager(mock_mgr_cls)
        # One full chunk + one short chunk: forces the inner loop to iterate twice.
        n = NATS_PUBLISH_FANOUT_CHUNK_SIZE + 7
        images = self._make_images(n)
        job = self._make_job()

        queue_images_to_nats(job, images)

        self.assertEqual(instance.publish_task.await_count, n)
        # Warm-up still only runs once even when we span multiple chunks.
        self.assertEqual(instance.ensure_job_resources.await_count, 1)

    def test_partial_failure_counted_as_failed_not_raised(self, mock_mgr_cls, _state_cls):
        # 3 images, middle one fails. Method should return False (failure summary)
        # but not raise — and the success count should reflect the two that worked.
        instance = _stub_manager(mock_mgr_cls, publish_results=[True, False, True])
        images = self._make_images(3)
        job = self._make_job()

        result = queue_images_to_nats(job, images)

        self.assertFalse(result)
        self.assertEqual(instance.publish_task.await_count, 3)

    def test_stream_setup_failure_short_circuits_publishing(self, mock_mgr_cls, _state_cls):
        # If ensure_job_resources raises, we should not attempt any publish_task
        # calls — the whole batch is marked failed in one shot.
        instance = _stub_manager(mock_mgr_cls)
        instance.ensure_job_resources = AsyncMock(side_effect=RuntimeError("nats down"))
        images = self._make_images(4)
        job = self._make_job()

        result = queue_images_to_nats(job, images)

        self.assertFalse(result)
        self.assertEqual(instance.publish_task.await_count, 0)
