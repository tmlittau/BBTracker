"""Computed training analytics.

The core math is pure (Decimal/int in, Decimal/float out) so it is trivially
unit-testable without the ORM. Thin DB-aware wrappers at the bottom apply these
to model instances.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from .enums import COUNTED_SET_TYPES, WORKING_SET_TYPES

# Above this many reps, rep-based 1RM formulas lose accuracy; treat as not meaningful.
MAX_REPS_FOR_E1RM = 30


def epley_1rm(weight: float | Decimal, reps: int) -> Decimal | None:
    """Estimated 1RM via Epley: w * (1 + reps/30). Returns None if not applicable."""
    return _e1rm(weight, reps, lambda w, r: w * (1 + r / 30))


def brzycki_1rm(weight: float | Decimal, reps: int) -> Decimal | None:
    """Estimated 1RM via Brzycki: w * 36 / (37 - reps)."""
    return _e1rm(weight, reps, lambda w, r: w * 36 / (37 - r) if r < 37 else None)


def _e1rm(weight, reps, fn) -> Decimal | None:
    if weight is None or reps is None:
        return None
    w = float(weight)
    if w <= 0 or reps <= 0 or reps > MAX_REPS_FOR_E1RM:
        return None
    if reps == 1:
        return _round2(w)
    val = fn(w, reps)
    return _round2(val) if val and val > 0 else None


def estimated_1rm(weight, reps) -> Decimal | None:
    """Default e1RM used across the app (Epley — simple and widely used)."""
    return epley_1rm(weight, reps)


def _round2(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def is_working_set(set_type: str) -> bool:
    return set_type in WORKING_SET_TYPES


def counts_as_set(set_type: str) -> bool:
    """Whether a set is tallied as a discrete hard set for weekly set counts."""
    return set_type in COUNTED_SET_TYPES


def rest_seconds_for(exercise, set_type: str) -> int:
    """Rest (seconds) configured on the exercise for this set type, else the default."""
    from .enums import DEFAULT_REST_SECONDS

    value = (exercise.rest_by_set_type or {}).get(set_type)
    return int(value) if isinstance(value, (int, float)) and value > 0 else DEFAULT_REST_SECONDS


def set_volume(weight, reps, set_type: str) -> Decimal:
    """Tonnage (weight × reps) for one set; 0 for warm-ups or missing data."""
    if not is_working_set(set_type) or weight is None or reps is None:
        return Decimal("0")
    return _round2(float(weight) * reps)


# --- DB-aware wrappers ---------------------------------------------------------


def recompute_set_metrics(logged_set) -> None:
    """Fill `e1rm` and `is_pr` on a LoggedSet (does not save).

    A set is a PR if its estimated 1RM strictly exceeds every prior completed
    set of the same exercise by the same owner (earlier sessions, or earlier in
    the same session). Only weight×reps sets get an e1RM.
    """
    from .enums import LoadType

    le = logged_set.logged_exercise
    exercise = le.exercise

    if exercise.load_type in (LoadType.WEIGHT_REPS, LoadType.WEIGHTED_BODYWEIGHT):
        logged_set.e1rm = estimated_1rm(logged_set.weight, logged_set.reps)
    else:
        logged_set.e1rm = None

    logged_set.is_pr = False
    if logged_set.e1rm is None or not logged_set.is_completed:
        return

    best_prior = _best_prior_e1rm(logged_set)
    if best_prior is None or logged_set.e1rm > best_prior:
        logged_set.is_pr = True


def _best_prior_e1rm(logged_set):
    """Highest e1RM among the owner's other completed sets of the same exercise."""
    from .models import LoggedSet

    le = logged_set.logged_exercise
    qs = (
        LoggedSet.objects.filter(
            logged_exercise__exercise_id=le.exercise_id,
            logged_exercise__session__owner_id=le.session.owner_id,
            is_completed=True,
            e1rm__isnull=False,
        )
        .exclude(pk=logged_set.pk)
    )
    best = qs.order_by("-e1rm").values_list("e1rm", flat=True).first()
    return best


def exercise_history(owner, exercise):
    """Per-session bests for an exercise: heaviest set and top e1RM over time.

    Returns a list of dicts ordered oldest→newest, suitable for charting.
    """
    from .models import WorkoutSession

    sessions = (
        WorkoutSession.objects.filter(
            owner=owner, logged_exercises__exercise=exercise
        )
        .distinct()
        .order_by("started_at")
        .prefetch_related("logged_exercises__sets")
    )
    history = []
    for session in sessions:
        best_e1rm = None
        top_weight = None
        total_volume = Decimal("0")
        for le in session.logged_exercises.all():
            if le.exercise_id != exercise.id:
                continue
            for s in le.sets.all():
                if not s.is_completed:
                    continue
                if s.e1rm is not None and (best_e1rm is None or s.e1rm > best_e1rm):
                    best_e1rm = s.e1rm
                if s.weight is not None and (top_weight is None or s.weight > top_weight):
                    top_weight = s.weight
                total_volume += set_volume(s.weight, s.reps, s.set_type)
        history.append(
            {
                "session_id": session.id,
                "date": session.started_at.date().isoformat(),
                "best_e1rm": best_e1rm,
                "top_weight": top_weight,
                "volume": total_volume,
            }
        )
    return history


