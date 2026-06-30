"""Schema validation + admin-action wiring tests for class masking and rank rollup.

These are deliberately lightweight: they exercise the pydantic config contracts
and the admin trigger flow (intermediate page -> Job creation with the right
config payload) without the full project fixture. The masking maths is covered
in ``test_class_masking``.
"""
import pydantic
from django.contrib import admin as django_admin
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from ami.jobs.models import Job
from ami.main.models import (
    Classification,
    Deployment,
    Detection,
    Occurrence,
    Project,
    SourceImage,
    SourceImageCollection,
    TaxaList,
)
from ami.ml.models import Algorithm
from ami.ml.models.algorithm import AlgorithmTaskType
from ami.ml.post_processing.admin.class_masking_form import ClassMaskingActionForm
from ami.ml.post_processing.class_masking import ClassMaskingConfig
from ami.ml.post_processing.rank_rollup import RankRollupConfig
from ami.users.models import User


class TestClassMaskingConfig(TestCase):
    def test_collection_scope_is_valid(self):
        config = ClassMaskingConfig(source_image_collection_id=1, taxa_list_id=2, algorithm_id=3)
        self.assertEqual(config.source_image_collection_id, 1)
        self.assertIsNone(config.occurrence_id)

    def test_occurrence_scope_is_valid(self):
        config = ClassMaskingConfig(occurrence_id=5, taxa_list_id=2, algorithm_id=3)
        self.assertEqual(config.occurrence_id, 5)

    def test_both_scopes_is_invalid(self):
        with self.assertRaises(pydantic.ValidationError):
            ClassMaskingConfig(source_image_collection_id=1, occurrence_id=5, taxa_list_id=2, algorithm_id=3)

    def test_no_scope_is_invalid(self):
        with self.assertRaises(pydantic.ValidationError):
            ClassMaskingConfig(taxa_list_id=2, algorithm_id=3)

    def test_missing_required_fields_is_invalid(self):
        with self.assertRaises(pydantic.ValidationError):
            ClassMaskingConfig(source_image_collection_id=1)  # no taxa_list_id / algorithm_id

    def test_extra_field_is_forbidden(self):
        with self.assertRaises(pydantic.ValidationError):
            ClassMaskingConfig(source_image_collection_id=1, taxa_list_id=2, algorithm_id=3, bogus=1)


class TestRankRollupConfig(TestCase):
    def test_defaults_applied(self):
        config = RankRollupConfig(source_image_collection_id=1)
        self.assertEqual(config.thresholds["SPECIES"], 0.8)
        self.assertEqual(config.rollup_order, ["SPECIES", "GENUS", "FAMILY"])

    def test_threshold_out_of_range_is_invalid(self):
        with self.assertRaises(pydantic.ValidationError):
            RankRollupConfig(source_image_collection_id=1, thresholds={"SPECIES": 1.5})

    def test_threshold_and_order_are_uppercased(self):
        config = RankRollupConfig(
            source_image_collection_id=1, thresholds={"species": 0.7}, rollup_order=["species", "genus"]
        )
        self.assertIn("SPECIES", config.thresholds)
        self.assertEqual(config.rollup_order, ["SPECIES", "GENUS"])


