from django.db import transaction

from .models import HealthDailyAggregate
from .serializers import HealthDailyAggregateSerializer


@transaction.atomic
def apply_health_aggregate_rows(owner, rows, *, replace=False):
    serializer = HealthDailyAggregateSerializer(data=rows, many=True)
    serializer.is_valid(raise_exception=True)

    current = {
        (row.kind, row.date, row.source): row
        for row in HealthDailyAggregate.objects.select_for_update().filter(owner=owner)
    }
    retained_ids = []
    accepted = 0
    unchanged = 0

    for data in serializer.validated_data:
        key = (data["kind"], data["date"], data["source"])
        existing = current.get(key)
        comparable_fields = (
            "value",
            "minimum",
            "maximum",
            "sample_count",
            "source_fingerprint",
            "updated_at",
        )
        if existing is not None and all(
            getattr(existing, field) == data.get(field) for field in comparable_fields
        ):
            retained_ids.append(existing.id)
            unchanged += 1
            continue

        aggregate, _ = HealthDailyAggregate.objects.update_or_create(
            owner=owner,
            kind=data["kind"],
            date=data["date"],
            source=data["source"],
            defaults={
                "value": data["value"],
                "minimum": data.get("minimum"),
                "maximum": data.get("maximum"),
                "sample_count": data["sample_count"],
                "source_fingerprint": data["source_fingerprint"],
                "updated_at": data["updated_at"],
            },
        )
        retained_ids.append(aggregate.id)
        accepted += 1

    deleted = 0
    if replace:
        stale = HealthDailyAggregate.objects.filter(owner=owner)
        if retained_ids:
            stale = stale.exclude(id__in=retained_ids)
        deleted, _ = stale.delete()

    return {"accepted": accepted, "unchanged": unchanged, "deleted": deleted}
