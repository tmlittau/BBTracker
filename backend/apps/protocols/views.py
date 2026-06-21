from datetime import date, timedelta

from django.db.models import ProtectedError, Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.viewsets import OwnerScopedViewSet

from .models import (
    BloodMarker,
    BloodPressureLog,
    BloodResult,
    Compound,
    DoseLog,
    InjectionSite,
    Protocol,
    ProtocolItem,
    Supplement,
    Vial,
)
from .serializers import (
    AdherenceRowSerializer,
    BloodMarkerSerializer,
    BloodPressureLogSerializer,
    BloodResultSerializer,
    CompoundPlotRequestSerializer,
    CompoundPlotSerializer,
    CompoundSerializer,
    DoseLogSerializer,
    InjectionSiteSerializer,
    MarkerTrendPointSerializer,
    PhaseDoseMatrixSerializer,
    ProtocolItemSerializer,
    ProtocolReleaseSerializer,
    ProtocolSerializer,
    SiteRecencySerializer,
    SupplementSerializer,
    VialSerializer,
    WeekPrepPlanSerializer,
)
from .services import (
    bloodwork_matrix,
    injection_site_recency,
    marker_trend,
    phase_dose_matrix,
    plot_compounds,
    protocol_adherence,
    protocol_release_curves,
    suggest_next_site,
    week_prep_plan,
)


class GlobalOrOwnedViewSet(viewsets.ModelViewSet):
    """Reference items visible if global (owner=None) or owned. Single-user app:
    seeded globals are editable + deletable too; deletion is blocked (with a clear
    message) only when the item is still referenced by logged history."""

    search_fields: list[str] = ["name"]

    def get_queryset(self):
        qs = self.model.objects.filter(Q(owner=self.request.user) | Q(owner__isnull=True))
        q = self.request.query_params.get("q")
        if q:
            cond = Q()
            for f in self.search_fields:
                cond |= Q(**{f"{f}__icontains": q})
            qs = qs.filter(cond)
        return qs

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError:
            raise ValidationError(
                "Can't delete — it's still used in your protocols or logged doses. "
                "Remove those first."
            ) from None


@extend_schema(tags=["protocols"])
class CompoundViewSet(GlobalOrOwnedViewSet):
    model = Compound
    serializer_class = CompoundSerializer
    search_fields = ["name", "ester"]
    # Bounded reference data (global seed + a user's customs) — return the whole
    # list so the library and the protocol-builder picker can filter/search it
    # client-side without the 50-row page cap cropping entries.
    pagination_class = None


@extend_schema(tags=["protocols"], request=CompoundPlotRequestSerializer,
               responses=CompoundPlotSerializer)
class CompoundPlotView(APIView):
    """Stateless cycle planner: POST a set of {compound, dose, frequency, …} items →
    overlaid relative concentration curves. Plans without touching any protocol."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        ser = CompoundPlotRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = plot_compounds(
            request.user,
            ser.validated_data["items"],
            ser.validated_data.get("horizon_days", 84),
        )
        return Response(data)


@extend_schema(
    tags=["protocols"],
    parameters=[OpenApiParameter("start", str, description="Monday of the week (YYYY-MM-DD).")],
    responses=WeekPrepPlanSerializer,
)
class WeekPrepView(APIView):
    """Weekly pill-box plan: an every-day baseline plus per-day deviations for the
    owner's oral compounds + supplements, resolving the protocol in force each day."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        raw = request.query_params.get("start")
        if raw:
            try:
                start = date.fromisoformat(raw)
            except ValueError:
                raise ValidationError({"start": "Use YYYY-MM-DD."}) from None
        else:
            today = timezone.localdate()
            start = today - timedelta(days=today.weekday())
        return Response(week_prep_plan(request.user, start))


@extend_schema(tags=["protocols"])
class SupplementViewSet(GlobalOrOwnedViewSet):
    model = Supplement
    serializer_class = SupplementSerializer
    search_fields = ["name", "brand"]
    pagination_class = None

    def get_queryset(self):
        return super().get_queryset().prefetch_related("supplement_nutrients__nutrient")


@extend_schema(tags=["protocols"])
class InjectionSiteViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = InjectionSite.objects.all()
    serializer_class = InjectionSiteSerializer
    pagination_class = None

    @extend_schema(
        parameters=[OpenApiParameter("days", int)],
        responses=SiteRecencySerializer(many=True),
    )
    @action(detail=False, methods=["get"])
    def recency(self, request):
        days = _int_param(request, "days", 30)
        return Response(injection_site_recency(request.user, days=days))

    @extend_schema(responses=SiteRecencySerializer)
    @action(detail=False, methods=["get"])
    def suggest(self, request):
        return Response(suggest_next_site(request.user) or {})


@extend_schema(tags=["protocols"])
class BloodMarkerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = BloodMarker.objects.all()
    serializer_class = BloodMarkerSerializer
    pagination_class = None


