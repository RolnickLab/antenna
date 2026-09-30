from cachalot.api import cachalot_disabled
from rest_framework import status
from rest_framework.test import APITestCase

from ami.base.serializers import reverse_with_params
from ami.jobs.descriptors import _sentence_case, describe_docstring, normalize_config_schema, strip_markup
from ami.jobs.models import Job, PostProcessingJob, RegroupEventsJob
from ami.main.models import Occurrence, Project, SourceImageCollection, TaxaList
from ami.ml.models import Algorithm
from ami.ml.post_processing import registry
from ami.ml.post_processing.class_masking import ClassMaskingConfig
from ami.users.models import User
from ami.users.roles import BasicMember, MLDataManager


def types_url(project_id=None):
    params = {"project_id": project_id} if project_id is not None else {}
    return reverse_with_params("api:job-types", params=params)


class TestJobTypesEndpoint(APITestCase):
    """GET /jobs/types/ describes the job types a project member may create, and nobody else may read it."""

    def setUp(self):
        self.owner = User.objects.create_user(email="owner@insectai.org")
        self.project = Project.objects.create(name="Job types project", owner=self.owner)
        self.other_project = Project.objects.create(name="Other project", owner=self.owner)
        self.basic = User.objects.create_user(email="basic@insectai.org")
        BasicMember.assign_user(self.basic, self.project)
        self.ml_manager = User.objects.create_user(email="ml@insectai.org")
        MLDataManager.assign_user(self.ml_manager, self.project)
        self.outsider = User.objects.create_user(email="outsider@insectai.org")
        self.superuser = User.objects.create_user(email="super@insectai.org", is_staff=True, is_superuser=True)

    def get_types(self, user, project_id=None):
        self.client.force_authenticate(user=user)
        return self.client.get(types_url(self.project.pk if project_id is None else project_id))

    def test_anonymous_is_refused_before_the_project_is_read(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(types_url(self.project.pk))
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_non_member_is_refused(self):
        response = self.get_types(self.outsider)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_project_id_is_required_and_validated(self):
        self.client.force_authenticate(user=self.basic)
        self.assertEqual(self.client.get(types_url()).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.get(types_url("abc")).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.get(types_url(999999)).status_code, status.HTTP_404_NOT_FOUND)

    def test_member_sees_creatable_types_with_permission_resolved(self):
        response = self.get_types(self.basic)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        by_key = {t["key"]: t for t in response.json()["results"]}
        # Exports are created from the exports page, never offered here.
        self.assertNotIn("data_export", by_key)
        self.assertNotIn("unknown", by_key)
        self.assertEqual(
            set(by_key),
            {"ml", "data_storage_sync", "populate_captures_collection", "post_processing", "regroup_events"},
        )
        # A basic member may create jobs but not run a pipeline over a capture set.
        self.assertFalse(by_key["ml"]["allowed"])
        self.assertEqual([s["field"] for s in by_key["ml"]["scope"]], ["pipeline_id", "source_image_collection_id"])
        self.assertTrue(by_key["ml"]["description"])

    def test_ml_data_manager_may_run_ml_jobs(self):
        by_key = {t["key"]: t for t in self.get_types(self.ml_manager).json()["results"]}
        self.assertTrue(by_key["ml"]["allowed"])

    def test_staff_only_tasks_are_disabled_and_their_settings_hidden_for_members(self):
        by_key = {t["key"]: t for t in self.get_types(self.ml_manager).json()["results"]}
        variants = {v["key"]: v for v in by_key["post_processing"]["variants"]}
        masking = variants["class_masking"]
        self.assertFalse(masking["allowed"])
        self.assertEqual(masking["config_schema"]["properties"], {})

    def test_superuser_sees_every_post_processing_setting_except_scope(self):
        by_key = {t["key"]: t for t in self.get_types(self.superuser).json()["results"]}
        post_processing = by_key["post_processing"]
        self.assertEqual(post_processing["variant_key"], "task")
        masking = {v["key"]: v for v in post_processing["variants"]}["class_masking"]
        self.assertTrue(masking["allowed"])
        self.assertEqual([s["field"] for s in masking["scope"]], ["source_image_collection_id"])
        self.assertEqual(masking["scope"][0]["target"], "config")
        properties = masking["config_schema"]["properties"]
        self.assertEqual(set(properties), {"taxa_list_id", "algorithm_id", "reweight"})
        self.assertEqual(properties["taxa_list_id"]["title"], "Taxa list to keep")
        self.assertEqual(properties["algorithm_id"]["ami_entity"], "ml/algorithms")
        self.assertTrue(masking["description"].startswith("Masks out classes"))

    def test_superuser_sees_which_settings_members_cannot_change(self):
        original = dict(registry.MEMBER_POST_PROCESSING_TASKS)
        registry.MEMBER_POST_PROCESSING_TASKS["class_masking"] = frozenset(
            {"source_image_collection_id", "taxa_list_id", "algorithm_id"}
        )
        try:
            superuser_types = {t["key"]: t for t in self.get_types(self.superuser).json()["results"]}
            member_types = {t["key"]: t for t in self.get_types(self.ml_manager).json()["results"]}
        finally:
            registry.MEMBER_POST_PROCESSING_TASKS.clear()
            registry.MEMBER_POST_PROCESSING_TASKS.update(original)
        masking = {v["key"]: v for v in superuser_types["post_processing"]["variants"]}["class_masking"]
        properties = masking["config_schema"]["properties"]
        self.assertTrue(properties["reweight"]["ami_staff_only"])
        self.assertNotIn("ami_staff_only", properties["taxa_list_id"])
        member_masking = {v["key"]: v for v in member_types["post_processing"]["variants"]}["class_masking"]
        self.assertEqual(set(member_masking["config_schema"]["properties"]), {"taxa_list_id", "algorithm_id"})

    def test_query_count_does_not_grow_with_job_types(self):
        self.client.force_authenticate(user=self.ml_manager)
        with cachalot_disabled():
            # Project, membership, user and group permissions, plus the request's savepoint pair:
            # fixed however many job types and post-processing tasks are listed.
            with self.assertNumQueries(6):
                response = self.client.get(types_url(self.project.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.json()["results"]), 3)


class TestDescriptionText(APITestCase):
    def test_generated_labels_keep_acronyms(self):
        self.assertEqual(_sentence_case("iou_weight"), "IoU weight")
        self.assertEqual(_sentence_case("stationary_min_iou"), "Stationary min IoU")
        self.assertEqual(_sentence_case("species_label_algorithm_id"), "Species label algorithm")

    def test_docstring_markup_is_stripped(self):
        self.assertEqual(strip_markup("uses ``a_b`` and :class:`Foo` and `x`"), "uses a_b and Foo and x")
        self.assertNotIn("`", describe_docstring(RegroupEventsJob))


class TestSchemaNormalizer(APITestCase):
    def test_scope_fields_are_dropped_and_titles_filled(self):
        schema = normalize_config_schema(ClassMaskingConfig, exclude={"source_image_collection_id", "occurrence_id"})
        self.assertNotIn("source_image_collection_id", schema["properties"])
        self.assertEqual(schema["required"], ["taxa_list_id", "algorithm_id"])
        self.assertEqual(schema["x-ami-schema-version"], 1)


class TestCreateJobWithParams(APITestCase):
    """POST /jobs/ checks a job's settings against its job type before the job is stored."""

    def setUp(self):
        self.owner = User.objects.create_user(email="owner@insectai.org")
        self.project = Project.objects.create(name="Params project", owner=self.owner)
        self.other_project = Project.objects.create(name="Other params project", owner=self.owner)
        self.collection = SourceImageCollection.objects.create(name="Mine", project=self.project)
        self.other_collection = SourceImageCollection.objects.create(name="Theirs", project=self.other_project)
        self.taxa_list = TaxaList.objects.create(name="Keep")
        self.taxa_list.projects.add(self.project)
        self.algorithm = Algorithm.objects.create(name="Classifier", key="classifier")
        self.superuser = User.objects.create_user(email="super@insectai.org", is_staff=True, is_superuser=True)
        self.ml_manager = User.objects.create_user(email="ml@insectai.org")
        MLDataManager.assign_user(self.ml_manager, self.project)

    def post_job(self, user, **body):
        self.client.force_authenticate(user=user)
        payload = {"name": "Job", "delay": 0, "project_id": self.project.pk, **body}
        return self.client.post(reverse_with_params("api:job-list"), payload, format="json")

    def masking_params(self, collection_id):
        return {
            "task": "class_masking",
            "config": {
                "source_image_collection_id": collection_id,
                "taxa_list_id": self.taxa_list.pk,
                "algorithm_id": self.algorithm.pk,
            },
        }

    def test_superuser_creates_a_post_processing_job_with_defaults_filled(self):
        response = self.post_job(
            self.superuser, job_type_key="post_processing", params=self.masking_params(self.collection.pk)
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.json())
        job = Job.objects.get(pk=response.json()["id"])
        self.assertEqual(job.params["task"], "class_masking")
        self.assertTrue(job.params["config"]["reweight"])
        self.assertIsNone(job.params["config"]["occurrence_id"])

    def test_capture_set_from_another_project_is_refused(self):
        response = self.post_job(
            self.superuser, job_type_key="post_processing", params=self.masking_params(self.other_collection.pk)
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("source_image_collection_id", str(response.json()))

    def test_occurrence_from_another_project_is_refused(self):
        occurrence = Occurrence.objects.create(project=self.other_project)
        params = self.masking_params(None)
        params["config"]["occurrence_id"] = occurrence.pk
        del params["config"]["source_image_collection_id"]
        response = self.post_job(self.superuser, job_type_key="post_processing", params=params)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_schema_errors_come_back_per_field(self):
        params = self.masking_params(self.collection.pk)
        del params["config"]["taxa_list_id"]
        response = self.post_job(self.superuser, job_type_key="post_processing", params=params)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("taxa_list_id: field required", response.json()["params"]["config"])

    def test_member_cannot_start_a_staff_only_task(self):
        response = self.post_job(
            self.ml_manager, job_type_key="post_processing", params=self.masking_params(self.collection.pk)
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("staff", str(response.json()))

    def test_member_on_the_allowlist_still_cannot_change_staff_only_settings(self):
        original = dict(registry.MEMBER_POST_PROCESSING_TASKS)
        registry.MEMBER_POST_PROCESSING_TASKS["class_masking"] = frozenset(
            {"source_image_collection_id", "taxa_list_id", "algorithm_id"}
        )
        try:
            params = self.masking_params(self.collection.pk)
            params["config"]["reweight"] = False
            response = self.post_job(self.ml_manager, job_type_key="post_processing", params=params)
        finally:
            registry.MEMBER_POST_PROCESSING_TASKS.clear()
            registry.MEMBER_POST_PROCESSING_TASKS.update(original)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("reweight: Only staff", str(response.json()))

    def test_platform_job_types_cannot_be_created_through_the_api(self):
        response = self.post_job(self.superuser, job_type_key="data_export")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("job_type_key", response.json())

    def test_params_are_ignored_for_job_types_without_settings(self):
        response = self.post_job(
            self.superuser,
            job_type_key="populate_captures_collection",
            source_image_collection_id=self.collection.pk,
            params={"anything": 1},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.json())
        self.assertFalse(Job.objects.get(pk=response.json()["id"]).params)

    def test_capture_set_column_from_another_project_is_refused(self):
        response = self.post_job(
            self.superuser,
            job_type_key="populate_captures_collection",
            source_image_collection_id=self.other_collection.pk,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("source_image_collection_id", response.json())

    def test_params_cannot_be_changed_after_creation(self):
        response = self.post_job(
            self.superuser, job_type_key="post_processing", params=self.masking_params(self.collection.pk)
        )
        job_id = response.json()["id"]
        detail = reverse_with_params("api:job-detail", args=[job_id])
        self.client.patch(detail, {"params": {"task": "small_size_filter", "config": {}}}, format="json")
        self.assertEqual(Job.objects.get(pk=job_id).params["task"], "class_masking")

    def test_post_processing_scope_is_described_by_the_task(self):
        scope = PostProcessingJob.task_scope(registry.POSTPROCESSING_TASKS["small_size_filter"])
        self.assertEqual([f.field for f in scope], ["source_image_collection_id"])
