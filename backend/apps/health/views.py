from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import HealthDailyAggregateSerializer
from .services import apply_health_aggregate_rows


@extend_schema(tags=["health"])
class HealthAggregateIngestView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=HealthDailyAggregateSerializer(many=True),
        responses=dict,
    )
    def post(self, request):
        rows = request.data.get("aggregates") if isinstance(request.data, dict) else request.data
        if not isinstance(rows, list):
            raise ValidationError({"aggregates": "Expected a list."})
        result = apply_health_aggregate_rows(request.user, rows)
        return Response(result)
