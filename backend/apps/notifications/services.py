"""Home Assistant notify integration + reminder dispatch logic.

`ha_notify` POSTs to Home Assistant's REST API
(``POST /api/services/notify/<service>``) with a long-lived token. It is
best-effort and a no-op when unconfigured, so the app is unaffected if Home
Assistant is unreachable or the env vars are unset.
"""
from __future__ import annotations

import datetime
import json
import logging
import urllib.error
import urllib.request
import zoneinfo

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Day slots in chronological order (mirrors protocols.enums.TimeOfDay).
SLOTS = ["waking", "am", "noon", "pm", "night"]
SLOT_LABELS = {"waking": "Waking", "am": "AM", "noon": "Noon", "pm": "PM", "night": "Night"}
SLOT_ORDER = {s: i for i, s in enumerate(SLOTS)}

# Only fire a slot's reminder within this many minutes after its time, so a worker
# that was down doesn't blast stale slots from hours earlier when it restarts.
SLOT_GRACE_MINUTES = 30
HA_TIMEOUT = 8  # seconds


def _ha_config():
    base = (getattr(settings, "HA_BASE_URL", "") or "").rstrip("/")
    token = getattr(settings, "HA_TOKEN", "") or ""
    service = getattr(settings, "HA_NOTIFY_SERVICE", "") or "notify"
    return base, token, service


def ha_configured() -> bool:
    base, token, _ = _ha_config()
    return bool(base and token)


def ha_notify_result(title: str, message: str, data: dict | None = None) -> tuple[bool, str]:
    """Send a notification via Home Assistant. Returns ``(ok, detail)`` where
    `detail` explains a failure — including Home Assistant's own error body (e.g.
    an unknown notify service). Never raises."""
    base, token, service = _ha_config()
    if not (base and token):
        return False, "Home Assistant is not configured (HA_BASE_URL / HA_TOKEN)."
    payload: dict = {"title": title, "message": message}
    if data:
        payload["data"] = data
    request = urllib.request.Request(
        f"{base}/api/services/notify/{service}",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=HA_TIMEOUT) as resp:
            return (200 <= resp.status < 300), f"HTTP {resp.status}"
    except urllib.error.HTTPError as exc:  # 4xx/5xx — HA replied, so it IS reachable
        body = ""
        try:
            body = exc.read().decode("utf-8", "replace")[:300].strip()
        except OSError:
            pass
        detail = (
            f"Home Assistant returned HTTP {exc.code}: {body or exc.reason}. "
            f"Check HA_NOTIFY_SERVICE (currently {service!r}) — it must be an existing "
            "notify service such as mobile_app_<device>."
        )
        logger.warning(detail)
        return False, detail
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        detail = f"Could not reach Home Assistant at {base}: {exc}"
        logger.warning(detail)
        return False, detail


def ha_notify(title: str, message: str, data: dict | None = None) -> bool:
    """Best-effort fire-and-forget notify (bool). See ha_notify_result for the
    failure reason."""
    return ha_notify_result(title, message, data)[0]


# --- Dose-slot reminders ------------------------------------------------------


def _active_protocol(user):
    return (
        user.protocols.filter(is_active=True)
        .prefetch_related("items__compound", "items__supplement")
        .first()
    )


def item_scheduled_on(item, on_date) -> bool:
    """Whether a protocol item is scheduled on ``on_date`` (mirrors the frontend
    isScheduledToday). PRN items are never auto-reminded."""
    from apps.protocols.services import dose_anchor, scheduled_dose_dates

    if item.frequency in ("prn", "as_needed"):
        return False
    # Phase interval cadences (eod / every-3 / weekly) to the same anchor as the rest
    # of the app — the protocol's start, else the fixed epoch. Falling back to `on_date`
    # would make the cadence collapse to "every day" (delta 0) when started_on is unset.
    anchor = dose_anchor(item.protocol)
    return bool(scheduled_dose_dates(item.frequency, item.days_of_week, on_date, on_date, anchor))


def slot_pending_items(user, slot, on_date) -> list[str]:
    """Names of active-protocol items due at ``slot`` on ``on_date`` that haven't
    been logged enough times yet today."""
    from apps.protocols.models import DoseLog

    protocol = _active_protocol(user)
    if protocol is None:
        return []
    pending: list[str] = []
    cutoff = SLOT_ORDER.get(slot, 0)
    for item in protocol.items.all():
        times = item.times_of_day or []
        if slot not in times or not item_scheduled_on(item, on_date):
            continue
        # Doses you should have taken by this slot = item's times at/<= this slot.
        expected_by_now = sum(1 for t in times if SLOT_ORDER.get(t, 0) <= cutoff)
        if item.compound_id is not None:
            logged = DoseLog.objects.filter(
                owner=user, taken_at__date=on_date, compound_id=item.compound_id
            ).count()
            name = item.compound.name
        elif item.supplement_id is not None:
            logged = DoseLog.objects.filter(
                owner=user, taken_at__date=on_date, supplement_id=item.supplement_id
            ).count()
            name = item.supplement.name
        else:
            continue
        if logged < expected_by_now:
            pending.append(name)
    return pending


