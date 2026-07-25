"""Reminder settings + dispatch tracking for Home Assistant notifications.

The app is web-only, so notifications that must fire while the phone is locked
are sent from the backend (a small worker loop) through the user's Home Assistant
notify service. These are personal nudges, not medical advice.
"""
import datetime

from django.conf import settings
from django.db import models


def _t(hour, minute=0):
    return datetime.time(hour, minute)


# Canonical time-of-day slots + their default display names. Users can rename the
# slots (the keys never change) in their reminder settings.
SLOT_KEYS = ["waking", "am", "noon", "pm", "night"]
DEFAULT_SLOT_LABELS = {"waking": "Waking", "am": "AM", "noon": "Noon", "pm": "PM", "night": "Night"}


class ReminderSettings(models.Model):
    """Per-user notification preferences. Slot times are in the user's profile
    timezone (accounts.Profile.timezone); slot *labels* are user-customisable
    display names (blank → the default for that slot)."""

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reminder_settings"
    )
    enabled = models.BooleanField(default=True, help_text="Master switch for dose reminders.")
    rest_enabled = models.BooleanField(default=True, help_text="Notify when a rest timer ends.")
    waking = models.TimeField(default=_t(6, 30))
    am = models.TimeField(default=_t(10, 0))
    noon = models.TimeField(default=_t(15, 0))
    pm = models.TimeField(default=_t(19, 0))
    night = models.TimeField(default=_t(21, 0))
    # Optional custom display names for the slots (blank → DEFAULT_SLOT_LABELS).
    waking_label = models.CharField(max_length=24, blank=True)
    am_label = models.CharField(max_length=24, blank=True)
    noon_label = models.CharField(max_length=24, blank=True)
    pm_label = models.CharField(max_length=24, blank=True)
    night_label = models.CharField(max_length=24, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def slot_time(self, slot):
        return getattr(self, slot, None)

    def label(self, slot):
        custom = (getattr(self, f"{slot}_label", "") or "").strip()
        return custom or DEFAULT_SLOT_LABELS.get(slot, slot)

    def labels(self):
        return {slot: self.label(slot) for slot in SLOT_KEYS}

    def __str__(self):
        return f"ReminderSettings(owner={self.owner_id})"


class DeviceToken(models.Model):
    """An APNs address for one installed iOS app.

    Apple may rotate a token at any time, so registration is an idempotent upsert
    and ``last_seen`` is refreshed whenever the app launches.
    """

    class Environment(models.TextChoices):
        SANDBOX = "sandbox", "Sandbox"
        PRODUCTION = "production", "Production"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="device_tokens"
    )
    token = models.CharField(max_length=200, unique=True)
    platform = models.CharField(max_length=8, default="ios")
    environment = models.CharField(
        max_length=12,
        choices=Environment.choices,
        default=Environment.PRODUCTION,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_seen"]

    def __str__(self):
        return f"{self.owner_id} ios/{self.environment} {self.token[:12]}…"


class ReminderDispatch(models.Model):
    """One row per (user, slot, day) once that slot has been handled — prevents
    re-sending the same slot reminder multiple times in a day."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reminder_dispatches"
    )
    slot = models.CharField(max_length=12)
    sent_on = models.DateField()
    items = models.CharField(max_length=255, blank=True)  # what was reminded (audit)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "slot", "sent_on"], name="uniq_reminder_dispatch"
            )
        ]

    def __str__(self):
        return f"{self.owner_id} {self.slot} {self.sent_on}"


class RestReminder(models.Model):
    """A pending 'rest over' notification (at most one per user). Upserted when a
    rest countdown starts; deleted when it's cancelled or fired."""

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="rest_reminder"
    )
    fire_at = models.DateTimeField()

    def __str__(self):
        return f"RestReminder(owner={self.owner_id} @ {self.fire_at:%H:%M:%S})"
