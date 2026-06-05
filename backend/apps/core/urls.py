from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    DashboardTodayView,
    HealthzView,
    PhaseAdjustmentViewSet,
    PhaseViewSet,
    WeeklyCheckInView,
)

router = DefaultRouter()
router.register("phases", PhaseViewSet, basename="phase")
router.register("phase-adjustments", PhaseAdjustmentViewSet, basename="phaseadjustment")

urlpatterns = [
    path("healthz/", HealthzView.as_view(), name="healthz"),
    path("dashboard/today/", DashboardTodayView.as_view(), name="dashboard-today"),
    path("checkin/weekly/", WeeklyCheckInView.as_view(), name="checkin-weekly"),
    *router.urls,
]
