"""Full per-user data export.

Bundles everything an owner has logged into a single zip: a complete machine-
readable `data.json`, human-friendly denormalised CSVs for the common logs, the
progress-photo image files, and a README. Owner-scoped only — global/seeded
reference rows are included by reference (id→name) so the JSON resolves.
"""
from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import date

from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone


def _rows(qs, *fields):
    """Owner data as plain dicts (all fields, or a subset)."""
    return list(qs.values(*fields)) if fields else list(qs.values())


def _csv(rows, header):
    """Render rows (list of lists) as CSV text with a header."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue()


def build_export(user, include_photos: bool = True):
    """Return (filename, BytesIO zip) of all the user's data."""
    from apps.accounts.models import Profile
    from apps.analysis.models import BodyMeasurement
    from apps.core.models import Phase, PhaseAdjustment
    from apps.diary.models import CheckIn, ProgressPhoto
    from apps.diary.storage import get_storage
    from apps.notifications.models import ReminderSettings
    from apps.nutrition.models import (
        DiaryEntry,
        Food,
        FoodNutrient,
        Meal,
        Nutrient,
        NutrientTarget,
        NutritionTarget,
        Recipe,
        RecipeItem,
        ServingSize,
    )
    from apps.protocols.models import (
        BloodMarker,
        BloodPressureLog,
        BloodResult,
        Compound,
        DoseLog,
        Protocol,
        ProtocolItem,
        Supplement,
        SupplementNutrient,
        Vial,
    )
    from apps.training.models import (
        Exercise,
        ExerciseSlot,
        LoggedExercise,
        LoggedSet,
        PlannedSet,
        Program,
        TrainingDay,
        WorkoutSession,
    )

    data: dict = {
        "profile": _rows(Profile.objects.filter(user=user)),
        "phases": _rows(Phase.objects.filter(owner=user)),
        "phase_adjustments": _rows(PhaseAdjustment.objects.filter(phase__owner=user)),
        "check_ins": _rows(CheckIn.objects.filter(owner=user)),
        "body_measurements": _rows(BodyMeasurement.objects.filter(owner=user)),
        "foods_custom": _rows(Food.objects.filter(owner=user)),
        "serving_sizes": _rows(ServingSize.objects.filter(food__owner=user)),
        "food_nutrients": _rows(FoodNutrient.objects.filter(food__owner=user)),
        "nutrition_targets": _rows(NutritionTarget.objects.filter(owner=user)),
        "nutrient_targets": _rows(NutrientTarget.objects.filter(target__owner=user)),
        "meals": _rows(Meal.objects.filter(owner=user)),
        "diary_entries": _rows(DiaryEntry.objects.filter(owner=user)),
        "recipes": _rows(Recipe.objects.filter(owner=user)),
        "recipe_items": _rows(RecipeItem.objects.filter(recipe__owner=user)),
        "programs": _rows(Program.objects.filter(owner=user)),
        "training_days": _rows(TrainingDay.objects.filter(program__owner=user)),
        "exercise_slots": _rows(ExerciseSlot.objects.filter(day__program__owner=user)),
        "planned_sets": _rows(PlannedSet.objects.filter(slot__day__program__owner=user)),
        "exercises_custom": _rows(Exercise.objects.filter(owner=user)),
        "workout_sessions": _rows(WorkoutSession.objects.filter(owner=user)),
        "logged_exercises": _rows(LoggedExercise.objects.filter(session__owner=user)),
        "logged_sets": _rows(LoggedSet.objects.filter(logged_exercise__session__owner=user)),
        "compounds_custom": _rows(Compound.objects.filter(owner=user)),
        "supplements_custom": _rows(Supplement.objects.filter(owner=user)),
        "supplement_nutrients": _rows(SupplementNutrient.objects.filter(supplement__owner=user)),
        "protocols": _rows(Protocol.objects.filter(owner=user)),
        "protocol_items": _rows(ProtocolItem.objects.filter(protocol__owner=user)),
        "dose_logs": _rows(DoseLog.objects.filter(owner=user)),
        "vials": _rows(Vial.objects.filter(owner=user)),
        "blood_results": _rows(BloodResult.objects.filter(owner=user)),
        "blood_pressure_logs": _rows(BloodPressureLog.objects.filter(owner=user)),
        "progress_photos": _rows(ProgressPhoto.objects.filter(owner=user)),
        "reminder_settings": _rows(ReminderSettings.objects.filter(owner=user)),
    }

    # Referenced global/seeded rows, so FK ids in the dump resolve to names.
    def _idset(qs, field):
        return set(qs.values_list(field, flat=True))

    ex_ids = _idset(LoggedExercise.objects.filter(session__owner=user), "exercise_id")
    ex_ids |= _idset(ExerciseSlot.objects.filter(day__program__owner=user), "exercise_id")
    cmp_ids = _idset(DoseLog.objects.filter(owner=user, compound__isnull=False), "compound_id")
    cmp_ids |= _idset(
        ProtocolItem.objects.filter(protocol__owner=user, compound__isnull=False), "compound_id"
    )
    supp_ids = _idset(DoseLog.objects.filter(owner=user, supplement__isnull=False), "supplement_id")
    supp_ids |= _idset(
        ProtocolItem.objects.filter(protocol__owner=user, supplement__isnull=False), "supplement_id"
    )
    food_ids = _idset(DiaryEntry.objects.filter(owner=user, food__isnull=False), "food_id")
    food_ids |= _idset(RecipeItem.objects.filter(recipe__owner=user), "food_id")
    marker_ids = _idset(BloodResult.objects.filter(owner=user), "marker_id")
    data["reference"] = {
        "exercises": _rows(
            Exercise.objects.filter(id__in=ex_ids), "id", "name", "load_type", "category"
        ),
        "compounds": _rows(
            Compound.objects.filter(id__in=cmp_ids),
            "id", "name", "compound_class", "default_unit", "half_life_hours",
        ),
        "supplements": _rows(Supplement.objects.filter(id__in=supp_ids), "id", "name", "brand"),
        "foods": _rows(Food.objects.filter(id__in=food_ids), "id", "name", "brand", "unit"),
        "blood_markers": _rows(
            BloodMarker.objects.filter(id__in=marker_ids), "id", "name", "slug", "unit"
        ),
        "nutrients": _rows(Nutrient.objects.all(), "id", "slug", "name", "unit"),
    }

    counts = {k: len(v) for k, v in data.items() if isinstance(v, list)}
    manifest = {
        "app": "BBTracker",
        "generated_at": timezone.now().isoformat(),
        "user": user.email,
        "counts": counts,
    }

    # --- denormalised CSVs (human/spreadsheet friendly) ---
    csvs: dict[str, str] = {}
    csvs["check_ins.csv"] = _csv(
        [
            [c.date, c.bodyweight, c.systolic, c.diastolic, c.pulse,
             c.energy, c.sleep, c.mood, c.motivation, c.soreness, c.notes]
            for c in CheckIn.objects.filter(owner=user).order_by("date")
        ],
        ["date", "bodyweight", "systolic", "diastolic", "pulse",
         "energy", "sleep", "mood", "motivation", "soreness", "notes"],
    )
    csvs["body_measurements.csv"] = _csv(
        [
            [m.date, m.type, m.value, m.method, m.notes]
            for m in BodyMeasurement.objects.filter(owner=user).order_by("date")
        ],
        ["date", "type", "value", "method", "notes"],
    )
    csvs["blood_results.csv"] = _csv(
        [
            [r.measured_on, r.marker.name, r.value, r.unit or r.marker.unit,
             r.ref_low, r.ref_high, r.source, r.notes]
            for r in BloodResult.objects.filter(owner=user)
            .select_related("marker").order_by("measured_on")
        ],
        ["measured_on", "marker", "value", "unit", "ref_low", "ref_high", "source", "notes"],
    )
    csvs["dose_logs.csv"] = _csv(
        [
            [d.taken_at.isoformat(),
             "compound" if d.compound_id else "supplement",
             (d.compound.name if d.compound_id else (d.supplement.name if d.supplement_id else "")),
             d.amount, d.unit, d.route,
             (d.injection_site.name if d.injection_site_id else ""), d.status, d.notes]
            for d in DoseLog.objects.filter(owner=user)
            .select_related("compound", "supplement", "injection_site").order_by("taken_at")
        ],
        ["taken_at", "kind", "name", "amount", "unit", "route",
         "injection_site", "status", "notes"],
    )
    csvs["training_sets.csv"] = _csv(
        [
            [s.logged_exercise.session.started_at.date(), s.logged_exercise.exercise.name,
             s.set_type, s.weight, s.reps, s.rir, s.e1rm, s.is_pr]
            for s in LoggedSet.objects.filter(logged_exercise__session__owner=user)
            .select_related("logged_exercise__exercise", "logged_exercise__session")
            .order_by("logged_exercise__session__started_at", "logged_exercise__order", "order")
        ],
        ["date", "exercise", "set_type", "weight", "reps", "rir", "e1rm", "is_pr"],
    )
    csvs["diary_entries.csv"] = _csv(
        [
            [e.date, (e.meal.name if e.meal_id else ""),
             (e.food.name if e.food_id else (e.recipe.name if e.recipe_id else "")),
             e.quantity, e.grams]
            for e in DiaryEntry.objects.filter(owner=user)
            .select_related("meal", "food", "recipe").order_by("date")
        ],
        ["date", "meal", "item", "quantity", "grams"],
    )
    csvs["blood_pressure.csv"] = _csv(
        [
            [b.measured_at.isoformat(), b.systolic, b.diastolic, b.pulse, b.notes]
            for b in BloodPressureLog.objects.filter(owner=user).order_by("measured_at")
        ],
        ["measured_at", "systolic", "diastolic", "pulse", "notes"],
    )

    readme = (
        "BBTracker data export\n"
        f"Generated: {manifest['generated_at']}\n"
        f"Account: {user.email}\n\n"
        "Contents:\n"
        "- data.json   Complete machine-readable dump of all your data (one section\n"
        "              per table; a 'reference' section resolves global ids to names).\n"
        "- csv/        Denormalised spreadsheet-friendly copies of the common logs.\n"
        "- photos/     Your progress photo image files.\n\n"
        "This is your own data, exported for backup/portability. Not medical advice.\n"
    )

    # --- assemble the zip ---
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, cls=DjangoJSONEncoder))
        zf.writestr("data.json", json.dumps(data, indent=2, cls=DjangoJSONEncoder))
        zf.writestr("README.txt", readme)
        for name, text in csvs.items():
            zf.writestr(f"csv/{name}", text)
        if include_photos:
            storage = get_storage()
            for p in ProgressPhoto.objects.filter(owner=user).select_related("pose"):
                if not p.object_key:
                    continue
                try:
                    blob = storage.get(p.object_key)
                except Exception:
                    continue
                pose = p.pose.slug if p.pose_id else "freeform"
                zf.writestr(f"photos/{p.taken_on}_{pose}_{p.id}.jpg", blob)

    buf.seek(0)
    filename = f"bbtracker-export-{date.today().isoformat()}.zip"
    return filename, buf
