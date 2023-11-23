from django.conf import settings
from django.urls import path
from django.urls.conf import include
from djoser.views import UserViewSet
from rest_framework.routers import DefaultRouter, SimpleRouter

from ami.jobs.views import JobViewSet
from ami.labelstudio import views as labelstudio_views
from ami.main.api import views

if settings.DEBUG:
    router = DefaultRouter()
else:
    router = SimpleRouter()

router.register(r"users", UserViewSet)
router.register(r"storage", views.StorageSourceViewSet)
router.register(r"projects", views.ProjectViewSet)
router.register(r"deployments/devices", views.DeviceViewSet)
router.register(r"deployments/sites", views.SiteViewSet)
router.register(r"deployments", views.DeploymentViewSet)
router.register(r"events", views.EventViewSet)
router.register(r"captures/collections", views.SourceImageCollectionViewSet)
router.register(r"captures/upload", views.SourceImageUploadViewSet)
router.register(r"captures", views.SourceImageViewSet)
router.register(r"detections", views.DetectionViewSet)
router.register(r"occurrences", views.OccurrenceViewSet)
router.register(r"taxa", views.TaxonViewSet)
router.register(r"ml/algorithms", views.AlgorithmViewSet)
router.register(r"ml/pipelines", views.PipelineViewSet)
router.register(r"classifications", views.ClassificationViewSet)
router.register(r"identifications", views.IdentificationViewSet)
router.register(r"jobs", JobViewSet)
router.register(r"pages", views.PageViewSet)
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
]


urlpatterns += router.urls
