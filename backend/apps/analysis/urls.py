from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import BodyAnalysisView, BodyMeasurementViewSet

router = DefaultRouter()
router.register("measurements", BodyMeasurementViewSet, basename="bodymeasurement")

urlpatterns = [
    path("body/", BodyAnalysisView.as_view(), name="body-analysis"),
    *router.urls,
]
