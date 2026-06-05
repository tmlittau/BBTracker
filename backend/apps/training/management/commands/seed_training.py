"""Idempotent seed of reference data: muscles + a starter global exercise library.

Run:  python manage.py seed_training
Safe to run repeatedly (get_or_create on stable slugs/names).
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.training.enums import ExerciseCategory, LoadType
from apps.training.models import Exercise, Muscle

MUSCLES = [
    ("Chest", "chest"),
    ("Upper back", "back"),
    ("Lats", "back"),
    ("Lower back", "back"),
    ("Traps", "back"),
    ("Front delts", "shoulders"),
    ("Side delts", "shoulders"),
    ("Rear delts", "shoulders"),
    ("Biceps", "arms"),
    ("Triceps", "arms"),
    ("Forearms", "arms"),
    ("Quads", "legs"),
    ("Hamstrings", "legs"),
    ("Glutes", "legs"),
    ("Calves", "legs"),
    ("Abs", "core"),
    ("Obliques", "core"),
]

# (name, category, load_type, [primary], [secondary])
EXERCISES = [
    ("Barbell Bench Press", ExerciseCategory.BARBELL, LoadType.WEIGHT_REPS,
     ["Chest"], ["Front delts", "Triceps"]),
    ("Incline Barbell Bench Press", ExerciseCategory.BARBELL, LoadType.WEIGHT_REPS,
     ["Chest"], ["Front delts", "Triceps"]),
    ("Dumbbell Bench Press", ExerciseCategory.DUMBBELL, LoadType.WEIGHT_REPS,
     ["Chest"], ["Front delts", "Triceps"]),
    ("Overhead Press", ExerciseCategory.BARBELL, LoadType.WEIGHT_REPS,
     ["Front delts"], ["Side delts", "Triceps"]),
    ("Dumbbell Shoulder Press", ExerciseCategory.DUMBBELL, LoadType.WEIGHT_REPS,
     ["Front delts"], ["Side delts", "Triceps"]),
    ("Lateral Raise", ExerciseCategory.DUMBBELL, LoadType.WEIGHT_REPS,
     ["Side delts"], []),
    ("Triceps Pushdown", ExerciseCategory.CABLE, LoadType.WEIGHT_REPS,
     ["Triceps"], []),
    ("Barbell Back Squat", ExerciseCategory.BARBELL, LoadType.WEIGHT_REPS,
     ["Quads"], ["Glutes", "Hamstrings"]),
    ("Front Squat", ExerciseCategory.BARBELL, LoadType.WEIGHT_REPS,
     ["Quads"], ["Glutes"]),
    ("Leg Press", ExerciseCategory.MACHINE, LoadType.WEIGHT_REPS,
     ["Quads"], ["Glutes", "Hamstrings"]),
    ("Romanian Deadlift", ExerciseCategory.BARBELL, LoadType.WEIGHT_REPS,
     ["Hamstrings"], ["Glutes", "Lower back"]),
    ("Conventional Deadlift", ExerciseCategory.BARBELL, LoadType.WEIGHT_REPS,
     ["Lower back"], ["Glutes", "Hamstrings", "Traps"]),
    ("Leg Curl", ExerciseCategory.MACHINE, LoadType.WEIGHT_REPS,
     ["Hamstrings"], []),
    ("Leg Extension", ExerciseCategory.MACHINE, LoadType.WEIGHT_REPS,
     ["Quads"], []),
    ("Standing Calf Raise", ExerciseCategory.MACHINE, LoadType.WEIGHT_REPS,
     ["Calves"], []),
    ("Pull-up", ExerciseCategory.BODYWEIGHT, LoadType.WEIGHTED_BODYWEIGHT,
     ["Lats"], ["Biceps", "Upper back"]),
    ("Lat Pulldown", ExerciseCategory.CABLE, LoadType.WEIGHT_REPS,
     ["Lats"], ["Biceps"]),
    ("Barbell Row", ExerciseCategory.BARBELL, LoadType.WEIGHT_REPS,
     ["Upper back"], ["Lats", "Biceps"]),
    ("Seated Cable Row", ExerciseCategory.CABLE, LoadType.WEIGHT_REPS,
     ["Upper back"], ["Lats", "Biceps"]),
    ("Face Pull", ExerciseCategory.CABLE, LoadType.WEIGHT_REPS,
     ["Rear delts"], ["Traps"]),
    ("Barbell Curl", ExerciseCategory.BARBELL, LoadType.WEIGHT_REPS,
     ["Biceps"], ["Forearms"]),
    ("Dumbbell Curl", ExerciseCategory.DUMBBELL, LoadType.WEIGHT_REPS,
     ["Biceps"], ["Forearms"]),
    ("Hanging Leg Raise", ExerciseCategory.BODYWEIGHT, LoadType.BODYWEIGHT_REPS,
     ["Abs"], ["Obliques"]),
    ("Plank", ExerciseCategory.BODYWEIGHT, LoadType.DURATION,
     ["Abs"], ["Obliques"]),
]


class Command(BaseCommand):
    help = "Seed muscles and a starter global exercise library (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        by_name: dict[str, Muscle] = {}
        for name, group in MUSCLES:
            muscle, _ = Muscle.objects.get_or_create(
                slug=slugify(name), defaults={"name": name, "group": group}
            )
            # keep name/group in sync if edited in source
            if muscle.name != name or muscle.group != group:
                muscle.name, muscle.group = name, group
                muscle.save(update_fields=["name", "group"])
            by_name[name] = muscle

        created = 0
        for name, category, load_type, primary, secondary in EXERCISES:
            exercise, was_created = Exercise.objects.get_or_create(
                owner=None,
                name=name,
                defaults={"category": category, "load_type": load_type},
            )
            if was_created:
                created += 1
            exercise.primary_muscles.set([by_name[m] for m in primary])
            exercise.secondary_muscles.set([by_name[m] for m in secondary])

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(by_name)} muscles and {len(EXERCISES)} exercises "
                f"({created} new)."
            )
        )
