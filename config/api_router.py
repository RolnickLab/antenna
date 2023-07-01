from django.conf import settings
from rest_framework.routers import DefaultRouter, SimpleRouter

from ami.main.api import views
from ami.users.api.views import UserViewSet

if settings.DEBUG:
    router = DefaultRouter()
else:
    router = SimpleRouter()

router.register("users", UserViewSet)
router.register(r"projects", views.ProjectViewSet)
router.register(r"deployments", views.DeploymentViewSet)
router.register(r"events", views.EventViewSet)
router.register(r"captures", views.SourceImageViewSet)
router.register(r"detections", views.DetectionViewSet)
router.register(r"occurrences", views.OccurrenceViewSet)
router.register(r"taxa", views.TaxonViewSet)
router.register(r"models", views.AlgorithmViewSet)

# Wire up our API using automatic URL routing.


app_name = "api"
urlpatterns = router.urls