def send_slot_reminder(user, slot, on_date) -> bool:
    """Send (if anything is pending) and record the slot reminder. Records a
    dispatch row either way, so each slot fires at most once per day."""
    from .models import ReminderDispatch, ReminderSettings

    pending = slot_pending_items(user, slot, on_date)
    sent = False
    if pending:
        rs = ReminderSettings.objects.filter(owner=user).first()
        label = rs.label(slot) if rs else SLOT_LABELS.get(slot, slot)
        sent = ha_notify(
            "Dose reminder",
            f"{label}: don't forget {', '.join(pending)}.",
        )
    ReminderDispatch.objects.get_or_create(
        owner=user, slot=slot, sent_on=on_date, defaults={"items": ", ".join(pending)[:255]}
    )
    return sent


# --- Rest-timer reminders -----------------------------------------------------


def dispatch_rest_reminders(now=None) -> int:
    """Fire any due 'rest over' notifications. Returns the count sent."""
    from .models import RestReminder

    now = now or timezone.now()
    due = list(RestReminder.objects.filter(fire_at__lte=now))
    data = {"push": {"sound": "Bell.wav"}}
    for reminder in due:
        ha_notify("BBTracker", "Rest over — time for your next set.", data=data)
        reminder.delete()
    return len(due)


# --- Worker entry point -------------------------------------------------------


def _user_local_now(user, now):
    """`now` (aware UTC) in the user's profile timezone (falls back to UTC)."""
    tz_name = getattr(getattr(user, "profile", None), "timezone", None) or "UTC"
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except (zoneinfo.ZoneInfoNotFoundError, ValueError):
        tz = zoneinfo.ZoneInfo("UTC")
    return now.astimezone(tz)


def dispatch_slot_reminders(now=None) -> int:
    """Fire due daily dose-slot reminders across users with an active protocol.

    Settings are auto-created (with defaults) for those users, so reminders work
    out of the box. Returns the count of notifications sent."""
    from django.contrib.auth import get_user_model

    from .models import ReminderDispatch, ReminderSettings

    now = now or timezone.now()
    user_model = get_user_model()
    sent = 0
    users = (
        user_model.objects.filter(protocols__is_active=True)
        .distinct()
        .select_related("profile")
    )
    for user in users:
        prefs, _ = ReminderSettings.objects.get_or_create(owner=user)
        if not prefs.enabled:
            continue
        local = _user_local_now(user, now)
        today = local.date()
        for slot in SLOTS:
            slot_time = prefs.slot_time(slot)
            if slot_time is None:
                continue
            slot_dt = datetime.datetime.combine(today, slot_time, tzinfo=local.tzinfo)
            delta = (local - slot_dt).total_seconds()
            if delta < 0 or delta > SLOT_GRACE_MINUTES * 60:
                continue  # not yet, or past the grace window
            if ReminderDispatch.objects.filter(owner=user, slot=slot, sent_on=today).exists():
                continue
            if send_slot_reminder(user, slot, today):
                sent += 1
    return sent


def dispatch_protocol_activation(now=None) -> int:
    """Activate each owner's timeline-prescribed protocol, so a future-dated phase
    adjustment takes effect automatically on its effective date (in the owner's own
    timezone). Returns the number of owners whose active protocol changed."""
    from django.contrib.auth import get_user_model

    from apps.core.models import PhaseAdjustment
    from apps.protocols.services import sync_active_protocol

    now = now or timezone.now()
    user_model = get_user_model()
    owner_ids = (
        PhaseAdjustment.objects.filter(protocol__isnull=False)
        .values_list("phase__owner_id", flat=True)
        .distinct()
    )
    changed = 0
    for user in user_model.objects.filter(id__in=owner_ids).select_related("profile"):
        if sync_active_protocol(user, _user_local_now(user, now).date()):
            changed += 1
    return changed


def run_due(now=None) -> dict:
    """One worker pass: roll forward auto-activation, then fire due reminders.

    Activation runs first so a phase adjustment that kicks in today drives this same
    pass's dose-slot reminders.
    """
    now = now or timezone.now()
    return {
        "activated": dispatch_protocol_activation(now),
        "rest": dispatch_rest_reminders(now),
        "slots": dispatch_slot_reminders(now),
    }
