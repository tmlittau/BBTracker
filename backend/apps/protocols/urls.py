from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    BloodMarkerViewSet,
    BloodPressureLogViewSet,
    BloodResultViewSet,
    CompoundPlotView,
    CompoundViewSet,
    DoseLogViewSet,
    InjectionSiteViewSet,
    PhaseLevelsView,
    ProtocolItemViewSet,
    ProtocolViewSet,
    SupplementViewSet,
    VialViewSet,
    WeekPrepView,
)

router = DefaultRouter()
router.register("compounds", CompoundViewSet, basename="compound")
router.register("supplements", SupplementViewSet, basename="supplement")
router.register("injection-sites", InjectionSiteViewSet, basename="injectionsite")
router.register("blood-markers", BloodMarkerViewSet, basename="bloodmarker")
router.register("protocols", ProtocolViewSet, basename="protocol")
router.register("protocol-items", ProtocolItemViewSet, basename="protocolitem")
router.register("dose-logs", DoseLogViewSet, basename="doselog")
router.register("vials", VialViewSet, basename="vial")
router.register("blood-results", BloodResultViewSet, basename="bloodresult")
router.register("bp-logs", BloodPressureLogViewSet, basename="bploh")

urlpatterns = [
    path("plot/", CompoundPlotView.as_view(), name="compound-plot"),
    path("week-prep/", WeekPrepView.as_view(), name="week-prep"),
    path("phase-levels/", PhaseLevelsView.as_view(), name="phase-levels"),
    *router.urls,
]
