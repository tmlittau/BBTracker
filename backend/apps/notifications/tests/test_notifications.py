"""Tests for Home Assistant notifications + reminder dispatch.

The HA HTTP call is always mocked — no network. Covers the ha_notify client
(configured/unconfigured), slot-pending computation, rest-reminder firing, and
the REST endpoints.
"""
import io
import json
import urllib.error
from datetime import timedelta
from unittest import mock

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.notifications import services
from apps.notifications.models import ReminderDispatch, ReminderSettings, RestReminder
from apps.protocols.models import Compound, DoseLog, Protocol, ProtocolItem

pytestmark = pytest.mark.django_db


@pytest.fixture
def user(db):
    return User.objects.create_user(email="a@example.com", password="x")


@pytest.fixture
def api(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def compound(db):
    return Compound.objects.create(name="Test E", compound_class="anabolic", default_unit="mg")


@pytest.fixture
def active_item(user, compound):
    protocol = Protocol.objects.create(
        owner=user, name="Cycle", is_active=True, started_on=timezone.now().date()
    )
    return ProtocolItem.objects.create(
        protocol=protocol, compound=compound, dose_amount="100", dose_unit="mg",
        frequency="daily", times_of_day=["waking", "noon"],
    )


# --- interval-cadence scheduling (reminder worker) ----------------------------


def _every3(user, compound, started_on):
    proto = Protocol.objects.create(
        owner=user, name="C", is_active=True, started_on=started_on
    )
    return ProtocolItem.objects.create(
        protocol=proto, compound=compound, dose_amount="1", dose_unit="mg",
        frequency="every_3_days", times_of_day=["waking"],
    )


def test_item_scheduled_on_every_3_days_phased_to_start(user, compound):
    start = timezone.now().date()
    item = _every3(user, compound, start)
    assert services.item_scheduled_on(item, start) is True
    assert services.item_scheduled_on(item, start + timedelta(days=1)) is False
    assert services.item_scheduled_on(item, start + timedelta(days=2)) is False
    assert services.item_scheduled_on(item, start + timedelta(days=3)) is True


def test_item_scheduled_on_every_3_days_without_start_is_not_daily(user, compound):
    # No start date → phased to the fixed epoch, so exactly one day in three fires —
    # not "every day" (the old reminder bug anchored to the day being checked).
    item = _every3(user, compound, None)
    base = timezone.now().date()
    flags = [services.item_scheduled_on(item, base + timedelta(days=i)) for i in range(3)]
    assert sum(flags) == 1


# --- ha_notify client ---------------------------------------------------------


def test_ha_notify_noop_when_unconfigured(settings):
    settings.HA_BASE_URL = ""
    settings.HA_TOKEN = ""
    assert services.ha_notify("t", "m") is False


def test_ha_notify_posts_when_configured(settings):
    settings.HA_BASE_URL = "http://ha.local:8123"
    settings.HA_TOKEN = "tok"
    settings.HA_NOTIFY_SERVICE = "mobile_app_phone"

    class _Resp:
        status = 200

        def read(self):
            return b""

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    with mock.patch("urllib.request.urlopen", return_value=_Resp()) as m:
        assert services.ha_notify("Title", "Body") is True
    req = m.call_args.args[0]
    assert req.full_url == "http://ha.local:8123/api/services/notify/mobile_app_phone"
    assert req.get_header("Authorization") == "Bearer tok"
    assert json.loads(req.data) == {"title": "Title", "message": "Body"}


def test_ha_notify_result_surfaces_http_error(settings):
    settings.HA_BASE_URL = "http://ha.local:8123"
    settings.HA_TOKEN = "tok"
    err = urllib.error.HTTPError(
        "u", 400, "Bad Request", {}, io.BytesIO(b'{"message":"Service notify.notify not found"}')
    )
    with mock.patch("urllib.request.urlopen", side_effect=err):
        ok, detail = services.ha_notify_result("t", "m")
    assert ok is False
    assert "400" in detail
    assert "not found" in detail


# --- slot pending logic -------------------------------------------------------


def test_slot_pending_tracks_per_slot(user, compound, active_item):
    today = timezone.now().date()
    # Nothing logged → due at both waking and noon.
    assert services.slot_pending_items(user, "waking", today) == ["Test E"]
    assert services.slot_pending_items(user, "noon", today) == ["Test E"]
    # Log one dose → waking satisfied (1/1), noon still pending (1/2).
    DoseLog.objects.create(
        owner=user, compound=compound, taken_at=timezone.now(), amount="100", unit="mg"
    )
    assert services.slot_pending_items(user, "waking", today) == []
    assert services.slot_pending_items(user, "noon", today) == ["Test E"]


def test_send_slot_reminder_records_dispatch(user, active_item):
    today = timezone.now().date()
    with mock.patch("apps.notifications.services.ha_notify", return_value=True) as m:
        assert services.send_slot_reminder(user, "waking", today) is True
    m.assert_called_once()
    assert ReminderDispatch.objects.filter(owner=user, slot="waking", sent_on=today).exists()


# --- rest reminders -----------------------------------------------------------


def test_dispatch_rest_reminders_fires_due_only(user):
    now = timezone.now()
    RestReminder.objects.create(owner=user, fire_at=now - timedelta(seconds=5))
    with mock.patch("apps.notifications.services.ha_notify", return_value=True) as m:
        assert services.dispatch_rest_reminders(now) == 1
    m.assert_called_once()
    assert not RestReminder.objects.filter(owner=user).exists()


def test_dispatch_rest_reminders_skips_future(user):
    RestReminder.objects.create(owner=user, fire_at=timezone.now() + timedelta(minutes=2))
    with mock.patch("apps.notifications.services.ha_notify") as m:
        assert services.dispatch_rest_reminders(timezone.now()) == 0
    m.assert_not_called()


# --- endpoints ----------------------------------------------------------------


def test_reminder_settings_get_creates_defaults(api, user):
    resp = api.get("/api/v1/notifications/reminder-settings/")
    assert resp.status_code == 200
    assert resp.json()["waking"] == "06:30:00"
    assert ReminderSettings.objects.filter(owner=user).exists()


def test_reminder_settings_update(api):
    api.get("/api/v1/notifications/reminder-settings/")
    resp = api.patch(
        "/api/v1/notifications/reminder-settings/",
        {"waking": "07:00", "enabled": False},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["waking"] == "07:00:00"
    assert resp.json()["enabled"] is False


def test_rest_schedule_and_cancel(api, user):
    sched = api.post("/api/v1/notifications/rest/schedule/", {"seconds": 90}, format="json")
    assert sched.json()["ok"] is True
    assert RestReminder.objects.filter(owner=user).exists()
    assert api.post("/api/v1/notifications/rest/cancel/").json()["ok"] is True
    assert not RestReminder.objects.filter(owner=user).exists()


def test_rest_schedule_respects_disabled(api, user):
    ReminderSettings.objects.create(owner=user, rest_enabled=False)
    resp = api.post("/api/v1/notifications/rest/schedule/", {"seconds": 90}, format="json")
    assert resp.json()["ok"] is False
    assert not RestReminder.objects.filter(owner=user).exists()


def test_test_notification_endpoint(api):
    with mock.patch(
        "apps.notifications.views.ha_notify_result", return_value=(True, "HTTP 200")
    ) as m:
        assert api.post("/api/v1/notifications/test/").json()["ok"] is True
    m.assert_called_once()


def test_dispatch_protocol_activation_follows_timeline(user):
    """The worker pass activates the protocol the phase timeline prescribes today."""
    from apps.core.models import Phase, PhaseAdjustment

    today = timezone.now().date()
    a = Protocol.objects.create(owner=user, name="A", is_active=True, started_on=today)
    b = Protocol.objects.create(owner=user, name="B", is_active=False)
    phase = Phase.objects.create(
        owner=user, name="Block", phase_type="bulk", start_date=today - timedelta(days=10)
    )
    PhaseAdjustment.objects.create(phase=phase, effective_date=today, protocol=b)

    assert services.dispatch_protocol_activation(timezone.now()) == 1
    a.refresh_from_db()
    b.refresh_from_db()
    assert b.is_active and not a.is_active


def test_endpoints_require_auth():
    assert APIClient().get("/api/v1/notifications/reminder-settings/").status_code in (401, 403)
