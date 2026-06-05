from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
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
    CompoundSerializer,
    ConcentrationPointSerializer,
    DoseLogSerializer,
    InjectionSiteSerializer,
    MarkerTrendPointSerializer,
    ProtocolItemSerializer,
    ProtocolSerializer,
    SiteRecencySerializer,
    SupplementSerializer,
    VialSerializer,
)
from .services import (
    bloodwork_matrix,
    compound_concentration,
    injection_site_recency,
    marker_trend,
    protocol_adherence,
    suggest_next_site,
)


class GlobalOrOwnedViewSet(viewsets.ModelViewSet):
    """Reference items visible if global (owner=None) or owned; editable only if owned."""

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

    def _ensure_owned(self, instance):
        if instance.owner_id != self.request.user.id:
            raise PermissionDenied("You can only modify your own items.")

    def perform_update(self, serializer):
        self._ensure_owned(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._ensure_owned(instance)
        instance.delete()


@extend_schema(tags=["protocols"])
class CompoundViewSet(GlobalOrOwnedViewSet):
    model = Compound
    serializer_class = CompoundSerializer
    search_fields = ["name", "ester"]


@extend_schema(tags=["protocols"])
class SupplementViewSet(GlobalOrOwnedViewSet):
    model = Supplement
    serializer_class = SupplementSerializer
    search_fields = ["name", "brand"]

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

        Body: {"measured_on": "YYYY-MM-DD", "results": [{"marker": id, "value": "x"}, …]}.
        """
        from decimal import Decimal, InvalidOperation

        measured_on = request.data.get("measured_on")
        if not measured_on:
            raise ValidationError({"measured_on": "required"})
        valid_markers = set(BloodMarker.objects.values_list("id", flat=True))
        created = []
        for r in request.data.get("results") or []:
            value = r.get("value")
            marker_id = r.get("marker")
            if value in (None, "") or marker_id not in valid_markers:
                continue
            try:
                value = Decimal(str(value))
            except (InvalidOperation, ValueError):
                continue
            created.append(
                BloodResult.objects.create(
                    owner=request.user, marker_id=marker_id, value=value, measured_on=measured_on
                )
            )
        return Response(BloodResultSerializer(created, many=True).data, status=201)


@extend_schema(tags=["protocols"])
class BloodPressureLogViewSet(viewsets.ModelViewSet):
    serializer_class = BloodPressureLogSerializer

    def get_queryset(self):
        return BloodPressureLog.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


@extend_schema(
    tags=["protocols"],
    parameters=[
        OpenApiParameter("compound", int, required=True),
        OpenApiParameter("days", int),
    ],
    responses=ConcentrationPointSerializer(many=True),
)
class ConcentrationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        compound_id = request.query_params.get("compound")
        if not compound_id:
            raise ValidationError({"compound": "required"})
        compound = Compound.objects.filter(
            Q(owner=request.user) | Q(owner__isnull=True), pk=compound_id
        ).first()
        if compound is None:
            raise ValidationError({"compound": "unknown compound"})
        days = _int_param(request, "days", 30)
        return Response(compound_concentration(request.user, compound, days=days))


def _int_param(request, name, default):
    raw = request.query_params.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise ValidationError({name: "must be an integer"}) from exc
