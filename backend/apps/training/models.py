"""Training domain models.

Two parallel hierarchies, intentionally decoupled:

* Template:  Program → TrainingDay → ExerciseSlot → PlannedSet
* Log:       WorkoutSession → LoggedExercise → LoggedSet

Editing a program never rewrites past workouts, and a logged workout keeps its
own copy of what was actually done. Reference data: Muscle, Exercise.
"""
from django.conf import settings
from django.db import models

from .enums import ExerciseCategory, LoadType, SetType


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Muscle(models.Model):
    """Reference table for per-muscle volume analytics."""

    class Group(models.TextChoices):
        CHEST = "chest", "Chest"
        BACK = "back", "Back"
        SHOULDERS = "shoulders", "Shoulders"
        ARMS = "arms", "Arms"
        LEGS = "legs", "Legs"
        CORE = "core", "Core"
        OTHER = "other", "Other"

    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True)
    group = models.CharField(max_length=12, choices=Group.choices, default=Group.OTHER)

    class Meta:
        ordering = ["group", "name"]

    def __str__(self):
        return self.name


class Exercise(TimeStampedModel):
    """A movement. Global (owner=None) or user-custom."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="exercises",
        help_text="Null = global/seeded exercise available to everyone.",
    )
    name = models.CharField(max_length=120)
    category = models.CharField(
        max_length=16, choices=ExerciseCategory.choices, default=ExerciseCategory.BARBELL
    )
    load_type = models.CharField(
        max_length=24, choices=LoadType.choices, default=LoadType.WEIGHT_REPS
    )
    primary_muscles = models.ManyToManyField(
        Muscle, related_name="primary_exercises", blank=True
    )
    secondary_muscles = models.ManyToManyField(
        Muscle, related_name="secondary_exercises", blank=True
    )
    equipment = models.CharField(max_length=120, blank=True)
    instructions = models.TextField(blank=True)
    is_unilateral = models.BooleanField(
        default=False, help_text="Performed one side at a time (logged load is per-side)."
    )
    rest_by_set_type = models.JSONField(
        default=dict,
        blank=True,
        help_text="Rest seconds per set type, e.g. {'working': 180, 'warmup': 60}. "
        "Missing types fall back to DEFAULT_REST_SECONDS.",
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "name"], name="uniq_exercise_owner_name"
            )
        ]

    @property
    def is_global(self) -> bool:
        return self.owner_id is None

    def __str__(self):
        return self.name


class Program(TimeStampedModel):
    """A training split/routine, e.g. 'Push/Pull/Legs'."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="programs"
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=False)

    class Meta:
        ordering = ["-is_active", "name"]

    def __str__(self):
        return self.name


class TrainingDay(models.Model):
    """A day within a program, e.g. 'Push'."""

    program = models.ForeignKey(
        Program, on_delete=models.CASCADE, related_name="days"
    )
    name = models.CharField(max_length=120)
    order = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.program.name} · {self.name}"


class ExerciseSlot(models.Model):
    """An exercise's place within a training day (planned)."""

    day = models.ForeignKey(
        TrainingDay, on_delete=models.CASCADE, related_name="slots"
    )
    exercise = models.ForeignKey(
        Exercise, on_delete=models.PROTECT, related_name="slots"
    )
    order = models.PositiveIntegerField(default=0)
    notes = models.CharField(max_length=255, blank=True)
    # Slots sharing a non-null group id on the same day form a superset/giant set.
    superset_group = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.day.name} · {self.exercise.name}"


class PlannedSet(models.Model):
    """A target set for a slot: type + targets (reps/load/intensity/tempo/rest)."""

    slot = models.ForeignKey(
        ExerciseSlot, on_delete=models.CASCADE, related_name="planned_sets"
    )
    order = models.PositiveIntegerField(default=0)
    set_type = models.CharField(
        max_length=16, choices=SetType.choices, default=SetType.WORKING
    )
    target_reps_low = models.PositiveIntegerField(null=True, blank=True)
    target_reps_high = models.PositiveIntegerField(null=True, blank=True)
    target_weight = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True
    )
    target_pct_1rm = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    target_rir = models.PositiveIntegerField(null=True, blank=True)
    tempo = models.CharField(max_length=12, blank=True, help_text="e.g. '3-1-1-0'")
    rest_seconds = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.slot.exercise.name} · planned {self.set_type}"


class WorkoutSession(TimeStampedModel):
    """A performed (or in-progress) workout."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workout_sessions"
    )
    # Snapshot link to the template day; nullable for freeform sessions. SET_NULL so
    # deleting a program never destroys workout history.
    day = models.ForeignKey(
        TrainingDay, on_delete=models.SET_NULL, null=True, blank=True, related_name="sessions"
    )
    name = models.CharField(max_length=120, blank=True)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    bodyweight = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [models.Index(fields=["owner", "started_at"])]

    @property
    def is_completed(self) -> bool:
        return self.ended_at is not None

    def __str__(self):
        return self.name or f"Workout {self.started_at:%Y-%m-%d}"


class LoggedExercise(models.Model):
    """An exercise performed in a session (its own record, not a template ref)."""

    session = models.ForeignKey(
        WorkoutSession, on_delete=models.CASCADE, related_name="logged_exercises"
    )
    exercise = models.ForeignKey(
        Exercise, on_delete=models.PROTECT, related_name="logged_exercises"
    )
    order = models.PositiveIntegerField(default=0)
    superset_group = models.PositiveIntegerField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.session} · {self.exercise.name}"


class LoggedSet(models.Model):
    """An actual set performed. `is_pr`/`e1rm` are cached, computed on save via services."""

    logged_exercise = models.ForeignKey(
        LoggedExercise, on_delete=models.CASCADE, related_name="sets"
    )
    order = models.PositiveIntegerField(default=0)
    set_type = models.CharField(
        max_length=16, choices=SetType.choices, default=SetType.WORKING
    )
    reps = models.PositiveIntegerField(null=True, blank=True)
    weight = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    rir = models.PositiveIntegerField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    distance_m = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    # Seconds to rest after this set; carried from the plan (or defaulted by set
    # type) so the live logger can start a countdown when the set is logged.
    rest_seconds = models.PositiveIntegerField(null=True, blank=True)
    is_completed = models.BooleanField(default=True)
    # Cached analytics (filled by services.recompute_set_metrics).
    e1rm = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    is_pr = models.BooleanField(default=False)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.set_type} {self.weight or '—'}×{self.reps or '—'}"
