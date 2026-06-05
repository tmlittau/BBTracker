"""Seed the mandatory bodybuilding poses (idempotent).

Run:  python manage.py seed_diary
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.diary.enums import PoseView
from apps.diary.models import Pose

# Mandatory + relaxed poses, in conventional judging order. Relaxed-from-every-
# side, most-muscular and a generic classic pose were added in iteration 2.
POSES = [
    ("Front relaxed", PoseView.FRONT, 0),
    ("Front double biceps", PoseView.FRONT, 1),
    ("Front lat spread", PoseView.FRONT, 2),
    ("Most muscular", PoseView.FRONT, 3),
    ("Side relaxed (left)", PoseView.SIDE, 4),
    ("Side chest", PoseView.SIDE, 5),
    ("Side triceps", PoseView.SIDE, 6),
    ("Side relaxed (right)", PoseView.SIDE, 7),
    ("Abdominal and thigh", PoseView.FRONT, 8),
    ("Back relaxed", PoseView.BACK, 9),
    ("Back double biceps", PoseView.BACK, 10),
    ("Back lat spread", PoseView.BACK, 11),
    ("Classic / vacuum", PoseView.FRONT, 12),
]


class Command(BaseCommand):
    help = "Seed mandatory poses for the progress diary (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        created = 0
        for name, view, order in POSES:
            _, was_created = Pose.objects.update_or_create(
                slug=slugify(name),
                defaults={"name": name, "view": view, "order": order},
            )
            created += was_created
        self.stdout.write(
            self.style.SUCCESS(f"Seeded {len(POSES)} poses ({created} new).")
        )
