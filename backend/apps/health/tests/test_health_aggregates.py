import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.health.models import HealthDailyAggregate

pytestmark = pytest.mark.django_db


def aggregate(value=42.50000000000001, fingerprint="abc"):
    return {
        "kind": "hrv",
        "date": "2026-07-25",
        "value": value,
        "minimum": 38.0,
        "maximum": 47.0,
        "sample_count": 3,
        "source": "healthkit",
        "source_fingerprint": fingerprint,
        "updated_at": "2026-07-25T10:15:00Z",
    }


def test_ingest_is_owner_scoped_and_idempotent(db):
    user = User.objects.create_user(email="health@example.com", password="x")
    other = User.objects.create_user(email="other-health@example.com", password="x")
    client = APIClient()
    client.force_authenticate(user)

    first = client.post(
        "/api/v1/health/ingest/",
        {"aggregates": [aggregate()]},
        format="json",
    )
    repeated = client.post(
        "/api/v1/health/ingest/",
        {"aggregates": [aggregate()]},
        format="json",
    )
    changed = client.post(
        "/api/v1/health/ingest/",
        {"aggregates": [aggregate(value=44.0, fingerprint="def")]},
        format="json",
    )

    assert first.status_code == 200
    assert first.json() == {"accepted": 1, "unchanged": 0, "deleted": 0}
    assert repeated.json() == {"accepted": 0, "unchanged": 1, "deleted": 0}
    assert changed.json() == {"accepted": 1, "unchanged": 0, "deleted": 0}
    assert HealthDailyAggregate.objects.get(owner=user).value == 44
    assert not HealthDailyAggregate.objects.filter(owner=other).exists()
