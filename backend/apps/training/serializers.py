from rest_framework import serializers

from .models import (
    Exercise,
    ExerciseSlot,
    LoggedExercise,
    LoggedSet,
    Muscle,
    PlannedSet,
    Program,
    TrainingDay,
    WorkoutSession,
)
from .services import recompute_set_metrics


class MuscleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Muscle
        fields = ["id", "name", "slug", "group"]


class ExerciseSerializer(serializers.ModelSerializer):
    primary_muscles = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Muscle.objects.all(), required=False
    )
    secondary_muscles = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Muscle.objects.all(), required=False
    )
    primary_muscle_names = serializers.SerializerMethodField()
    is_global = serializers.BooleanField(read_only=True)

    class Meta:
        model = Exercise
        fields = [
            "id", "name", "category", "load_type",
            "primary_muscles", "secondary_muscles", "primary_muscle_names",
            "equipment", "instructions", "is_unilateral", "is_global",
        ]

    def get_primary_muscle_names(self, obj) -> list[str]:
        return [m.name for m in obj.primary_muscles.all()]


# --- Template hierarchy (read-nested, write-flat) ---


class PlannedSetSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlannedSet
        fields = [
            "id", "slot", "order", "set_type",
            "target_reps_low", "target_reps_high", "target_weight",
            "target_pct_1rm", "target_rir", "tempo", "rest_seconds",
        ]


class ExerciseSlotSerializer(serializers.ModelSerializer):
    planned_sets = PlannedSetSerializer(many=True, read_only=True)
    exercise_name = serializers.CharField(source="exercise.name", read_only=True)

    class Meta:
        model = ExerciseSlot
        fields = [
            "id", "day", "exercise", "exercise_name", "order",
            "notes", "superset_group", "planned_sets",
        ]


class TrainingDaySerializer(serializers.ModelSerializer):
    slots = ExerciseSlotSerializer(many=True, read_only=True)

    class Meta:
        model = TrainingDay
        fields = ["id", "program", "name", "order", "notes", "slots"]


class ProgramSerializer(serializers.ModelSerializer):
    days = TrainingDaySerializer(many=True, read_only=True)

    class Meta:
        model = Program
        fields = ["id", "name", "description", "is_active", "created_at", "days"]
        read_only_fields = ["created_at"]


# --- Log hierarchy ---


class LoggedSetSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoggedSet
        fields = [
            "id", "logged_exercise", "order", "set_type",
            "reps", "weight", "rir", "duration_seconds", "distance_m",
            "rest_seconds", "is_completed", "e1rm", "is_pr",
        ]
        read_only_fields = ["e1rm", "is_pr"]

    def save(self, **kwargs):
        instance = super().save(**kwargs)
        recompute_set_metrics(instance)
        instance.save(update_fields=["e1rm", "is_pr"])
        return instance


class LoggedExerciseSerializer(serializers.ModelSerializer):
    sets = LoggedSetSerializer(many=True, read_only=True)
    exercise_name = serializers.CharField(source="exercise.name", read_only=True)

    class Meta:
        model = LoggedExercise
        fields = [
            "id", "session", "exercise", "exercise_name",
            "order", "superset_group", "notes", "sets",
        ]


class WorkoutSessionSerializer(serializers.ModelSerializer):
    logged_exercises = LoggedExerciseSerializer(many=True, read_only=True)
    is_completed = serializers.BooleanField(read_only=True)

    class Meta:
        model = WorkoutSession
        fields = [
            "id", "day", "name", "started_at", "ended_at",
            "bodyweight", "notes", "is_completed", "logged_exercises",
        ]


class WorkoutSessionListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for the history list (no nested sets)."""

    is_completed = serializers.BooleanField(read_only=True)
    exercise_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = WorkoutSession
        fields = [
            "id", "day", "name", "started_at", "ended_at",
            "bodyweight", "is_completed", "exercise_count",
        ]


class ExerciseHistoryPointSerializer(serializers.Serializer):
    session_id = serializers.IntegerField()
    date = serializers.CharField()
    best_e1rm = serializers.DecimalField(max_digits=7, decimal_places=2, allow_null=True)
    top_weight = serializers.DecimalField(max_digits=7, decimal_places=2, allow_null=True)
    volume = serializers.DecimalField(max_digits=12, decimal_places=2)


class MuscleVolumeSerializer(serializers.Serializer):
    muscle = serializers.CharField()
    sets = serializers.IntegerField()
    tonnage = serializers.DecimalField(max_digits=12, decimal_places=2)


class ExercisePerformanceSerializer(serializers.Serializer):
    """At-a-glance logger stats: best (heaviest) set + last finished session's sets."""

    best = serializers.DictField(allow_null=True)
    last = serializers.DictField(allow_null=True)
