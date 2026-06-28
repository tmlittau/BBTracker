"""Delete a user and ALL of their data, by email.

Unlike the admin's default delete (which refuses when the user's own dose logs /
protocol items PROTECT-reference their custom compounds), this tears down the
protecting rows first, then the user:

    python manage.py delete_user --email someone@example.com --dry-run
    python manage.py delete_user --email someone@example.com
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.services import hard_delete_user


class Command(BaseCommand):
    help = "Delete a user and all their data (handles PROTECT'd custom library items)."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True, help="Email of the user to delete.")
        parser.add_argument(
            "--dry-run", action="store_true", help="Show what would be deleted; delete nothing."
        )

    def handle(self, *args, **opts):
        user_model = get_user_model()
        try:
            user = user_model.objects.get(email__iexact=opts["email"])
        except user_model.DoesNotExist as exc:
            raise CommandError(f"No user with email {opts['email']!r}.") from exc

        if opts["dry_run"]:
            from apps.diary.models import CheckIn, ProgressPhoto
            from apps.nutrition.models import DiaryEntry, Food
            from apps.protocols.models import Compound, DoseLog, Supplement
            from apps.training.models import Exercise, WorkoutSession

            counts = {
                "dose logs": DoseLog.objects.filter(owner=user).count(),
                "workouts": WorkoutSession.objects.filter(owner=user).count(),
                "diary entries": DiaryEntry.objects.filter(owner=user).count(),
                "check-ins": CheckIn.objects.filter(owner=user).count(),
                "photos": ProgressPhoto.objects.filter(owner=user).count(),
                "custom compounds": Compound.objects.filter(owner=user).count(),
                "custom supplements": Supplement.objects.filter(owner=user).count(),
                "custom foods": Food.objects.filter(owner=user).count(),
                "custom exercises": Exercise.objects.filter(owner=user).count(),
            }
            self.stdout.write(f"Would delete {user.email} and (among others):")
            for label, n in counts.items():
                self.stdout.write(f"  {n:>6}  {label}")
            return

        hard_delete_user(user)
        self.stdout.write(self.style.SUCCESS(f"Deleted {opts['email']} and all their data."))
