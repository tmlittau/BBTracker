"""Reminder worker: fire due 'rest over' + daily dose-slot notifications.

Runs as a long-lived loop (a sidecar service in docker-compose). Pass --once for
a single pass (cron / manual testing).
"""
import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.notifications.services import ha_configured, run_due


class Command(BaseCommand):
    help = "Dispatch due rest-timer and dose-slot reminders via Home Assistant."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Run a single pass and exit.")
        parser.add_argument("--interval", type=int, default=15, help="Seconds between passes.")

    def handle(self, *args, **opts):
        if not ha_configured():
            self.stdout.write(
                self.style.WARNING(
                    "Home Assistant not configured (HA_BASE_URL / HA_TOKEN) — "
                    "reminders will run but notifications no-op."
                )
            )
        if opts["once"]:
            res = run_due(timezone.now())
            self.stdout.write(
                f"Dispatched: activated={res['activated']} rest={res['rest']} slots={res['slots']}"
            )
            return

        interval = max(5, opts["interval"])
        self.stdout.write(self.style.SUCCESS(f"Reminder worker started (every {interval}s)."))
        while True:
            try:
                run_due(timezone.now())
            except Exception as exc:  # never let the loop die on a transient error
                self.stderr.write(f"reminder pass failed: {exc}")
            time.sleep(interval)
