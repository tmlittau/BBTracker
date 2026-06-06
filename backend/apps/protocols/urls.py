from rest_framework.routers import DefaultRouter

from .views import (
    BloodMarkerViewSet,
    BloodPressureLogViewSet,
    BloodResultViewSet,
    CompoundViewSet,
    DoseLogViewSet,
    InjectionSiteViewSet,
    ProtocolItemViewSet,
    ProtocolViewSet,
    SupplementViewSet,
    VialViewSet,
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

urlpatterns = router.urls