@extend_schema(tags=["protocols"])
class ProtocolViewSet(viewsets.ModelViewSet):
    serializer_class = ProtocolSerializer

    def get_queryset(self):
        return Protocol.objects.filter(owner=self.request.user).prefetch_related(
            "items__compound", "items__supplement"
        )

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        protocol = self.get_object()
        Protocol.objects.filter(owner=request.user).update(is_active=False)
        protocol.is_active = True
        protocol.save(update_fields=["is_active"])
        return Response(self.get_serializer(protocol).data)

    @extend_schema(
        parameters=[OpenApiParameter("window_days", int)],
        responses=AdherenceRowSerializer(many=True),
    )
    @action(detail=True, methods=["get"])
    def adherence(self, request, pk=None):
        protocol = self.get_object()
        window = _int_param(request, "window_days", 28)
        return Response(protocol_adherence(request.user, protocol, window_days=window))

    @extend_schema(
        parameters=[OpenApiParameter("horizon_days", int)],
        responses=ProtocolReleaseSerializer,
    )
    @action(detail=True, methods=["get"])
    def release(self, request, pk=None):
        """Per-compound active-release (mg/day) curves: logged actuals + projected future."""
        protocol = self.get_object()
        horizon = _int_param(request, "horizon_days", 84)
        return Response(protocol_release_curves(request.user, protocol, horizon_days=horizon))

    @extend_schema(
        parameters=[OpenApiParameter("phase", int)],
        responses=PhaseDoseMatrixSerializer,
    )
    @action(detail=True, methods=["get"])
    def phase_matrix(self, request, pk=None):
        """Week-by-week dose table for a phase: rows = items, columns = weeks.

        `?phase=` selects the phase; without it, the phase containing today (else the
        latest) is used.
        """
        from apps.core.models import Phase

        protocol = self.get_object()
        phase_id = _int_param(request, "phase", 0)
        phases = Phase.objects.filter(owner=request.user)
        phase = phases.filter(id=phase_id).first() if phase_id else None
        if phase is None:
            today = timezone.now().date()
            phase = (
                phases.filter(start_date__lte=today)
                .filter(Q(end_date__isnull=True) | Q(end_date__gte=today))
                .order_by("-start_date")
                .first()
                or phases.order_by("-start_date").first()
            )
        if phase is None:
            return Response(
                {"detail": "No phase found — create a phase to see its dose table."},
                status=400,
            )
        return Response(phase_dose_matrix(request.user, phase, protocol))


@extend_schema(tags=["protocols"])
class ProtocolItemViewSet(OwnerScopedViewSet):
    queryset = ProtocolItem.objects.all()
    serializer_class = ProtocolItemSerializer
    owner_path = "protocol__owner"
    parent_checks = [("protocol", Protocol, "owner")]

    def _check_refs(self, serializer):
        for field in ("compound", "supplement"):
            obj = serializer.validated_data.get(field)
            if obj is not None and obj.owner_id not in (None, self.request.user.id):
                raise PermissionDenied(f"That {field} does not belong to you.")

    def perform_create(self, serializer):
        self._validate_parents(serializer)
        self._check_refs(serializer)
        serializer.save()

    def perform_update(self, serializer):
        self._validate_parents(serializer)
        self._check_refs(serializer)
        serializer.save()


def _ref_owned_ok(user, obj):
    return obj is None or obj.owner_id in (None, user.id)


@extend_schema(tags=["protocols"])
class DoseLogViewSet(viewsets.ModelViewSet):
    serializer_class = DoseLogSerializer

    def get_queryset(self):
        qs = DoseLog.objects.filter(owner=self.request.user).select_related(
            "compound", "supplement", "injection_site"
        )
        d = self.request.query_params.get("date")
        if d:
            qs = qs.filter(taken_at__date=d)
        compound = self.request.query_params.get("compound")
        if compound:
            qs = qs.filter(compound_id=compound)
        frm = self.request.query_params.get("from")
        if frm:
            qs = qs.filter(taken_at__date__gte=frm)
        to = self.request.query_params.get("to")
        if to:
            qs = qs.filter(taken_at__date__lte=to)
        return qs

    def _check_refs(self, serializer):
        if not _ref_owned_ok(self.request.user, serializer.validated_data.get("compound")):
            raise PermissionDenied("That compound does not belong to you.")
        if not _ref_owned_ok(self.request.user, serializer.validated_data.get("supplement")):
            raise PermissionDenied("That supplement does not belong to you.")
        item = serializer.validated_data.get("protocol_item")
        if item is not None and item.protocol.owner_id != self.request.user.id:
            raise PermissionDenied("That protocol item does not belong to you.")

    def perform_create(self, serializer):
        self._check_refs(serializer)
        serializer.save(owner=self.request.user)

    def perform_update(self, serializer):
        self._check_refs(serializer)
        serializer.save()


