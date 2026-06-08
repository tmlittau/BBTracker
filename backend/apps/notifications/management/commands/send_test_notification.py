"""Send a one-off test notification through Home Assistant to verify the wiring."""
from django.core.management.base import BaseCommand

from apps.notifications.services import ha_configured, ha_notify


class Command(BaseCommand):
    help = "Send a test notification via Home Assistant (verifies HA_* config)."

    def handle(self, *args, **opts):
        if not ha_configured():
            self.stdout.write(self.style.ERROR("HA_BASE_URL / HA_TOKEN are not set."))
            return
        ok = ha_notify("BBTracker", "Test notification — Home Assistant wiring works.")
        self.stdout.write(
            self.style.SUCCESS("Sent.") if ok else self.style.ERROR("Failed — check logs.")
        )
