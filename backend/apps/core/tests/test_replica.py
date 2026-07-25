import uuid

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.models import Phase, ReplicaBackup
from apps.health.models import HealthDailyAggregate

pytestmark = pytest.mark.django_db


@pytest.fixture
def user(db):
    return User.objects.create_user(email="replica@example.com", password="x")


@pytest.fixture
def api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_bootstrap_builds_relational_snapshot(api, user):
    Phase.objects.create(owner=user, name="Local import", start_date="2026-07-01")

    response = api.get("/api/v1/sync/bootstrap/")

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "server"
    assert body["revision"] == 0
    assert body["snapshot"]["schema_version"] == 1
    assert body["snapshot"]["user"]["email"] == user.email
    assert body["snapshot"]["phases"][0]["name"] == "Local import"
    assert "workout_sessions" in body["snapshot"]
    assert "blood_results" in body["snapshot"]
    assert body["snapshot"]["reminder_settings"]["waking"] == "06:30:00"


def test_backup_is_idempotent_and_bootstrap_restores_it(api, user):
    device_id = str(uuid.uuid4())
    payload = {
        "device_id": device_id,
        "schema_version": 1,
        "revision": 1,
        "base_revision": 0,
        "snapshot": {"schema_version": 1, "phases": [{"id": -1, "name": "Offline"}]},
    }

    first = api.put("/api/v1/sync/backup/", payload, format="json")
    repeated = api.put("/api/v1/sync/backup/", payload, format="json")
    restored = api.get("/api/v1/sync/bootstrap/")

    assert first.status_code == 200
    assert first.json()["idempotent"] is False
    assert repeated.status_code == 200
    assert repeated.json()["idempotent"] is True
    assert ReplicaBackup.objects.get(owner=user).revision == 1
    assert restored.json()["source"] == "backup"
    assert restored.json()["snapshot"]["phases"][0]["name"] == "Offline"


def test_backup_rejects_stale_base_revision(api, user):
    device_id = str(uuid.uuid4())
    ReplicaBackup.objects.create(
        owner=user,
        device_id=device_id,
        schema_version=1,
        revision=3,
        snapshot={"schema_version": 1},
    )

    response = api.put(
        "/api/v1/sync/backup/",
        {
            "device_id": device_id,
            "schema_version": 1,
            "revision": 4,
            "base_revision": 2,
            "snapshot": {"schema_version": 1},
        },
        format="json",
    )

    assert response.status_code == 409
    assert response.json()["server_revision"] == 3
    assert ReplicaBackup.objects.get(owner=user).revision == 3


def test_backup_mirrors_profile_and_reminders_for_web_compatibility(api, user):
    payload = {
        "device_id": str(uuid.uuid4()),
        "schema_version": 1,
        "revision": 1,
        "base_revision": 0,
        "snapshot": {
            "schema_version": 1,
            "user": {
                "first_name": "Native",
                "profile": {
                    "sex": "male",
                    "date_of_birth": "1990-05-15",
                    "height_cm": 182.5,
                    "unit_system": "imperial",
                    "timezone": "Europe/Amsterdam",
                },
            },
            "reminder_settings": {
                "enabled": False,
                "rest_enabled": True,
                "waking": "07:15:00",
                "waking_label": "Morning",
            },
        },
    }

    response = api.put("/api/v1/sync/backup/", payload, format="json")

    assert response.status_code == 200
    user.refresh_from_db()
    assert user.first_name == "Native"
    assert str(user.profile.date_of_birth) == "1990-05-15"
    assert str(user.profile.height_cm) == "182.5"
    assert user.profile.unit_system == "imperial"
    assert user.reminder_settings.enabled is False
    assert str(user.reminder_settings.waking) == "07:15:00"
    assert user.reminder_settings.waking_label == "Morning"

    payload["revision"] = 2
    payload["base_revision"] = 1
    payload["snapshot"]["user"]["profile"]["date_of_birth"] = None
    payload["snapshot"]["user"]["profile"]["height_cm"] = None
    response = api.put("/api/v1/sync/backup/", payload, format="json")

    assert response.status_code == 200
    user.refresh_from_db()
    assert user.profile.date_of_birth is None
    assert user.profile.height_cm is None


def test_backup_projects_and_restores_health_aggregates(api, user):
    payload = {
        "device_id": str(uuid.uuid4()),
        "schema_version": 1,
        "revision": 1,
        "base_revision": 0,
        "snapshot": {
            "schema_version": 1,
            "health_data": {
                "last_sync_at": "2026-07-25T10:15:00Z",
                "aggregates": [
                    {
                        "kind": "resting_hr",
                        "date": "2026-07-25",
                        "value": 54.0,
                        "minimum": 51.0,
                        "maximum": 58.0,
                        "sample_count": 4,
                        "source": "healthkit",
                        "source_fingerprint": "fingerprint",
                        "updated_at": "2026-07-25T10:15:00Z",
                    }
                ],
            },
        },
    }

    response = api.put("/api/v1/sync/backup/", payload, format="json")
    restored = api.get("/api/v1/sync/bootstrap/")

    assert response.status_code == 200
    aggregate = HealthDailyAggregate.objects.get(owner=user)
    assert aggregate.kind == "resting_hr"
    assert aggregate.value == 54
    assert restored.json()["snapshot"]["health_data"]["aggregates"][0]["value"] == 54.0

    payload["revision"] = 2
    payload["base_revision"] = 1
    payload["snapshot"]["health_data"]["aggregates"] = []
    response = api.put("/api/v1/sync/backup/", payload, format="json")

    assert response.status_code == 200
    assert not HealthDailyAggregate.objects.filter(owner=user).exists()
