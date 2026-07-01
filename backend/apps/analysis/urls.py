from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    BodyAnalysisView,
    BodyMeasurementViewSet,
    MetricCatalogView,
    SeriesOverlayView,
)

router = DefaultRouter()
router.register("measurements", BodyMeasurementViewSet, basename="bodymeasurement")

urlpatterns = [
    path("body/", BodyAnalysisView.as_view(), name="body-analysis"),
    path("metrics/", MetricCatalogView.as_view(), name="analysis-metrics"),
    path("series/", SeriesOverlayView.as_view(), name="analysis-series"),
    *router.urls,
]
