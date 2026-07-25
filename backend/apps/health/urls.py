from django.urls import path

from .views import HealthAggregateIngestView

urlpatterns = [
    path("ingest/", HealthAggregateIngestView.as_view(), name="health-ingest"),
    path("aggregates/ingest/", HealthAggregateIngestView.as_view(), name="health-aggregate-ingest"),
]
