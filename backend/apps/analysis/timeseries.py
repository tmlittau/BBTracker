"""Unified time-series layer: pull any tracked metric onto a common daily grid so
cross-domain metrics can be overlaid on one axis (the analysis "explore" tool).

Each metric resolves to a sparse ``[(date, value)]`` series (days without data are
absent). Core metrics are fixed; bloodwork markers and compound doses are discovered
per owner from their logged data.
"""
from __future__ import annotations

from collections import defaultdict

# key -> (label, unit, group). CheckIn-backed metrics map key -> model field below.
_CHECKIN = {
    "bodyweight": ("Body weight", "kg", "body"),
    "resting_pulse": ("Resting pulse", "bpm", "recovery"),
    "systolic": ("Systolic BP", "mmHg", "recovery"),
    "diastolic": ("Diastolic BP", "mmHg", "recovery"),
    "energy": ("Energy", "1–5", "recovery"),
    "sleep": ("Sleep quality", "1–5", "recovery"),
    "mood": ("Mood", "1–5", "recovery"),
    "motivation": ("Motivation", "1–5", "recovery"),
    "soreness": ("Soreness", "1–5", "recovery"),
}
_CHECKIN_FIELD = {"resting_pulse": "pulse"}  # key -> CheckIn field where they differ

_NUTRITION = {
    "calories": ("Calories", "kcal", "nutrition"),
    "protein_g": ("Protein", "g", "nutrition"),
}
_TRAINING = {
    "training_tonnage": ("Training tonnage", "kg", "training"),
    "training_hard_sets": ("Hard sets", "sets", "training"),
}
_MEASUREMENT = {
    "body_fat": ("Body fat", "%", "body"),
    "waist": ("Waist", "cm", "body"),
}
CORE_META = {**_CHECKIN, **_NUTRITION, **_TRAINING, **_MEASUREMENT}


def _checkin_series(owner, key, start, end):
    from apps.diary.models import CheckIn

    field = _CHECKIN_FIELD.get(key, key)
    rows = (
        CheckIn.objects.filter(owner=owner, date__gte=start, date__lte=end)
        .exclude(**{f"{field}__isnull": True})
        .values_list("date", field)
    )
    return [(d, float(v)) for d, v in rows if v is not None]


def _nutrition_series(owner, key, start, end):
    from apps.nutrition.services import macro_totals_by_day

    return [
        (d, float(v[key]))
        for d, v in macro_totals_by_day(owner, start, end).items()
        if v.get(key) is not None
    ]


def _training_series(owner, key, start, end):
    from apps.training.models import LoggedSet
    from apps.training.services import counts_as_set, set_volume

    rows = LoggedSet.objects.filter(
        logged_exercise__session__owner=owner,
        is_completed=True,
        logged_exercise__session__started_at__date__gte=start,
        logged_exercise__session__started_at__date__lte=end,
    ).values_list("logged_exercise__session__started_at", "set_type", "weight", "reps")
    by_day: dict = defaultdict(float)
    for started_at, set_type, weight, reps in rows:
        day = started_at.date()
        if key == "training_tonnage":
            by_day[day] += float(set_volume(weight, reps, set_type))
        elif counts_as_set(set_type):
            by_day[day] += 1.0
    return sorted(by_day.items())


def _measurement_series(owner, key, start, end):
    from apps.analysis.models import BodyMeasurement

    rows = BodyMeasurement.objects.filter(
        owner=owner, type=key, date__gte=start, date__lte=end
    ).values_list("date", "value")
    return [(d, float(v)) for d, v in rows if v is not None]


def _blood_series(owner, slug, start, end):
    from apps.protocols.models import BloodResult

    rows = BloodResult.objects.filter(
        owner=owner, marker__slug=slug, measured_on__gte=start, measured_on__lte=end
    ).values_list("measured_on", "value")
    return [(d, float(v)) for d, v in rows if v is not None]


def _dose_series(owner, slug, start, end):
    from apps.protocols.models import DoseLog

    rows = DoseLog.objects.filter(
        owner=owner,
        compound__slug=slug,
        status="taken",
        taken_at__date__gte=start,
        taken_at__date__lte=end,
    ).values_list("taken_at", "amount")
    by_day: dict = defaultdict(float)
    for taken_at, amount in rows:
        by_day[taken_at.date()] += float(amount or 0)
    return sorted(by_day.items())


def series_for(owner, key, start, end):
    """Sparse [(date, value)] for a metric key over [start, end], sorted by date."""
    if key in _CHECKIN:
        pts = _checkin_series(owner, key, start, end)
    elif key in _NUTRITION:
        pts = _nutrition_series(owner, key, start, end)
    elif key in _TRAINING:
        pts = _training_series(owner, key, start, end)
    elif key in _MEASUREMENT:
        pts = _measurement_series(owner, key, start, end)
    elif key.startswith("blood:"):
        pts = _blood_series(owner, key.split(":", 1)[1], start, end)
    elif key.startswith("dose:"):
        pts = _dose_series(owner, key.split(":", 1)[1], start, end)
    else:
        pts = []
    return sorted(pts, key=lambda p: p[0])


def metric_catalog(owner):
    """Metrics the owner has data for, for the explore-tool picker."""
    from apps.protocols.models import BloodResult, DoseLog

    items = [
        {"key": k, "label": lbl, "unit": u, "group": g}
        for k, (lbl, u, g) in CORE_META.items()
    ]
    for slug, name, unit in (
        BloodResult.objects.filter(owner=owner)
        .order_by()  # drop default ordering so .distinct() collapses to one row/marker
        .values_list("marker__slug", "marker__name", "marker__unit")
        .distinct()
    ):
        items.append(
            {"key": f"blood:{slug}", "label": name, "unit": unit, "group": "bloodwork"}
        )
    for slug, name in (
        DoseLog.objects.filter(owner=owner, compound__isnull=False)
        .order_by()  # ditto — otherwise one row per dose log
        .values_list("compound__slug", "compound__name")
        .distinct()
    ):
        items.append(
            {"key": f"dose:{slug}", "label": f"{name} dose", "unit": "mg", "group": "protocol"}
        )
    return items


def _meta_for(key, catalog):
    hit = next((c for c in catalog if c["key"] == key), None)
    return hit or {"key": key, "label": key, "unit": "", "group": "other"}


def _annotations(owner, start, end):
    """Phase spans + protocol-change events overlapping the window, for chart markers."""
    from apps.core.models import Phase, PhaseAdjustment

    phases = [
        {
            "name": p.name,
            "start": max(p.start_date, start).isoformat(),
            "end": (min(p.end_date, end) if p.end_date else end).isoformat(),
        }
        for p in Phase.objects.filter(owner=owner, start_date__lte=end).order_by("start_date")
        if (p.end_date or end) >= start
    ]
    events = [
        {"date": a.effective_date.isoformat(), "label": f"→ {a.protocol.name}"}
        for a in PhaseAdjustment.objects.filter(
            phase__owner=owner,
            protocol__isnull=False,
            effective_date__gte=start,
            effective_date__lte=end,
        ).select_related("protocol")
    ]
    return phases, events


def overlay(owner, keys, start, end):
    """Aligned series for `keys` plus phase/protocol annotations over [start, end]."""
    catalog = metric_catalog(owner)
    metrics = []
    for key in keys:
        pts = series_for(owner, key, start, end)
        metrics.append(
            {
                **_meta_for(key, catalog),
                "points": [{"date": d.isoformat(), "value": round(v, 3)} for d, v in pts],
            }
        )
    phases, events = _annotations(owner, start, end)
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "metrics": metrics,
        "phases": phases,
        "events": events,
    }
