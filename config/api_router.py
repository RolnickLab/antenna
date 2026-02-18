from django.urls import path
from django.urls.conf import include
from djoser.views import UserViewSet
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers

from ami.exports import views as export_views
from ami.jobs import views as job_views
from ami.labelstudio import views as labelstudio_views
from ami.main.api import views
from ami.ml import views as ml_views
from ami.users.api.views import RolesAPIView, UserProjectMembershipViewSet

router = DefaultRouter()

router.register(r"users", UserViewSet)
router.register(r"storage", views.StorageSourceViewSet)
router.register(r"projects", views.ProjectViewSet)
# NESTED: /projects/{project_id}/members/
projects_router = routers.NestedDefaultRouter(router, r"projects", lookup="project")
projects_router.register(
    r"members",
    UserProjectMembershipViewSet,
    basename="project-members",
)
projects_router.register(
    r"pipelines",
    ml_views.ProjectPipelineViewSet,
    basename="project-pipelines",
)

router.register(r"deployments/devices", views.DeviceViewSet)
router.register(r"deployments/sites", views.SiteViewSet)
router.register(r"deployments", views.DeploymentViewSet)
router.register(r"events", views.EventViewSet)
router.register(r"exports", export_views.ExportViewSet)
router.register(r"captures/collections", views.SourceImageCollectionViewSet)
router.register(r"captures/upload", views.SourceImageUploadViewSet)
router.register(r"captures", views.SourceImageViewSet)
router.register(r"detections", views.DetectionViewSet)
router.register(r"occurrences", views.OccurrenceViewSet)
router.register(r"taxa/lists", views.TaxaListViewSet)
router.register(r"taxa", views.TaxonViewSet)
router.register(r"tags", views.TagViewSet)
router.register(r"ml/algorithms", ml_views.AlgorithmViewSet)
router.register(r"ml/labels", ml_views.AlgorithmCategoryMapViewSet)
router.register(r"ml/pipelines", ml_views.PipelineViewSet)
router.register(r"ml/processing_services", ml_views.ProcessingServiceViewSet)
router.register(r"classifications", views.ClassificationViewSet)
router.register(r"identifications", views.IdentificationViewSet)
router.register(r"jobs", job_views.JobViewSet)
router.register(r"pages", views.PageViewSet)
router.register(r"exports", export_views.ExportViewSet)
router.register(
    r"labelstudio/captures", labelstudio_views.LabelStudioSourceImageViewSet, basename="labelstudio-captures"
)
router.register(
    r"labelstudio/detections", labelstudio_views.LabelStudioDetectionViewSet, basename="labelstudio-detections"
)
router.register(
    r"labelstudio/occurrences", labelstudio_views.LabelStudioOccurrenceViewSet, basename="labelstudio-occurrences"
)
router.register(r"labelstudio/hooks", labelstudio_views.LabelStudioHooksViewSet, basename="labelstudio-hooks")
router.register(r"labelstudio/config", labelstudio_views.LabelStudioConfigViewSet, basename="labelstudio-config")
# Wire up our API using automatic URL routing.

app_name = "api"  # this breaks the automatic routing with viewsets & hyperlinked serializers

urlpatterns = [
    path("auth/", include("djoser.urls.authtoken")),
    path("status/summary/", views.SummaryView.as_view(), name="status-summary"),
    path("status/storage/", views.StorageStatus.as_view(), name="status-storage"),
    path(
        "users/roles/",
        RolesAPIView.as_view(),
        name="user-roles",
    ),
]


urlpatterns += router.urls + projects_router.urls
#
