from datetime import date as date_cls

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import BodyMeasurement
from .serializers import BodyAnalysisSerializer, BodyMeasurementSerializer
from .services import body_analysis


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
