"""Native local-first bootstrap snapshot.

The first native launch imports the existing relational data in the exact serializer shapes
already consumed by the iOS app. After cutover, subsequent restores use ReplicaBackup instead.
"""
import copy
from datetime import date

from django.db.models import Q
from django.utils import timezone


def upgrade_replica_snapshot(user, snapshot, fallback_snapshot=None):
    """Add protocol dose slots to backups written by pre-slot app versions.

    Old installed clients ignore unknown fields when decoding and omit them again
    on their next backup. Running this on both PUT and bootstrap keeps the rolling
    deployment safe until every device has upgraded.
    """
    if not isinstance(snapshot, dict):
        return snapshot
    upgraded = copy.deepcopy(snapshot)
    protocols = upgraded.get("protocols")
    if not isinstance(protocols, list):
        return upgraded

    from apps.notifications.models import ReminderSettings
    from apps.protocols.dose_slots import DEFAULT_DOSE_SLOTS
    from apps.protocols.models import Protocol

    relational = {
        protocol.id: protocol
        for protocol in Protocol.objects.filter(owner=user).prefetch_related("dose_slots")
    }
    fallback_protocols = {
        protocol.get("id"): protocol
        for protocol in (
            fallback_snapshot.get("protocols", [])
            if isinstance(fallback_snapshot, dict)
            else []
        )
        if isinstance(protocol, dict)
    }
    settings = ReminderSettings.objects.filter(owner=user).first()
    used_ids = {
        slot.get("id")
        for protocol in protocols
        if isinstance(protocol, dict)
        for slot in (protocol.get("dose_slots") or [])
        if isinstance(slot, dict) and isinstance(slot.get("id"), int)
    }
    next_local_id = min([value for value in used_ids if value < 0] or [0]) - 1

    for protocol_data in protocols:
        if not isinstance(protocol_data, dict):
            continue
        protocol_id = protocol_data.get("id")
        if "dose_slots" not in protocol_data:
            fallback_protocol = fallback_protocols.get(protocol_id, {})
            fallback_slots = fallback_protocol.get("dose_slots")
            if isinstance(fallback_slots, list) and fallback_slots:
                slots = copy.deepcopy(fallback_slots)
            elif (source := relational.get(protocol_id)) is not None:
                slots = [
                    {
                        "id": slot.id,
                        "protocol": protocol_id,
                        "key": slot.key,
                        "name": slot.name,
                        "reminder_time": slot.reminder_time.isoformat(),
                        "order": slot.order,
                    }
                    for slot in source.dose_slots.order_by("order", "id")
                ]
            else:
                slots = []
                for order, (key, default_name, default_time) in enumerate(DEFAULT_DOSE_SLOTS):
                    name = default_name
                    reminder_time = default_time
                    if settings is not None:
                        name = (
                            (getattr(settings, f"{key}_label", "") or "").strip()
                            or default_name
                        )
                        reminder_time = getattr(settings, key, default_time)
                    slots.append(
                        {
                            "id": next_local_id,
                            "protocol": protocol_id,
                            "key": key,
                            "name": name,
                            "reminder_time": reminder_time.isoformat(),
                            "order": order,
                        }
                    )
                    next_local_id -= 1
            protocol_data["dose_slots"] = slots
        slots = protocol_data.get("dose_slots") or []
        slots_by_key = {
            slot["key"]: slot["id"]
            for slot in slots
            if isinstance(slot, dict) and "key" in slot and "id" in slot
        }
        for item in protocol_data.get("items") or []:
            if not isinstance(item, dict) or "dose_slot_ids" in item:
                continue
            item["dose_slot_ids"] = [
                slots_by_key[key]
                for key in (item.get("times_of_day") or [])
                if key in slots_by_key
            ]
    return upgraded


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
        "dose_slots", "items__compound", "items__supplement", "items__dose_slots"
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
