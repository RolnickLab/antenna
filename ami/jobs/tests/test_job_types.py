from cachalot.api import cachalot_disabled
from rest_framework import status
from rest_framework.test import APITestCase

from ami.base.serializers import reverse_with_params
from ami.jobs.models import Job, PostProcessingJob
from ami.main.models import Project, ProjectFeatureFlags, SourceImageCollection, TaxaList
from ami.ml.models import Algorithm, Pipeline
from ami.ml.models.project_pipeline_config import ProjectPipelineConfig
from ami.ml.post_processing.registry import POSTPROCESSING_TASKS
from ami.users.models import User
from ami.users.roles import BasicMember, MLDataManager


def types_url(project_id=None):
    params = {"project_id": project_id} if project_id is not None else {}
    return reverse_with_params("api:job-types", params=params)


def enable(project: Project, *flags: str) -> None:
    for flag in flags:
        setattr(project.feature_flags, flag, True)
    project.save()


class JobTypesTestBase(APITestCase):
    def setUp(self):
        owner = User.objects.create_user(email="owner@insectai.org")
        self.project = Project.objects.create(name="Job types project", owner=owner)
        self.other_project = Project.objects.create(name="Other project", owner=owner)
        self.basic = User.objects.create_user(email="basic@insectai.org")
        BasicMember.assign_user(self.basic, self.project)
        self.ml_manager = User.objects.create_user(email="ml@insectai.org")
        MLDataManager.assign_user(self.ml_manager, self.project)
        self.superuser = User.objects.create_user(email="super@insectai.org", is_staff=True, is_superuser=True)

    def get_types(self, user, project_id=None) -> dict:
        self.client.force_authenticate(user=user)
        response = self.client.get(types_url(self.project.pk if project_id is None else project_id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return {t["key"]: t for t in response.json()["results"]}


class TestJobTypesEndpoint(JobTypesTestBase):
    """GET /jobs/types/ lists what a project member may create, and only members may read it."""

    def test_only_project_members_may_read_it(self):
        self.client.force_authenticate(user=None)
        self.assertIn(
            self.client.get(types_url(self.project.pk)).status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
        self.client.force_authenticate(user=User.objects.create_user(email="outsider@insectai.org"))
        self.assertEqual(self.client.get(types_url(self.project.pk)).status_code, status.HTTP_403_FORBIDDEN)

    def test_project_id_is_required_and_validated(self):
        self.client.force_authenticate(user=self.basic)
        self.assertEqual(self.client.get(types_url()).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.get(types_url("abc")).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.get(types_url(999999)).status_code, status.HTTP_404_NOT_FOUND)

    def test_lists_creatable_types_with_the_users_permission(self):
        types = self.get_types(self.basic)
        # Exports are made from the exports page; post-processing has no method turned on yet.
        self.assertEqual(set(types), {"ml", "data_storage_sync", "populate_captures_collection", "regroup_events"})
        self.assertFalse(types["ml"]["allowed"])
        ml_schema = types["ml"]["config_schema"]
        self.assertEqual(ml_schema["required"], ["pipeline_id"])
        self.assertEqual(ml_schema["properties"]["source_image_collection_id"]["ami_entity"], "captures/collections")
        self.assertTrue(self.get_types(self.ml_manager)["ml"]["allowed"])

    def test_only_methods_turned_on_for_the_project_are_offered(self):
        enable(self.project, "class_masking")
        post_processing = self.get_types(self.ml_manager)["post_processing"]
        self.assertTrue(post_processing["allowed"])
        self.assertEqual([v["key"] for v in post_processing["variants"]], ["class_masking"])
        properties = post_processing["variants"][0]["config_schema"]["properties"]
        self.assertEqual(properties["taxa_list_id"]["title"], "Taxa list to keep")
        self.assertEqual(properties["source_image_collection_id"]["ami_entity"], "captures/collections")
        self.assertEqual(properties["occurrence_id"]["ami_widget"], "hidden")

    def test_query_count_does_not_grow_with_job_types(self):
        enable(self.project, "class_masking", "small_size_filter")
        self.client.force_authenticate(user=self.ml_manager)
        with cachalot_disabled():
            # Project, membership, user and group permissions, plus the request's savepoint pair.
            with self.assertNumQueries(6):
                response = self.client.get(types_url(self.project.pk))
        self.assertEqual(len(response.json()["results"]), 5)

    def test_every_task_names_a_real_feature_flag(self):
        for task in POSTPROCESSING_TASKS.values():
            self.assertIn(task.feature_flag, ProjectFeatureFlags.__fields__, task.key)


class TestCreateJobWithParams(JobTypesTestBase):
    """POST /jobs/ checks a job's settings against its job type before the job is stored."""

    def setUp(self):
        super().setUp()
        self.collection = SourceImageCollection.objects.create(name="Mine", project=self.project)
        self.other_collection = SourceImageCollection.objects.create(name="Theirs", project=self.other_project)
        self.taxa_list = TaxaList.objects.create(name="Keep")
        self.taxa_list.projects.add(self.project)
        self.algorithm = Algorithm.objects.create(name="Classifier", key="classifier")
        enable(self.project, "class_masking")

    def post_job(self, user, **body):
        self.client.force_authenticate(user=user)
        payload = {"name": "Job", "delay": 0, "project_id": self.project.pk, **body}
        return self.client.post(reverse_with_params("api:job-list"), payload, format="json")

    def post_masking(self, user, **config):
        config = {
            "source_image_collection_id": self.collection.pk,
            "taxa_list_id": self.taxa_list.pk,
            "algorithm_id": self.algorithm.pk,
            **config,
        }
        return self.post_job(user, job_type_key="post_processing", params={"task": "class_masking", "config": config})

    def test_ml_data_manager_starts_an_enabled_method_with_any_settings(self):
        response = self.post_masking(self.ml_manager, reweight=False)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.json())
        params = Job.objects.get(pk=response.json()["id"]).params
        self.assertEqual(params["task"], "class_masking")
        self.assertFalse(params["config"]["reweight"])
        self.assertIsNone(params["config"]["occurrence_id"])  # defaults are stored

    def test_basic_member_cannot_start_post_processing(self):
        self.assertEqual(self.post_masking(self.basic).status_code, status.HTTP_403_FORBIDDEN)

    def test_a_method_turned_off_for_the_project_is_refused(self):
        self.project.feature_flags.class_masking = False
        self.project.save()
        response = self.post_masking(self.superuser)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("not turned on", str(response.json()))

    def test_ids_from_another_project_are_refused(self):
        response = self.post_masking(self.ml_manager, source_image_collection_id=self.other_collection.pk)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("source_image_collection_id", str(response.json()))
        # Shared rows such as algorithms must at least exist.
        response = self.post_masking(self.ml_manager, algorithm_id=999999)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("algorithm_id", str(response.json()))
        response = self.post_job(
            self.superuser,
            job_type_key="populate_captures_collection",
            params={"config": {"source_image_collection_id": self.other_collection.pk}},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # A pipeline the project has not enabled (or has switched off) counts as another project's.
        pipeline = Pipeline.objects.create(name="Not enabled here")
        ProjectPipelineConfig.objects.create(project=self.project, pipeline=pipeline, enabled=False)
        response = self.post_job(
            self.superuser,
            job_type_key="ml",
            params={"config": {"pipeline_id": pipeline.pk, "source_image_collection_id": self.collection.pk}},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("pipeline_id", str(response.json()))

    def test_schema_errors_come_back_per_field(self):
        response = self.post_masking(self.ml_manager, taxa_list_id=None)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("taxa_list_id: none is not an allowed value", response.json()["params"]["config"])

    def test_platform_job_types_cannot_be_created_through_the_api(self):
        response = self.post_job(self.superuser, job_type_key="data_export")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("job_type_key", response.json())

    def test_inputs_are_stored_in_params_and_on_job_columns(self):
        response = self.post_job(
            self.superuser,
            job_type_key="populate_captures_collection",
            params={"config": {"source_image_collection_id": self.collection.pk}},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.json())
        job = Job.objects.get(pk=response.json()["id"])
        self.assertEqual(job.params, {"config": {"source_image_collection_id": self.collection.pk}})
        self.assertEqual(job.source_image_collection_id, self.collection.pk)

    def test_an_ml_job_needs_a_pipeline(self):
        response = self.post_job(self.superuser, job_type_key="ml", params={"config": {}})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("pipeline_id: field required", response.json()["params"]["config"])

    def test_an_ml_job_needs_something_to_process(self):
        pipeline = Pipeline.objects.create(name="Enabled here")
        pipeline.projects.add(self.project)
        response = self.post_job(self.superuser, job_type_key="ml", params={"config": {"pipeline_id": pipeline.pk}})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Choose a capture set to process.", response.json()["params"]["config"])

    def test_project_type_and_params_are_fixed_after_creation(self):
        job_id = self.post_masking(self.superuser).json()["id"]
        detail = reverse_with_params("api:job-detail", args=[job_id])
        self.client.patch(detail, {"params": {}}, format="json")
        self.assertEqual(Job.objects.get(pk=job_id).params["task"], "class_masking")
        # The viewset also scopes its lookup by a posted project_id, so a move may 404 first.
        response = self.client.patch(detail, {"project_id": self.other_project.pk}, format="json")
        self.assertIn(response.status_code, (status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND))
        self.assertEqual(Job.objects.get(pk=job_id).project_id, self.project.pk)
        response = self.client.patch(detail, {"job_type_key": "ml"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_turning_a_method_off_stops_members_re_running_its_jobs(self):
        job = Job.objects.get(pk=self.post_masking(self.ml_manager).json()["id"])
        self.assertTrue(job.check_custom_permission(self.ml_manager, "retry"))
        self.project.feature_flags.class_masking = False
        self.project.save()
        job.refresh_from_db()
        self.assertFalse(job.check_custom_permission(self.ml_manager, "retry"))
        self.assertTrue(job.check_custom_permission(self.superuser, "retry"))
        self.assertEqual(PostProcessingJob.enabled_tasks(self.project), {})
