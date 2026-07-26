from datetime import date as date_cls
from datetime import timedelta

from django.db import transaction
from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.coaching.access import EffectiveOwnerMixin
from apps.core.viewsets import OwnerScopedViewSet

from .export import build_export
from .models import Phase, PhaseAdjustment, ReplicaBackup
from .replica import apply_replica_health, apply_replica_settings, build_replica_snapshot
from .report import ALL_SECTIONS, build_checkin_report_pdf
from .serializers import (
    DashboardTodaySerializer,
    PhaseAdjustmentSerializer,
    PhaseSerializer,
    WeeklyCheckInSerializer,
)
from .services import dashboard_today, seed_initial_adjustment, weekly_checkin


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
class PhaseViewSet(EffectiveOwnerMixin, viewsets.ModelViewSet):
    """The periodization timeline. Owner-scoped; a phase's prescription lives in a
    dated PhaseAdjustment timeline (see PhaseAdjustmentViewSet)."""

    serializer_class = PhaseSerializer
    prescription_write = True  # a coach may edit a client's phases

    def get_queryset(self):
        return Phase.objects.filter(owner=self.effective_owner).prefetch_related(
            "adjustments__nutrition_target", "adjustments__program", "adjustments__protocol"
        )

    def perform_create(self, serializer):
        # Owner is the effective owner so a coach creating a phase assigns it to the client.
        phase = serializer.save(owner=self.effective_owner)
        # Seed the phase's initial adjustment from the active plan so its timeline is
        # well-formed from the start (history survives later adjustments).
        seed_initial_adjustment(phase)


@extend_schema(tags=["core"])
class PhaseAdjustmentViewSet(OwnerScopedViewSet):
    """Dated prescription changes within a phase. Owner-scoped via the phase; any
    linked target/program/protocol must belong to the same user."""

    queryset = PhaseAdjustment.objects.all()
    serializer_class = PhaseAdjustmentSerializer
    owner_path = "phase__owner"
    parent_checks = [("phase", Phase, "owner")]
    prescription_write = True  # a coach may edit a client's prescription timeline

    def get_queryset(self):
        return super().get_queryset().select_related(
            "nutrition_target", "program", "protocol"
        )

    def _check_links(self, serializer):
        owner_id = self.effective_owner.id
        for field in ("nutrition_target", "program", "protocol"):
            obj = serializer.validated_data.get(field)
            if obj is not None and obj.owner_id != owner_id:
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
class DashboardTodayView(EffectiveOwnerMixin, APIView):
    """Unified 'today' across all five domains + the current phase."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(dashboard_today(self.effective_owner, _parse_date(request, "date")))


@extend_schema(
    tags=["core"],
    parameters=[
        OpenApiParameter("end", str, description="ISO end date (default today); 7-day window")
    ],
    responses=WeeklyCheckInSerializer,
)
class WeeklyCheckInView(EffectiveOwnerMixin, APIView):
    """Auto-generated weekly check-in report — the self-coaching payload."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(weekly_checkin(self.effective_owner, _parse_date(request, "end")))


class ReplicaBootstrapView(APIView):
    """Restore the latest native backup, or assemble a one-time relational import."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        backup = ReplicaBackup.objects.filter(owner=request.user).first()
        if backup is not None:
            return Response(
                {
                    "source": "backup",
                    "revision": backup.revision,
                    "backed_up_at": backup.updated_at,
                    "snapshot": backup.snapshot,
                }
            )
        return Response(
            {
                "source": "server",
                "revision": 0,
                "backed_up_at": None,
                "snapshot": build_replica_snapshot(request.user),
            }
        )


class ReplicaBackupView(APIView):
    """Idempotently persist the latest device-authoritative structured snapshot."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        backup = ReplicaBackup.objects.filter(owner=request.user).first()
        if backup is None:
            return Response({"detail": "No native backup exists."}, status=404)
        return Response(
            {
                "device_id": backup.device_id,
                "schema_version": backup.schema_version,
                "revision": backup.revision,
                "backed_up_at": backup.updated_at,
                "snapshot": backup.snapshot,
            }
        )

    @transaction.atomic
    def put(self, request):
        required = ("device_id", "schema_version", "revision", "base_revision", "snapshot")
        missing = [key for key in required if key not in request.data]
        if missing:
            raise ValidationError({key: "This field is required." for key in missing})

        try:
            revision = int(request.data["revision"])
            base_revision = int(request.data["base_revision"])
            schema_version = int(request.data["schema_version"])
        except (TypeError, ValueError) as exc:
            raise ValidationError("Revision and schema values must be integers.") from exc
        if revision < 1 or base_revision < 0 or schema_version < 1:
            raise ValidationError("Revision and schema values are outside the valid range.")
        snapshot = request.data["snapshot"]
        if not isinstance(snapshot, dict):
            raise ValidationError({"snapshot": "Expected a JSON object."})

        backup = (
            ReplicaBackup.objects.select_for_update().filter(owner=request.user).first()
        )
        device_id = request.data["device_id"]

        if (
            backup is not None
            and revision == backup.revision
            and str(backup.device_id) == str(device_id)
        ):
            return Response(
                {
                    "revision": backup.revision,
                    "backed_up_at": backup.updated_at,
                    "idempotent": True,
                }
            )

        current_revision = backup.revision if backup is not None else 0
        if base_revision != current_revision or revision <= current_revision:
            return Response(
                {
                    "detail": "The server holds a newer native backup.",
                    "server_revision": current_revision,
                },
                status=409,
            )

        if backup is None:
            backup = ReplicaBackup(owner=request.user)
        backup.device_id = device_id
        backup.schema_version = schema_version
        backup.revision = revision
        backup.snapshot = snapshot
        apply_replica_settings(request.user, snapshot)
        apply_replica_health(request.user, snapshot)
        backup.save()
        return Response(
            {
                "revision": backup.revision,
                "backed_up_at": backup.updated_at,
                "idempotent": False,
            }
        )


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


class CheckinReportView(EffectiveOwnerMixin, APIView):
    """Generate a shareable check-in report PDF for a date window (e.g. a phase).

    Honours the effective owner, so a coach can download a client's report.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["core"],
        parameters=[
            OpenApiParameter("start", str), OpenApiParameter("end", str),
            OpenApiParameter(
                "include", str,
                description="CSV of sections: training,nutrition,photos,protocols,bloodwork",
            ),
        ],
        responses={(200, "application/pdf"): OpenApiTypes.BINARY},
    )
    def get(self, request):
        end = _parse_date(request, "end") or date_cls.today()
        start = _parse_date(request, "start") or (end - timedelta(days=84))
        inc = request.query_params.get("include")
        include = {s for s in inc.split(",") if s} if inc is not None else ALL_SECTIONS
        filename, pdf = build_checkin_report_pdf(self.effective_owner, start, end, include)
        resp = HttpResponse(pdf, content_type="application/pdf")
        resp["Content-Disposition"] = f'attachment; filename="{filename}"'
        return resp
