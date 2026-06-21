from datetime import date as date_cls

from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.viewsets import OwnerScopedViewSet

from .export import build_export
from .models import Phase, PhaseAdjustment
from .serializers import (
    DashboardTodaySerializer,
    PhaseAdjustmentSerializer,
    PhaseSerializer,
    WeeklyCheckInSerializer,
)
from .services import dashboard_today, weekly_checkin


class HealthzView(APIView):
    """Liveness probe — open, no auth."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=["core"],
        responses=inline_serializer(name="Healthz", fields={"status": serializers.CharField()}),
    )
    def get(self, request):
        return Response({"status": "ok"})


def _parse_date(request, param):
    raw = request.query_params.get(param)
    if not raw:
        return date_cls.today()
    try:
        return date_cls.fromisoformat(raw)
    except ValueError as exc:
        raise ValidationError({param: "must be ISO format YYYY-MM-DD"}) from exc


@extend_schema(tags=["core"])
class PhaseViewSet(viewsets.ModelViewSet):
    """The periodization timeline. Owner-scoped; a phase's prescription lives in a
    dated PhaseAdjustment timeline (see PhaseAdjustmentViewSet)."""

    serializer_class = PhaseSerializer

    def get_queryset(self):
        return Phase.objects.filter(owner=self.request.user).prefetch_related(
            "adjustments__nutrition_target", "adjustments__program", "adjustments__protocol"
        )

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


@extend_schema(tags=["core"])
class PhaseAdjustmentViewSet(OwnerScopedViewSet):
    """Dated prescription changes within a phase. Owner-scoped via the phase; any
    linked target/program/protocol must belong to the same user."""

    queryset = PhaseAdjustment.objects.all()
    serializer_class = PhaseAdjustmentSerializer
    owner_path = "phase__owner"
    parent_checks = [("phase", Phase, "owner")]

    def get_queryset(self):
        return super().get_queryset().select_related(
            "nutrition_target", "program", "protocol"
        )

    def _check_links(self, serializer):
        for field in ("nutrition_target", "program", "protocol"):
            obj = serializer.validated_data.get(field)
            if obj is not None and obj.owner_id != self.request.user.id:
                raise PermissionDenied(f"That {field} does not belong to you.")

    def perform_create(self, serializer):
        self._validate_parents(serializer)
        self._check_links(serializer)
        serializer.save()

    def perform_update(self, serializer):
        self._validate_parents(serializer)
        self._check_links(serializer)
        serializer.save()


@extend_schema(
    tags=["core"],
    parameters=[OpenApiParameter("date", str, description="ISO date (default today)")],
    responses=DashboardTodaySerializer,
)
class DashboardTodayView(APIView):
    """Unified 'today' across all five domains + the current phase."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(dashboard_today(request.user, _parse_date(request, "date")))


@extend_schema(
    tags=["core"],
    parameters=[
        OpenApiParameter("end", str, description="ISO end date (default today); 7-day window")
    ],
    responses=WeeklyCheckInSerializer,
)
class WeeklyCheckInView(APIView):
    """Auto-generated weekly check-in report — the self-coaching payload."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(weekly_checkin(request.user, _parse_date(request, "end")))


class DataExportView(APIView):
    """Download a zip of all your data (data.json + CSVs + progress photos)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["core"],
        parameters=[OpenApiParameter("photos", int, description="0 to omit photo files.")],
        responses={(200, "application/zip"): OpenApiTypes.BINARY},
    )
    def get(self, request):
        include_photos = request.query_params.get("photos", "1") != "0"
        filename, buf = build_export(request.user, include_photos)
        resp = HttpResponse(buf.getvalue(), content_type="application/zip")
        resp["Content-Disposition"] = f'attachment; filename="{filename}"'
        return resp