class _PostProcessingAdminCase(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.superuser = User.objects.create_superuser(email=f"ppadmin+{cls.__name__}@example.com", password="x")
        cls.project = Project.objects.create(name=f"PP admin test ({cls.__name__})")
        cls.collection = SourceImageCollection.objects.create(project=cls.project, name="PP admin collection")
        cls.occurrence = Occurrence.objects.create(project=cls.project)
        cls.taxa_list = TaxaList.objects.create(name="PP admin taxa list")
        cls.algorithm = Algorithm.objects.create(
            name="PP admin classifier", task_type=AlgorithmTaskType.CLASSIFICATION.value
        )
        # Wire the classifier to both scopes (the collection's image and the
        # occurrence) so the class-mask form offers it — it only lists algorithms
        # that actually produced classifications within the selection.
        cls.deployment = Deployment.objects.create(project=cls.project, name="PP admin dep")
        source_image = SourceImage.objects.create(deployment=cls.deployment, project=cls.project, path="pp-admin.jpg")
        cls.collection.images.add(source_image)
        detection = Detection.objects.create(source_image=source_image, bbox=[0, 0, 1, 1], occurrence=cls.occurrence)
        Classification.objects.create(detection=detection, algorithm=cls.algorithm, timestamp=timezone.now())

    def setUp(self) -> None:
        self.client = Client()
        self.client.force_login(self.superuser)


class TestClassMaskingAdmin(_PostProcessingAdminCase):
    def _post_collection(self, data: dict):
        url = reverse("admin:main_sourceimagecollection_changelist")
        return self.client.post(
            url,
            data={
                "action": "run_class_masking",
                django_admin.helpers.ACTION_CHECKBOX_NAME: [str(self.collection.pk)],
                **data,
            },
        )

    def test_renders_intermediate_page_without_confirm(self):
        response = self._post_collection({})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Run Class masking", response.content)
        self.assertIn(b'name="taxa_list_id"', response.content)
        self.assertIn(b'name="algorithm_id"', response.content)
        self.assertEqual(Job.objects.filter(project=self.project).count(), 0)

    def test_valid_post_creates_collection_scoped_job(self):
        response = self._post_collection(
            {"confirm": "yes", "taxa_list_id": str(self.taxa_list.pk), "algorithm_id": str(self.algorithm.pk)}
        )
        self.assertEqual(response.status_code, 302)
        job = Job.objects.get(project=self.project, job_type_key="post_processing")
        self.assertEqual(job.params["task"], "class_masking")
        self.assertEqual(job.params["config"]["source_image_collection_id"], self.collection.pk)
        self.assertEqual(job.params["config"]["taxa_list_id"], self.taxa_list.pk)
        self.assertEqual(job.params["config"]["algorithm_id"], self.algorithm.pk)
        self.assertIsNone(job.params["config"].get("occurrence_id"))

    def test_valid_post_on_occurrence_creates_occurrence_scoped_job(self):
        url = reverse("admin:main_occurrence_changelist")
        response = self.client.post(
            url,
            data={
                "action": "run_class_masking",
                django_admin.helpers.ACTION_CHECKBOX_NAME: [str(self.occurrence.pk)],
                "confirm": "yes",
                "taxa_list_id": str(self.taxa_list.pk),
                "algorithm_id": str(self.algorithm.pk),
            },
        )
        self.assertEqual(response.status_code, 302)
        job = Job.objects.get(project=self.project, job_type_key="post_processing")
        self.assertEqual(job.params["task"], "class_masking")
        self.assertEqual(job.params["config"]["occurrence_id"], self.occurrence.pk)
        self.assertIsNone(job.params["config"].get("source_image_collection_id"))


class TestRankRollupAdmin(_PostProcessingAdminCase):
    def test_valid_post_creates_rank_rollup_job_with_defaults(self):
        url = reverse("admin:main_sourceimagecollection_changelist")
        response = self.client.post(
            url,
            data={
                "action": "run_rank_rollup",
                django_admin.helpers.ACTION_CHECKBOX_NAME: [str(self.collection.pk)],
                "confirm": "yes",
            },
        )
        self.assertEqual(response.status_code, 302)
        job = Job.objects.get(project=self.project, job_type_key="post_processing")
        self.assertEqual(job.params["task"], "rank_rollup")
        self.assertEqual(job.params["config"]["source_image_collection_id"], self.collection.pk)
        self.assertEqual(job.params["config"]["thresholds"]["SPECIES"], 0.8)


class TestClassMaskingFormScopeFiltering(TestCase):
    """The class-mask form offers only classifiers that actually produced
    classifications within the selected scope, so an operator cannot pick an
    algorithm whose masking would be a no-op for the chosen occurrence."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.project = Project.objects.create(name="CM scope filter project")
        cls.deployment = Deployment.objects.create(project=cls.project, name="dep")
        cls.source_image = SourceImage.objects.create(
            deployment=cls.deployment, project=cls.project, path="cm-scope.jpg"
        )
        cls.used = Algorithm.objects.create(name="used classifier", task_type=AlgorithmTaskType.CLASSIFICATION.value)
        cls.unused = Algorithm.objects.create(
            name="unused classifier", task_type=AlgorithmTaskType.CLASSIFICATION.value
        )

        cls.occurrence = Occurrence.objects.create(project=cls.project, deployment=cls.deployment)
        detection = Detection.objects.create(
            source_image=cls.source_image, bbox=[0, 0, 1, 1], occurrence=cls.occurrence
        )
        Classification.objects.create(detection=detection, algorithm=cls.used, timestamp=timezone.now())

    def test_form_offers_only_algorithms_used_on_the_occurrence(self):
        form = ClassMaskingActionForm(scope_queryset=Occurrence.objects.filter(pk=self.occurrence.pk))
        offered = set(form.fields["algorithm_id"].queryset.values_list("pk", flat=True))
        self.assertEqual(offered, {self.used.pk})

    def test_form_without_scope_offers_all_classifiers(self):
        form = ClassMaskingActionForm()
        offered = set(form.fields["algorithm_id"].queryset.values_list("pk", flat=True))
        self.assertIn(self.used.pk, offered)
        self.assertIn(self.unused.pk, offered)

    def test_collection_scope_offers_all_classifiers(self):
        """A collection scope intentionally keeps the full classifier list rather
        than narrowing to the classifiers used in the collection. The narrowing
        lookup is an unbounded DISTINCT over every classification in the
        collection, which can time out while rendering the form on a large
        collection. This pins that the collection path stays unfiltered so the
        expensive filter is not re-added there by mistake."""
        collection = SourceImageCollection.objects.create(project=self.project, name="scope coll")
        collection.images.add(self.source_image)
        form = ClassMaskingActionForm(scope_queryset=SourceImageCollection.objects.filter(pk=collection.pk))
        offered = set(form.fields["algorithm_id"].queryset.values_list("pk", flat=True))
        self.assertIn(self.used.pk, offered)
        self.assertIn(self.unused.pk, offered)
