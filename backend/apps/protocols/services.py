"""Analytics for protocols: concentration curves, site rotation, adherence,
bloodwork trends, and the supplement → nutrition micronutrient feed.

Pure functions (numeric in/out) are unit-tested without the ORM; DB-aware
wrappers sit at the bottom. Nothing here recommends doses — it summarises the
user's own logged data.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.utils import timezone

from .enums import FREQUENCY_PER_WEEK, INJECTABLE_ROUTES

# Injection-site recency thresholds (days since last use).
SITE_REST_DAYS = 7      # >= this → fully rested (green)
SITE_RECOVER_DAYS = 3   # >= this → recovering (amber); below → fresh/needs-rest (red)


def _q(value, places="0.001") -> Decimal:
    return Decimal(str(value)).quantize(Decimal(places), rounding=ROUND_HALF_UP)


# --- Pure: pharmacokinetics ---------------------------------------------------


def remaining_fraction(hours_elapsed: float, half_life_hours: float) -> float:
    """Fraction of a dose still present after `hours_elapsed` (exponential decay)."""
    if half_life_hours is None or half_life_hours <= 0:
        return 0.0
    if hours_elapsed <= 0:
        return 1.0
    return 0.5 ** (hours_elapsed / half_life_hours)


def active_amount(dose_amount, active_fraction, hours_elapsed, half_life_hours) -> float:
    """Active drug remaining from one dose: amount × ester-fraction × decay."""
    if dose_amount is None:
        return 0.0
    frac = 1.0 if active_fraction is None else float(active_fraction)
    return float(dose_amount) * frac * remaining_fraction(hours_elapsed, half_life_hours)


def concentration_series(doses, half_life_hours, active_fraction, start, end, step_hours=12):
    """Active-amount time series over [start, end].

    `doses` is an iterable of (taken_at_datetime, amount). Returns a list of
    {t, value} with `t` ISO datetimes and `value` summed active amount.
    """
    if not half_life_hours or half_life_hours <= 0:
        return []
    points = []
    cursor = start
    step = timedelta(hours=step_hours)
    while cursor <= end:
        total = 0.0
        for taken_at, amount in doses:
            if taken_at <= cursor:
                hours = (cursor - taken_at).total_seconds() / 3600.0
                total += active_amount(amount, active_fraction, hours, float(half_life_hours))
        points.append({"t": cursor.isoformat(), "value": round(total, 3)})
        cursor += step
    return points


# --- Pure: rotation & adherence ----------------------------------------------


def site_status(days_since_last: float | None) -> str:
    """Recency bucket for an injection site: rested / recovering / fresh."""
    if days_since_last is None or days_since_last >= SITE_REST_DAYS:
        return "rested"
    if days_since_last >= SITE_RECOVER_DAYS:
        return "recovering"
    return "fresh"


def expected_doses(per_week: float, window_days: int) -> float:
    return (per_week or 0.0) * (window_days / 7.0)


def adherence_pct(actual: int, expected: float) -> int | None:
    """Whole-percent adherence (actual vs expected), capped at 100. None if N/A."""
    if not expected or expected <= 0:
        return None
    return min(100, round(actual / expected * 100))


def _times_per_day(times_of_day) -> int:
    return len(times_of_day) if times_of_day else 1


def expected_for_item(frequency, days_of_week, times_of_day, window_days, end_date) -> float:
    """Expected dose count over a trailing window for one item's schedule.

    `specific_days` counts matching weekdays in the window; `every_3_days` uses a
    1-in-3 cadence; everything else uses FREQUENCY_PER_WEEK — all multiplied by the
    number of times-of-day (≥1).
    """
    times = _times_per_day(times_of_day)
    if frequency == "specific_days" and days_of_week:
        wanted = set(days_of_week)
        start = end_date - timedelta(days=window_days - 1)
        matching = sum(
            1 for i in range(window_days) if (start + timedelta(days=i)).weekday() in wanted
        )
        return matching * times
    if frequency == "every_3_days":
        return (window_days / 3.0) * times
    per_week = FREQUENCY_PER_WEEK.get(frequency, 0.0)
    return per_week * (window_days / 7.0) * times


# --- DB-aware wrappers --------------------------------------------------------


def compound_concentration(owner, compound, days=30, step_hours=12):
    """Concentration series for a compound from the owner's dose history."""
    from .models import DoseLog

    end = timezone.now()
    start = end - timedelta(days=days)
    # Include doses from up to 5 half-lives before the window so the curve is
    # correct at `start` (older doses have decayed to ~3%).
    lookback = start
    if compound.half_life_hours:
        lookback = start - timedelta(hours=float(compound.half_life_hours) * 5)
    doses = list(
        DoseLog.objects.filter(
            owner=owner, compound=compound, taken_at__gte=lookback, taken_at__lte=end
        ).values_list("taken_at", "amount")
    )
    return concentration_series(
        doses, compound.half_life_hours, compound.active_fraction, start, end, step_hours
    )


