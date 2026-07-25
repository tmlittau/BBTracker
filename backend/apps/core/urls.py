from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    CheckinReportView,
    DashboardTodayView,
    DataExportView,
    HealthzView,
    PhaseAdjustmentViewSet,
    PhaseViewSet,
    ReplicaBackupView,
    ReplicaBootstrapView,
    WeeklyCheckInView,
)

router = DefaultRouter()
router.register("phases", PhaseViewSet, basename="phase")
router.register("phase-adjustments", PhaseAdjustmentViewSet, basename="phaseadjustment")

urlpatterns = [
    path("healthz/", HealthzView.as_view(), name="healthz"),
    path("dashboard/today/", DashboardTodayView.as_view(), name="dashboard-today"),
    path("checkin/weekly/", WeeklyCheckInView.as_view(), name="checkin-weekly"),
    path("sync/bootstrap/", ReplicaBootstrapView.as_view(), name="replica-bootstrap"),
    path("sync/backup/", ReplicaBackupView.as_view(), name="replica-backup"),
    path("export/", DataExportView.as_view(), name="data-export"),
    path("report/checkin/", CheckinReportView.as_view(), name="checkin-report"),
    *router.urls,
]