@extend_schema(tags=["protocols"])
class VialViewSet(viewsets.ModelViewSet):
    serializer_class = VialSerializer

    def get_queryset(self):
        return Vial.objects.filter(owner=self.request.user).select_related("compound")

    def _check_refs(self, serializer):
        if not _ref_owned_ok(self.request.user, serializer.validated_data.get("compound")):
            raise PermissionDenied("That compound does not belong to you.")

    def perform_create(self, serializer):
        self._check_refs(serializer)
        serializer.save(owner=self.request.user)

    def perform_update(self, serializer):
        self._check_refs(serializer)
        serializer.save()


@extend_schema(tags=["protocols"])
class BloodResultViewSet(viewsets.ModelViewSet):
    serializer_class = BloodResultSerializer

    def get_queryset(self):
        qs = BloodResult.objects.filter(owner=self.request.user).select_related("marker")
        marker = self.request.query_params.get("marker")
        if marker:
            qs = qs.filter(marker_id=marker)
        return qs

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @extend_schema(
        parameters=[OpenApiParameter("marker", int, required=True)],
        responses=MarkerTrendPointSerializer(many=True),
    )
    @action(detail=False, methods=["get"])
    def trend(self, request):
        marker_id = request.query_params.get("marker")
        if not marker_id:
            raise ValidationError({"marker": "required"})
        try:
            marker = BloodMarker.objects.get(pk=marker_id)
        except BloodMarker.DoesNotExist as exc:
            raise ValidationError({"marker": "unknown marker"}) from exc
        sex = getattr(getattr(request.user, "profile", None), "sex", None)
        return Response(marker_trend(request.user, marker, sex=sex))

    @action(detail=False, methods=["get"])
    def matrix(self, request):
        """Markers × dates table with %-change + range flags (tabular trend view)."""
        sex = getattr(getattr(request.user, "profile", None), "sex", None)
        return Response(bloodwork_matrix(request.user, sex=sex))

    @action(detail=False, methods=["post"])
    def bulk(self, request):
        """Create many results for one date; blank/invalid markers are skipped.

        Body: {"measured_on": "YYYY-MM-DD", "results": [{"marker": id, "value": "x",
        "unit"?: "", "ref_low"?: n, "ref_high"?: n, "source"?: "manual"|"pdf"}, …]}.
        Per-result unit/ranges (e.g. from a PDF import) are stored verbatim, so each
        reading flags against the exact range it came with.
        """
        from decimal import Decimal, InvalidOperation

        def _dec(v):
            if v in (None, ""):
                return None
            try:
                return Decimal(str(v))
            except (InvalidOperation, ValueError):
                return None

        measured_on = request.data.get("measured_on")
        if not measured_on:
            raise ValidationError({"measured_on": "required"})
        valid_markers = set(BloodMarker.objects.values_list("id", flat=True))
        created = []
        for r in request.data.get("results") or []:
            marker_id = r.get("marker")
            value = _dec(r.get("value"))
            if value is None or marker_id not in valid_markers:
                continue
            source = r.get("source") if r.get("source") in ("manual", "pdf") else "manual"
            created.append(
                BloodResult.objects.create(
                    owner=request.user, marker_id=marker_id, value=value,
                    unit=(r.get("unit") or "")[:20],
                    ref_low=_dec(r.get("ref_low")), ref_high=_dec(r.get("ref_high")),
                    source=source, measured_on=measured_on,
                )
            )
        return Response(BloodResultSerializer(created, many=True).data, status=201)

    @extend_schema(request=None, responses=None)
    @action(detail=False, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def parse_pdf(self, request):
        """Extract reviewable rows from an uploaded lab PDF (multipart `file`).

        Stateless: nothing is persisted and the bytes are dropped after parsing — the
        client reviews/edits the rows and POSTs the confirmed set to `bulk/`.
        """
        from .bloodwork_pdf import extract_text, match_marker, parse_report

        upload = request.FILES.get("file")
        if upload is None:
            raise ValidationError({"file": "required"})
        if upload.size and upload.size > 20 * 1024 * 1024:
            raise ValidationError({"file": "file too large (max 20 MB)"})
        try:
            text = extract_text(upload.read())
        except Exception as exc:  # noqa: BLE001 - any extraction failure → 400
            raise ValidationError({"file": "could not read this PDF"}) from exc
        parsed = parse_report(text)
        markers = list(BloodMarker.objects.all())
        rows = []
        for r in parsed["rows"]:
            marker, conf = match_marker(r["raw_name"], markers)
            rows.append({
                **r,
                "marker": marker.id if marker else None,
                "marker_name": marker.name if marker else None,
                "matched": marker is not None,
                "confidence": round(conf, 2),
            })
        return Response({"measured_on": parsed["measured_on"], "rows": rows})


@extend_schema(tags=["protocols"])
class BloodPressureLogViewSet(viewsets.ModelViewSet):
    serializer_class = BloodPressureLogSerializer

    def get_queryset(self):
        return BloodPressureLog.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


def _int_param(request, name, default):
    raw = request.query_params.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise ValidationError({name: "must be an integer"}) from exc
