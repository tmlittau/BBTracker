from datetime import date as date_cls
from datetime import timedelta

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import BodyMeasurement
from .serializers import (
    BodyAnalysisSerializer,
    BodyMeasurementSerializer,
    MetricSerializer,
    SeriesOverlaySerializer,
)
from .services import body_analysis
from .timeseries import metric_catalog, overlay


def _parse_date(raw):
    try:
        return date_cls.fromisoformat(raw)
    except ValueError as exc:
        raise ValidationError({"date": "Use YYYY-MM-DD."}) from exc


@extend_schema(tags=["analysis"])
class BodyMeasurementViewSet(viewsets.ModelViewSet):
    serializer_class = BodyMeasurementSerializer

    def get_queryset(self):
        qs = BodyMeasurement.objects.filter(owner=self.request.user)
        mtype = self.request.query_params.get("type")
        if mtype:
            qs = qs.filter(type=mtype)
        return qs

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


@extend_schema(tags=["analysis"])
class BodyAnalysisView(APIView):
    @extend_schema(
        parameters=[OpenApiParameter("date", str), OpenApiParameter("start", str)],
        responses=BodyAnalysisSerializer,
    )
    def get(self, request):
        d = request.query_params.get("date")
        on_date = date_cls.fromisoformat(d) if d else date_cls.today()
        s = request.query_params.get("start")
        window_start = date_cls.fromisoformat(s) if s else None
        return Response(body_analysis(request.user, on_date, window_start))


@extend_schema(tags=["analysis"])
class MetricCatalogView(APIView):
    """Metrics the user has data for — the explore-tool picker."""

    @extend_schema(responses=MetricSerializer(many=True))
    def get(self, request):
        return Response(metric_catalog(request.user))


@extend_schema(tags=["analysis"])
class SeriesOverlayView(APIView):
    """Aligned time-series for `metrics` (comma-separated keys) over [start, end]."""

    @extend_schema(
        parameters=[
            OpenApiParameter("metrics", str, description="Comma-separated metric keys"),
            OpenApiParameter("start", str),
            OpenApiParameter("end", str),
        ],
        responses=SeriesOverlaySerializer,
    )
    def get(self, request):
        keys = [k for k in request.query_params.get("metrics", "").split(",") if k.strip()]
        end_raw = request.query_params.get("end")
        end = _parse_date(end_raw) if end_raw else date_cls.today()
        start_raw = request.query_params.get("start")
        start = _parse_date(start_raw) if start_raw else end - timedelta(days=180)
        return Response(overlay(request.user, keys, start, end))