def injection_site_recency(owner, days=30):
    """Per-site last-use + recency status from injectable dose logs in a window."""
    from .models import DoseLog, InjectionSite

    now = timezone.now()
    since = now - timedelta(days=days)
    last_by_site: dict[int, object] = {}
    qs = DoseLog.objects.filter(
        owner=owner, taken_at__gte=since, injection_site__isnull=False
    ).values_list("injection_site_id", "taken_at")
    for site_id, taken_at in qs:
        if site_id not in last_by_site or taken_at > last_by_site[site_id]:
            last_by_site[site_id] = taken_at

    rows = []
    for site in InjectionSite.objects.all():
        last = last_by_site.get(site.id)
        days_since = (now - last).total_seconds() / 86400.0 if last else None
        rows.append(
            {
                "id": site.id,
                "name": site.name,
                "slug": site.slug,
                "region": site.region,
                "side": site.side,
                "x": site.x,
                "y": site.y,
                "last_used": last.isoformat() if last else None,
                "days_since": round(days_since, 1) if days_since is not None else None,
                "status": site_status(days_since),
            }
        )
    return rows


def suggest_next_site(owner, days=30):
    """The most-rested injectable site (never used, or longest since last use).

    Single numeric sort key (never-used = +inf = most rested) so ordering is
    total — a tuple key here could tie and fall through to comparing row dicts.
    """
    rows = injection_site_recency(owner, days=days)
    if not rows:
        return None
    rows.sort(key=lambda r: float("inf") if r["days_since"] is None else r["days_since"],
              reverse=True)
    return rows[0]


def protocol_adherence(owner, protocol, window_days=28):
    """Per-item adherence for a protocol over the trailing window."""
    from .models import DoseLog

    now = timezone.now()
    since = now - timedelta(days=window_days)
    end_date = now.date()
    rows = []
    for item in protocol.items.select_related("compound", "supplement").all():
        expected = expected_for_item(
            item.frequency, item.days_of_week, item.times_of_day, window_days, end_date
        )
        actual = DoseLog.objects.filter(
            owner=owner, protocol_item=item, taken_at__gte=since, taken_at__lte=now
        ).count()
        item_obj = item.compound or item.supplement
        rows.append(
            {
                "item_id": item.id,
                "name": str(item_obj) if item_obj else "—",
                "frequency": item.frequency,
                "expected": round(expected, 1),
                "actual": actual,
                "adherence": adherence_pct(actual, expected),
            }
        )
    return rows


def supplement_nutrient_contribution(owner, date):
    """{nutrient_id: amount} contributed by supplement doses logged on `date`.

    One DoseLog of a supplement = `amount` servings (amount defaults to 1). This
    is summed into the nutrition daily summary so micros from pills count too.
    """
    from .models import DoseLog

    totals: dict[int, Decimal] = {}
    qs = DoseLog.objects.filter(
        owner=owner, supplement__isnull=False, taken_at__date=date
    ).select_related("supplement").prefetch_related("supplement__supplement_nutrients")
    for log in qs:
        servings = Decimal(str(log.amount or 1))
        for sn in log.supplement.supplement_nutrients.all():
            add = _q(sn.amount_per_serving * servings)
            totals[sn.nutrient_id] = totals.get(sn.nutrient_id, Decimal("0")) + add
    return totals


def marker_in_range(value, marker, sex=None) -> str:
    """Flag a value as low / in_range / high using sex-specific ranges if present."""
    low, high = marker.ref_low, marker.ref_high
    if sex == "male" and marker.ref_low_male is not None:
        low, high = marker.ref_low_male, marker.ref_high_male
    elif sex == "female" and marker.ref_low_female is not None:
        low, high = marker.ref_low_female, marker.ref_high_female
    v = Decimal(str(value))
    if low is not None and v < low:
        return "low"
    if high is not None and v > high:
        return "high"
    return "in_range"


def marker_trend(owner, marker, sex=None):
    """Time series of a marker's results with reference-range flags."""
    from .models import BloodResult

    results = BloodResult.objects.filter(owner=owner, marker=marker).order_by("measured_on")
    return [
        {
            "date": r.measured_on.isoformat(),
            "value": r.value,
            "flag": marker_in_range(r.value, marker, sex),
        }
        for r in results
    ]


def bloodwork_matrix(owner, sex=None):
    """Markers (with ≥1 result) × measurement dates, for the tabular trend view.

    Returns {dates:[iso…], rows:[{marker,slug,unit,category,cells:[cell|None]}]}
    where each cell is {value, pct_change vs the marker's previous reading, flag}.
    Never-measured markers are omitted; a None cell means "not measured that date".
    """
    from .models import BloodResult

    results = list(
        BloodResult.objects.filter(owner=owner).select_related("marker").order_by("measured_on")
    )
    dates = sorted({r.measured_on for r in results})
    markers = {}
    by_marker: dict[int, dict] = {}
    for r in results:
        markers[r.marker_id] = r.marker
        by_marker.setdefault(r.marker_id, {})[r.measured_on] = r.value

    rows = []
    for mid, marker in sorted(markers.items(), key=lambda kv: (kv[1].display_order, kv[1].name)):
        series = by_marker[mid]
        cells = []
        prev = None
        for d in dates:
            val = series.get(d)
            if val is None:
                cells.append(None)
                continue
            pct = None
            if prev is not None and prev != 0:
                pct = round(float((val - prev) / prev) * 100, 1)
            cells.append(
                {"value": str(val), "pct_change": pct, "flag": marker_in_range(val, marker, sex)}
            )
            prev = val
        rows.append(
            {
                "marker": marker.name,
                "slug": marker.slug,
                "unit": marker.unit,
                "category": marker.category,
                "cells": cells,
            }
        )
    return {"dates": [d.isoformat() for d in dates], "rows": rows}


def is_injectable_route(route: str) -> bool:
    return route in INJECTABLE_ROUTES
