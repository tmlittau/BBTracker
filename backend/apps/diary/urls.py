from rest_framework.routers import DefaultRouter

from .views import CheckInViewSet, PoseViewSet, ProgressPhotoViewSet

router = DefaultRouter()
router.register("poses", PoseViewSet, basename="pose")
router.register("check-ins", CheckInViewSet, basename="checkin")
router.register("photos", ProgressPhotoViewSet, basename="progressphoto")

urlpatterns = router.urls
