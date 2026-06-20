"""Self-coaching aggregation: current phase, dashboard "Today", weekly check-in.

These stitch the five domains together by date. Cross-app imports are
function-local so `core` has no hard import dependency on the other apps (and they
never import `core`). Pure helpers (numeric in/out) are unit-tested; DB-aware
aggregators sit below.
"""
from __future__ import annotations

from datetime import timedelta

# --- Pure helpers -------------------------------------------------------------


def mean(values) -> float | None:
    """Arithmetic mean of the present (non-None) numbers, rounded to 1dp."""
    nums = [float(v) for v in values if v is not None]
    if not nums:
        return None
    return round(sum(nums) / len(nums), 1)


def trend(values) -> dict | None:
    """First/last/delta of an ordered numeric series (Nones skipped)."""
    nums = [float(v) for v in values if v is not None]
    if not nums:
        return None
    return {"first": nums[0], "last": nums[-1], "delta": round(nums[-1] - nums[0], 2)}


# --- DB-aware aggregators -----------------------------------------------------


def current_phase(owner, on_date):
    """The phase whose date range contains `on_date` (prefers the latest start)."""
    from django.db.models import Q

    from .models import Phase

    return (
        Phase.objects.filter(owner=owner, start_date__lte=on_date)
        .filter(Q(end_date__isnull=True) | Q(end_date__gte=on_date))
        .order_by("-start_date")
        .first()
    )


def current_phase_config(owner, on_date):
    """The covering phase plus the adjustment in force on `on_date`.

    Returns (phase, adjustment); adjustment is the latest one with
    effective_date <= on_date in that phase (or None) — it carries the nutrition
    target / program / protocol prescribed for that date.
    """
    phase = current_phase(owner, on_date)
    if phase is None:
        return None, None
    adjustment = (
        phase.adjustments.filter(effective_date__lte=on_date)
        .select_related("nutrition_target", "program", "protocol")
        .order_by("-effective_date", "-id")
        .first()
    )
    return phase, adjustment


def dashboard_today(owner, on_date):
    """Everything a coach glances at for one day, across all five domains."""
    from apps.nutrition.services import nutrition_headline
    from apps.protocols.models import DoseLog
    from apps.training.models import WorkoutSession

    phase, adjustment = current_phase_config(owner, on_date)

    nutrition = nutrition_headline(owner, on_date)

    sessions = list(
        WorkoutSession.objects.filter(owner=owner, started_at__date=on_date)
        .prefetch_related("logged_exercises__sets")
    )
    workout = None
    if sessions:
        prs = sum(
            1
            for s in sessions
            for le in s.logged_exercises.all()
            for st in le.sets.all()
            if st.is_pr
        )
        workout = {
            "count": len(sessions),
            "completed": any(s.ended_at is not None for s in sessions),
            "exercises": sum(len(s.logged_exercises.all()) for s in sessions),
            "prs": prs,
            "name": sessions[0].name or (sessions[0].day.name if sessions[0].day else "Workout"),
        }

    doses = [
        {
            "item": (d.compound or d.supplement) and str(d.compound or d.supplement),
            "amount": str(d.amount),
            "unit": d.unit,
            "site": d.injection_site.name if d.injection_site else None,
        }
        for d in DoseLog.objects.filter(owner=owner, taken_at__date=on_date)
        .select_related("compound", "supplement", "injection_site")
    ]

    return {
        "date": on_date.isoformat(),
        "phase": _phase_brief(phase, adjustment),
        "nutrition": nutrition,
        "workout": workout,
        "doses": doses,
    }


def _phase_brief(phase, adjustment=None):
    """Phase summary + the prescription resolved from its active adjustment."""
    if phase is None:
        return None
    brief = {
        "id": phase.id,
        "name": phase.name,
        "phase_type": phase.phase_type,
        "start_date": phase.start_date.isoformat(),
        "end_date": phase.end_date.isoformat() if phase.end_date else None,
        "notes": phase.notes if phase.notes else None,
        "nutrition_target_name": None,
        "program_name": None,
        "protocol_name": None,
        "adjustment_effective": None,
    }
    if adjustment is not None:
        brief["nutrition_target_name"] = (
            adjustment.nutrition_target.name if adjustment.nutrition_target else None
        )
        brief["program_name"] = adjustment.program.name if adjustment.program else None
        brief["protocol_name"] = adjustment.protocol.name if adjustment.protocol else None
        brief["adjustment_effective"] = adjustment.effective_date.isoformat()
    return brief


def weekly_checkin(owner, end_date):
    """Aggregate the trailing 7 days (end_date inclusive) across all domains.

    This is the self-coaching payload — what you'd send a coach: weight trend,
    training output, nutrition adherence, dose adherence, subjective wellbeing,
    photos taken, and the latest bloodwork.
    """
    from apps.diary.models import CheckIn, ProgressPhoto
    from apps.nutrition.services import weekly_macro_adherence
    from apps.protocols.models import BloodResult, DoseLog
    from apps.training.models import LoggedSet, WorkoutSession
    from apps.training.services import weekly_muscle_volume

    start_date = end_date - timedelta(days=6)
    window = {"date__gte": start_date, "date__lte": end_date}

    # --- Subjective + bodyweight from diary check-ins (oldest→newest) ---
    check_ins = list(
        CheckIn.objects.filter(owner=owner, **window).order_by("date")
    )
    subjective = {
        field: mean([getattr(c, field) for c in check_ins])
        for field in ("energy", "sleep", "mood", "motivation", "soreness")
    }
    bodyweight = trend([c.bodyweight for c in check_ins])

    # --- Training output over the window ---
    sessions = WorkoutSession.objects.filter(
        owner=owner, started_at__date__gte=start_date, started_at__date__lte=end_date
    )
    prs = LoggedSet.objects.filter(
        logged_exercise__session__in=sessions, is_pr=True
    ).count()
    muscle_volume = weekly_muscle_volume(
        owner, since=_as_datetime(start_date)
    )
    training = {
        "sessions": sessions.count(),
        "prs": prs,
        "working_sets": sum(v["sets"] for v in muscle_volume.values()),
        "top_muscles": sorted(
            ({"muscle": k, "sets": v["sets"]} for k, v in muscle_volume.items()),
            key=lambda r: -r["sets"],
        )[:5],
    }

    # --- Nutrition adherence (batched: one entries + one supplement query) ---
    nutrition = weekly_macro_adherence(owner, start_date, end_date)

    # --- Dose adherence (count) + photos + latest bloodwork ---
    dose_count = DoseLog.objects.filter(
        owner=owner, taken_at__date__gte=start_date, taken_at__date__lte=end_date
    ).count()
    photos = ProgressPhoto.objects.filter(
        owner=owner, taken_on__gte=start_date, taken_on__lte=end_date
    ).count()
    last_blood = (
        BloodResult.objects.filter(owner=owner).order_by("-measured_on").first()
    )

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "phase": _phase_brief(*current_phase_config(owner, end_date)),
        "bodyweight": bodyweight,
        "subjective": subjective,
        "training": training,
        "nutrition": nutrition,
        "doses": dose_count,
        "photos": photos,
        "last_bloodwork": last_blood.measured_on.isoformat() if last_blood else None,
        "check_ins": len(check_ins),
    }


def _as_datetime(d):
    """Midnight-aware datetime for `weekly_muscle_volume(since=...)`."""
    from datetime import datetime, time

    from django.utils import timezone

    return timezone.make_aware(datetime.combine(d, time.min))