def last_performance(owner, exercise):
    """At-a-glance stats for the live logger: the all-time best (heaviest) set for
    an exercise — with its reps + e1RM — and the sets from the most recent
    *finished* session, used to pre-fill the next workout."""
    from .models import LoggedExercise, LoggedSet

    best_set = (
        LoggedSet.objects.filter(
            logged_exercise__session__owner=owner,
            logged_exercise__exercise=exercise,
            is_completed=True,
            weight__isnull=False,
        )
        .select_related("logged_exercise__session")
        .order_by("-weight", "-reps")
        .first()
    )
    best = None
    if best_set:
        # Stringify decimals so they match the rest of the API (DecimalField →
        # string); a raw dict through DictField would otherwise emit JSON numbers.
        best = {
            "weight": str(best_set.weight),
            "reps": best_set.reps,
            "e1rm": str(best_set.e1rm) if best_set.e1rm is not None else None,
            "date": best_set.logged_exercise.session.started_at.date().isoformat(),
        }

    # Most recent *finished* session that logged this exercise (excludes the
    # current in-progress one), so the next workout pre-fills from last time.
    last_le = (
        LoggedExercise.objects.filter(
            session__owner=owner,
            exercise=exercise,
            session__ended_at__isnull=False,
            sets__is_completed=True,
        )
        .select_related("session")
        .order_by("-session__started_at")
        .distinct()
        .first()
    )
    last = None
    if last_le:
        sets = [
            {
                "set_type": s.set_type,
                "weight": str(s.weight) if s.weight is not None else None,
                "reps": s.reps,
            }
            for s in last_le.sets.filter(is_completed=True).order_by("order")
        ]
        if sets:
            last = {"date": last_le.session.started_at.date().isoformat(), "sets": sets}
    return {"best": best, "last": last}


def weekly_muscle_volume(owner, since=None):
    """Hard-set counts and tonnage grouped by muscle since a given datetime.

    Each *counted* set (working / top set) credits its exercise's primary muscles one
    set each; tonnage sums all non-warm-up work (so intensity techniques add tonnage
    but not extra sets). Returns {muscle_name: {"sets": int, "tonnage": Decimal}}.
    """
    from .models import LoggedSet

    qs = LoggedSet.objects.filter(
        logged_exercise__session__owner=owner, is_completed=True
    ).select_related("logged_exercise__exercise")
    if since is not None:
        qs = qs.filter(logged_exercise__session__started_at__gte=since)

    result: dict[str, dict] = {}
    for s in qs.prefetch_related("logged_exercise__exercise__primary_muscles"):
        if not is_working_set(s.set_type):
            continue
        tonnage = set_volume(s.weight, s.reps, s.set_type)
        counted = counts_as_set(s.set_type)
        for muscle in s.logged_exercise.exercise.primary_muscles.all():
            bucket = result.setdefault(muscle.name, {"sets": 0, "tonnage": Decimal("0")})
            if counted:
                bucket["sets"] += 1
            bucket["tonnage"] += tonnage
    return result


def average_weekly_muscle_volume(owner, window_days=30, now=None):
    """Per-muscle weekly *averages* over the last `window_days`.

    `weekly_muscle_volume` returns raw totals for a window; here we divide them by the
    number of weeks actually covered so the figure reads as sets-per-week. The divisor
    is the span from the owner's first logged session in the window to now (capped at
    the window, floored at one week) — so a sub-`window_days` history isn't diluted by
    days before they started logging. Returns {muscle: {"sets": int, "tonnage": Decimal}}.
    """
    from datetime import timedelta

    from django.utils import timezone

    from .models import WorkoutSession

    now = now or timezone.now()
    since = now - timedelta(days=window_days)
    totals = weekly_muscle_volume(owner, since=since)
    if not totals:
        return {}

    first = (
        WorkoutSession.objects.filter(owner=owner, started_at__gte=since)
        .order_by("started_at")
        .values_list("started_at", flat=True)
        .first()
    )
    span_days = (now - first).days + 1 if first is not None else window_days
    weeks = max(1.0, min(window_days, span_days) / 7.0)
    wk = Decimal(str(weeks))
    return {
        m: {
            "sets": round(v["sets"] / weeks),
            "tonnage": (v["tonnage"] / wk).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        }
        for m, v in totals.items()
    }
