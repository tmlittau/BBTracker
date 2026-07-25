"""Native local-first bootstrap snapshot.

The first native launch imports the existing relational data in the exact serializer shapes
already consumed by the iOS app. After cutover, subsequent restores use ReplicaBackup instead.
"""
from datetime import date

from django.db.models import Q
from django.utils import timezone


def build_replica_snapshot(user):
    from apps.accounts.serializers import UserSerializer
    from apps.analysis.services import body_analysis
    from apps.core.models import Phase
    from apps.core.serializers import PhaseSerializer
    from apps.diary.models import CheckIn
    from apps.diary.serializers import CheckInSerializer
    from apps.health.models import HealthDailyAggregate
    from apps.health.serializers import HealthDailyAggregateSerializer
    from apps.notifications.models import ReminderSettings
    from apps.notifications.serializers import ReminderSettingsSerializer
    from apps.nutrition.models import DiaryEntry, Food, Meal, Nutrient, NutritionTarget
    from apps.nutrition.serializers import (
        DiaryEntrySerializer,
        FoodSerializer,
        MealSerializer,
        NutrientSerializer,
        NutritionTargetSerializer,
    )
    from apps.protocols.models import (
        BloodMarker,
        BloodResult,
        Compound,
        DoseLog,
        InjectionSite,
        Protocol,
        Supplement,
    )
    from apps.protocols.serializers import (
        BloodMarkerSerializer,
        BloodResultSerializer,
        CompoundSerializer,
        DoseLogSerializer,
        InjectionSiteSerializer,
        ProtocolSerializer,
        SupplementSerializer,
    )
    from apps.training.models import Exercise, Muscle, Program, WorkoutSession
    from apps.training.serializers import (
        ExerciseSerializer,
        MuscleSerializer,
        ProgramSerializer,
        WorkoutSessionSerializer,
    )

    phases = Phase.objects.filter(owner=user).prefetch_related(
        "adjustments__nutrition_target", "adjustments__program", "adjustments__protocol"
    )
    exercises = Exercise.objects.filter(Q(owner__isnull=True) | Q(owner=user)).prefetch_related(
        "primary_muscles", "secondary_muscles"
    )
    programs = Program.objects.filter(owner=user).prefetch_related(
        "days__slots__exercise", "days__slots__planned_sets"
    )
    sessions = WorkoutSession.objects.filter(owner=user).prefetch_related(
        "logged_exercises__exercise", "logged_exercises__sets"
    )
    foods = Food.objects.filter(Q(owner__isnull=True) | Q(owner=user)).prefetch_related(
        "servings", "food_nutrients__nutrient"
    )
    targets = NutritionTarget.objects.filter(owner=user).prefetch_related("nutrient_targets")
    entries = DiaryEntry.objects.filter(owner=user).select_related(
        "meal", "food", "recipe", "serving"
    )
    compounds = Compound.objects.filter(Q(owner__isnull=True) | Q(owner=user))
    supplements = Supplement.objects.filter(
        Q(owner__isnull=True) | Q(owner=user)
    ).prefetch_related("supplement_nutrients__nutrient")
    protocols = Protocol.objects.filter(owner=user).prefetch_related(
        "items__compound", "items__supplement"
    )
    doses = DoseLog.objects.filter(owner=user).select_related(
        "compound", "supplement", "injection_site"
    )
    blood_results = BloodResult.objects.filter(owner=user).select_related("marker")
    reminder_settings, _ = ReminderSettings.objects.get_or_create(owner=user)
    health_aggregates = HealthDailyAggregate.objects.filter(owner=user)
    health_last_sync_at = (
        health_aggregates.order_by("-updated_at")
        .values_list("updated_at", flat=True)
        .first()
    )

    return {
        "schema_version": 1,
        "generated_at": timezone.now(),
        "user": UserSerializer(user).data,
        "phases": PhaseSerializer(phases, many=True).data,
        "check_ins": CheckInSerializer(CheckIn.objects.filter(owner=user), many=True).data,
        "body_analysis": body_analysis(user, date.today()),
        "muscles": MuscleSerializer(Muscle.objects.all(), many=True).data,
        "exercises": ExerciseSerializer(exercises, many=True).data,
        "programs": ProgramSerializer(programs, many=True).data,
        "workout_sessions": WorkoutSessionSerializer(sessions, many=True).data,
        "nutrients": NutrientSerializer(Nutrient.objects.all(), many=True).data,
        "foods": FoodSerializer(foods, many=True).data,
        "nutrition_targets": NutritionTargetSerializer(targets, many=True).data,
        "meals": MealSerializer(Meal.objects.filter(owner=user), many=True).data,
        "diary_entries": DiaryEntrySerializer(entries, many=True).data,
        "compounds": CompoundSerializer(compounds, many=True).data,
        "supplements": SupplementSerializer(supplements, many=True).data,
        "injection_sites": InjectionSiteSerializer(InjectionSite.objects.all(), many=True).data,
        "blood_markers": BloodMarkerSerializer(BloodMarker.objects.all(), many=True).data,
        "protocols": ProtocolSerializer(protocols, many=True).data,
        "dose_logs": DoseLogSerializer(doses, many=True).data,
        "blood_results": BloodResultSerializer(blood_results, many=True).data,
        "reminder_settings": ReminderSettingsSerializer(reminder_settings).data,
        "health_data": {
            "aggregates": HealthDailyAggregateSerializer(health_aggregates, many=True).data,
            "last_sync_at": health_last_sync_at,
        },
    }


def apply_replica_settings(user, snapshot):
    """Mirror native-owned settings into relational rows for the legacy web UI/workers."""
    from apps.accounts.serializers import UserSerializer
    from apps.notifications.models import ReminderSettings
    from apps.notifications.serializers import ReminderSettingsSerializer

    user_data = snapshot.get("user")
    if isinstance(user_data, dict):
        update = {}
        if "first_name" in user_data:
            update["first_name"] = user_data["first_name"]
        if isinstance(user_data.get("profile"), dict):
            update["profile"] = user_data["profile"]
        if update:
            serializer = UserSerializer(user, data=update, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()

    reminder_data = snapshot.get("reminder_settings")
    if isinstance(reminder_data, dict):
        reminder_settings, _ = ReminderSettings.objects.get_or_create(owner=user)
        serializer = ReminderSettingsSerializer(
            reminder_settings,
            data=reminder_data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()


def apply_replica_health(user, snapshot):
    """Project a complete native HealthKit aggregate snapshot into relational rows."""
    from apps.health.services import apply_health_aggregate_rows

    health_data = snapshot.get("health_data")
    if not isinstance(health_data, dict):
        return
    aggregates = health_data.get("aggregates")
    if isinstance(aggregates, list):
        apply_health_aggregate_rows(user, aggregates, replace=True)
