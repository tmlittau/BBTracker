"""Backfill the initial phase adjustment for existing phases so each phase's
prescription timeline is well-formed from its start date (see
`core.services.seed_initial_adjustment`).

  * Phases already covered at the start are left alone (idempotent).
  * Phases with NO adjustments get the owner's currently-active plan seeded at the start.
  * Phases that already changed plans (adjustments exist, but none on/before the start)
    can't be reconstructed automatically — the pre-first-adjustment prescription was
    never recorded — so they're reported for a manual initial adjustment.

    python manage.py backfill_initial_adjustments [--email you@example.com] [--dry-run]
"""
from django.core.management.base import BaseCommand

from apps.core.models import Phase, PhaseAdjustment
from apps.core.services import seed_initial_adjustment


class Command(BaseCommand):
    help = "Seed missing initial phase adjustments; flag phases needing manual review."

    def add_arguments(self, parser):
        parser.add_argument("--email", help="Limit to one owner's phases.")
        parser.add_argument("--dry-run", action="store_true", help="Report only; no writes.")

    def handle(self, *args, **opts):
        dry = opts.get("dry_run")
        phases = Phase.objects.select_related("owner").order_by("owner_id", "start_date")
        if opts.get("email"):
            phases = phases.filter(owner__email=opts["email"])

        seeded = skipped = flagged = 0
        for phase in phases:
            label = f'{phase.owner.email}: "{phase.name}" (starts {phase.start_date})'
            if PhaseAdjustment.objects.filter(
                phase=phase, effective_date__lte=phase.start_date
            ).exists():
                skipped += 1
                continue
            if PhaseAdjustment.objects.filter(phase=phase).exists():
                # Already changed plans — the original prescription isn't recorded, so
                # don't guess; surface it for a manual initial adjustment.
                flagged += 1
                first = (
                    PhaseAdjustment.objects.filter(phase=phase)
                    .order_by("effective_date", "id")
                    .first()
                )
                self.stdout.write(self.style.WARNING(
                    f"  ⚠ needs manual initial adjustment — {label}; first adjustment is "
                    f"{first.effective_date}. Add one effective {phase.start_date} with the "
                    f"plan actually in force at the start."
                ))
                continue
            if dry:
                self.stdout.write(f"  would seed — {label}")
                seeded += 1
                continue
            if seed_initial_adjustment(phase) is not None:
                seeded += 1
                self.stdout.write(self.style.SUCCESS(f"  seeded initial adjustment — {label}"))
            else:
                skipped += 1  # nothing active to capture

        self.stdout.write(self.style.SUCCESS(
            f"Done. seeded={seeded} flagged={flagged} skipped={skipped}"
            + (" (dry run)" if dry else "")
        ))
