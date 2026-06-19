"""Analytics for protocols: concentration curves, site rotation, adherence,
bloodwork trends, and the supplement → nutrition micronutrient feed.

Pure functions (numeric in/out) are unit-tested without the ORM; DB-aware
wrappers sit at the bottom. Nothing here recommends doses — it summarises the
user's own logged data.
"""
from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta
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


# --- Pure: depot release-rate model (whole-protocol curve) --------------------

# Legacy per-week frequencies → representative weekdays for projection.
LEGACY_WEEKDAY_MAP = {
    "2x_week": {0, 3},     # Mon, Thu
    "3x_week": {0, 2, 4},  # Mon, Wed, Fri
}


def decay_constant_per_day(half_life_hours) -> float | None:
    """First-order rate constant k (per day) from a half-life. None if unusable."""
    if not half_life_hours or float(half_life_hours) <= 0:
        return None
    return math.log(2) / (float(half_life_hours) / 24.0)


def release_rate_series(doses, half_life_hours, active_fraction, start_day, end_day,
                        step_days=1):
    """Active-drug release rate (mass/day) over day-offsets [start_day, end_day].

    Single-compartment depot: a dose D deposited on day dᵢ releases active drug at
    rate f·D·k·e^(−k·(t−dᵢ))  (k = ln2 / half-life, f = active fraction). Each point
    sums every dose with dᵢ ≤ t. At steady daily dosing the rate tends to dose×f per
    day (mass conservation). `doses` = iterable of (day_offset, amount). Returns
    [(day, rate)].
    """
    k = decay_constant_per_day(half_life_hours)
    if k is None:
        return []
    f = 1.0 if active_fraction is None else float(active_fraction)
    ds = sorted((float(d), float(a)) for d, a in doses if a is not None)
    points = []
    n = 0
    t = start_day
    while t <= end_day + 1e-9:
        total = 0.0
        for d_i, a_i in ds:
            if d_i > t:
                break
            total += f * a_i * k * math.exp(-k * (t - d_i))
        points.append((round(t, 4), round(total, 5)))
        n += 1
        t = start_day + n * step_days
    return points


def absorption_constant_per_day(tmax_hours, ke) -> float | None:
    """First-order absorption rate constant ka (per day) whose single-dose peak
    falls at `tmax_hours`, given elimination constant `ke`.

    Bateman peak time tmax = ln(ka/ke)/(ka−ke) is strictly decreasing in ka (→∞ as
    ka→0, →0 as ka→∞), so a bisection finds the unique ka. None if tmax is missing
    or outside the achievable range.
    """
    if not tmax_hours or float(tmax_hours) <= 0 or not ke or ke <= 0:
        return None
    tmax = float(tmax_hours) / 24.0

    def peak_time(ka):
        if abs(ka - ke) < 1e-9:
            return 1.0 / ke  # limit of ln(ka/ke)/(ka−ke) as ka→ke
        return math.log(ka / ke) / (ka - ke)

    lo, hi = 1e-6, 1e6
    if not (peak_time(hi) <= tmax <= peak_time(lo)):
        return None
    for _ in range(100):  # geometric bisection — ka spans orders of magnitude
        mid = math.sqrt(lo * hi)
        if peak_time(mid) > tmax:
            lo = mid
        else:
            hi = mid
    return math.sqrt(lo * hi)


def concentration_series(doses, half_life_hours, tmax_hours, bioavailability,
                         active_fraction, start_day, end_day, step_days=1):
    """Relative active serum level over day-offsets [start_day, end_day].

    One-compartment model with first-order absorption + elimination (Bateman): a
    dose D on day dᵢ contributes F·f·D·(ka/(ka−ke))·(e^−ke·Δ − e^−ka·Δ), Δ = t−dᵢ ≥ 0,
    where ke = ln2/half-life, ka is fitted from `tmax_hours`, F = bioavailability
    (default 1), f = active fraction. With no usable tmax it degrades to
    instantaneous absorption F·f·D·e^−ke·Δ (the older exponential shape). Output is
    a relative level (Vd = 1, arbitrary units) comparable across compounds — not a
    calibrated ng/mL. `doses` = iterable of (day_offset, amount). Returns [(day, level)].
    """
    ke = decay_constant_per_day(half_life_hours)
    if ke is None:
        return []
    f = 1.0 if active_fraction is None else float(active_fraction)
    bio = 1.0 if bioavailability is None else float(bioavailability)
    scale = f * bio
    ka = absorption_constant_per_day(tmax_hours, ke)

    if ka is not None and abs(ka - ke) > 1e-9:
        coef = ka / (ka - ke)

        def kernel(dt):
            return coef * (math.exp(-ke * dt) - math.exp(-ka * dt))
    else:
        def kernel(dt):
            return math.exp(-ke * dt)

    ds = sorted((float(d), float(a)) for d, a in doses if a is not None)
    points = []
    n = 0
    t = start_day
    while t <= end_day + 1e-9:
        total = 0.0
        for d_i, a_i in ds:
            if d_i > t:
                break
            total += scale * a_i * kernel(t - d_i)
        points.append((round(t, 4), round(total, 5)))
        n += 1
        t = start_day + n * step_days
    return points


def times_per_day_count(times_of_day, frequency) -> int:
    """Administrations per dosing day (multi-select times, or legacy 2×/day)."""
    n = len(times_of_day) if times_of_day else 0
    if n == 0:
        return 2 if frequency == "2x_day" else 1
    return n


def scheduled_dose_dates(frequency, days_of_week, start_date, end_date, anchor_date):
    """Dates in [start_date, end_date] on which an item is dosed (one per dosing day).

    Mirrors the adherence cadence: interval cadences (eod / every-3 / weekly) are
    phased to `anchor_date`; `specific_days` matches weekdays; PRN can't be projected
    (returns []). Legacy 2×/3× per week map to fixed weekdays.
    """
    if frequency in ("prn", "as_needed"):
        return []
    wanted = set(days_of_week or [])
    out = []
    d = start_date
    while d <= end_date:
        delta = (d - anchor_date).days
        if frequency in ("daily", "2x_day"):
            keep = True
        elif frequency == "eod":
            keep = delta % 2 == 0
        elif frequency == "every_3_days":
            keep = delta % 3 == 0
        elif frequency == "weekly":
            keep = delta % 7 == 0
        elif frequency == "specific_days":
            keep = d.weekday() in wanted
        elif frequency in LEGACY_WEEKDAY_MAP:
            keep = d.weekday() in LEGACY_WEEKDAY_MAP[frequency]
        else:
            keep = True
        if keep:
            out.append(d)
        d += timedelta(days=1)
    return out


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


# Mass-dose units we can place on a shared mg/day axis (others are excluded).
_MG_PER_UNIT = {"mg": 1.0, "mcg": 0.001}


def protocol_release_curves(owner, protocol, now=None, horizon_days=84,
                            step_days=1, max_history_days=365):
    """Per-compound active serum-level (relative, Bateman) curves for a whole protocol.

    The past (≤ today) uses the owner's actual `DoseLog`s for each compound; the
    future (> today) is projected from each item's schedule (frequency + days/times).
    One line per compound — each ester keeps its own half-life / active fraction.
    Compounds with no half-life, dosed in non-mass units (iu/ml/tablet), or with no
    doses at all are omitted (the first two are named in `excluded`). Returns
    {now, today_day, start, end, unit, compounds:[…], excluded:[…]}.
    """
    from .models import DoseLog

    now = now or timezone.now()
    if timezone.is_naive(now):
        now = timezone.make_aware(now)
    today = timezone.localtime(now).date()

    # Group compound items; skip supplements, missing half-life, non-mass units.
    grouped: dict[int, dict] = {}
    excluded: list[str] = []
    for it in protocol.items.select_related("compound").filter(compound__isnull=False):
        c = it.compound
        factor = _MG_PER_UNIT.get(c.default_unit)
        if not c.half_life_hours or float(c.half_life_hours) <= 0 or factor is None:
            if c.name not in excluded:
                excluded.append(c.name)
            continue
        grouped.setdefault(
            c.id, {"compound": c, "factor": factor, "items": []}
        )["items"].append(it)

    empty = {"now": today.isoformat(), "today_day": 0, "start": None, "end": None,
             "unit": "relative", "compounds": [], "excluded": excluded}
    if not grouped:
        return empty

    cids = list(grouped)
    first_dose = (
        DoseLog.objects.filter(owner=owner, compound_id__in=cids, status="taken")
        .order_by("taken_at").values_list("taken_at", flat=True).first()
    )

    # Plot window: start at the protocol start (or first dose, or today), clamped.
    start_date = protocol.started_on or (first_dose.date() if first_dose else today)
    start_date = max(start_date, today - timedelta(days=max_history_days))
    anchor = protocol.started_on or start_date

    dosing_end = protocol.ended_on or (today + timedelta(days=horizon_days))
    max_hl_days = max(float(g["compound"].half_life_hours) / 24.0 for g in grouped.values())
    if protocol.ended_on:           # show the wash-out tail after dosing stops
        plot_end = protocol.ended_on + timedelta(days=min(120, int(math.ceil(5 * max_hl_days))))
    else:                           # open-ended → plateau to the horizon
        plot_end = dosing_end
    plot_end = max(plot_end, start_date)

    start_dt = datetime.combine(start_date, time.min, tzinfo=now.tzinfo)
    total_days = (plot_end - start_date).days
    today_day = (today - start_date).days
    proj_start = max(start_date, today + timedelta(days=1))

    # All logged doses for these compounds in ONE query (widest lookback), bucketed
    # by compound — avoids a per-compound query inside the loop below.
    min_lookback = start_dt - timedelta(days=min(120, 5 * max_hl_days))
    doses_by_compound: dict[int, list] = {}
    for cid, ta, amt in DoseLog.objects.filter(
        owner=owner, compound_id__in=cids, status="taken",
        taken_at__lte=now, taken_at__gte=min_lookback,
    ).values_list("compound_id", "taken_at", "amount"):
        if amt is not None:
            doses_by_compound.setdefault(cid, []).append((ta, amt))

    compounds_out = []
    for g in grouped.values():
        c, factor = g["compound"], g["factor"]
        hl = c.half_life_hours

        # Actual doses up to now (with a pre-window lookback so the left edge is
        # correct), as (day_offset, mg).
        lookback = start_dt - timedelta(days=min(120, 5 * float(hl) / 24.0))
        doses = [
            ((ta - start_dt).total_seconds() / 86400.0, float(amt) * factor)
            for ta, amt in doses_by_compound.get(c.id, [])
            if ta >= lookback
        ]

        # Projected future doses (> today) from each item's schedule.
        for it in g["items"]:
            if it.dose_amount is None:
                continue
            per = times_per_day_count(it.times_of_day, it.frequency)
            amt_mg = float(it.dose_amount) * factor * per
            for d in scheduled_dose_dates(
                it.frequency, it.days_of_week, proj_start, dosing_end, anchor
            ):
                doses.append(((d - start_date).days + 0.5, amt_mg))

        if not doses:               # nothing logged or planned → no meaningful line
            continue

        series = concentration_series(
            doses, hl, c.tmax_hours, c.bioavailability, c.active_fraction,
            0, total_days, step_days,
        )
        compounds_out.append({
            "compound_id": c.id,
            "name": c.name,
            "unit": "relative",
            "half_life_hours": float(hl),
            "active_fraction": float(c.active_fraction),
            "points": [
                {"day": int(day), "date": (start_date + timedelta(days=int(day))).isoformat(),
                 "rate": rate, "projected": day > today_day}
                for day, rate in series
            ],
        })

    compounds_out.sort(key=lambda x: x["name"])
    return {
        "now": today.isoformat(),
        "today_day": today_day,
        "start": start_date.isoformat(),
        "end": plot_end.isoformat(),
        "unit": "relative",
        "compounds": compounds_out,
        "excluded": excluded,
    }


def plot_compounds(user, items, horizon_days=84, step_days=1):
    """Stateless cycle-planner curves: overlay per-compound concentration for a set
    of hypothetical items over `horizon_days` from day 0. No DB writes.

    Each item = {compound (id), dose_amount, dose_unit?, frequency?, days_of_week?,
    times_of_day?, start_day?, duration_days?}. One line per compound (same-compound
    items merge their doses). Non-mass units / missing half-life → excluded. Returns
    {horizon_days, unit, compounds:[…], excluded:[…]}.
    """
    from django.db.models import Q

    from .models import Compound

    horizon = max(1, min(int(horizon_days or 84), 730))
    anchor = date(2000, 1, 3)  # a Monday → sane weekday scheduling
    by_id = {c.id: c for c in Compound.objects.filter(Q(owner=user) | Q(owner__isnull=True))}

    grouped: dict[int, dict] = {}
    excluded: list[str] = []
    for it in items or []:
        c = by_id.get(it.get("compound"))
        if c is None:
            continue
        factor = _MG_PER_UNIT.get(it.get("dose_unit") or c.default_unit)
        dose = it.get("dose_amount")
        if not c.half_life_hours or float(c.half_life_hours) <= 0 or factor is None or not dose:
            if c.name not in excluded:
                excluded.append(c.name)
            continue
        start_day = max(0, int(it.get("start_day") or 0))
        duration = int(it.get("duration_days") or horizon)
        last_day = min(start_day + max(0, duration) - 1, horizon)
        if last_day < start_day:
            continue
        freq = it.get("frequency") or "daily"
        amt_mg = float(dose) * factor * times_per_day_count(it.get("times_of_day"), freq)
        s, e = anchor + timedelta(days=start_day), anchor + timedelta(days=last_day)
        bucket = grouped.setdefault(c.id, {"compound": c, "doses": []})
        for d in scheduled_dose_dates(freq, it.get("days_of_week") or [], s, e, anchor):
            bucket["doses"].append(((d - anchor).days, amt_mg))

    compounds_out = []
    for g in grouped.values():
        if not g["doses"]:
            continue
        c = g["compound"]
        series = concentration_series(
            g["doses"], c.half_life_hours, c.tmax_hours, c.bioavailability,
            c.active_fraction, 0, horizon, step_days,
        )
        compounds_out.append({
            "compound_id": c.id,
            "name": c.name,
            "half_life_hours": float(c.half_life_hours),
            "points": [{"day": int(d), "level": v} for d, v in series],
        })
    compounds_out.sort(key=lambda x: x["name"])
    return {"horizon_days": horizon, "unit": "relative",
            "compounds": compounds_out, "excluded": excluded}


def injection_site_recency(owner, days=30):
    """Per-site last-use + recency status from injectable dose logs in a window."""
    from .models import DoseLog, InjectionSite

    now = timezone.now()
    since = now - timedelta(days=days)
    last_by_site: dict[int, object] = {}
    qs = DoseLog.objects.filter(
        owner=owner, taken_at__gte=since, injection_site__isnull=False, status="taken"
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
                "route": site.route,
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
            owner=owner, protocol_item=item, status="taken",
            taken_at__gte=since, taken_at__lte=now
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


def phase_dose_matrix(owner, phase, protocol):
    """Week-by-week dose table for a phase, from the protocol's plan + the user's logs.

    Each row is a protocol item; each column a 7-day week of the phase. Past/current
    weeks reflect what was actually logged (taken / skipped); future weeks show the
    current plan — so adjusting the protocol only changes weeks not yet logged.
    Injectable anabolics report a summed **weekly** dose; everything else its **daily**
    dose. Cell `state`: done / partial / skipped / planned (future) / none.
    """
    from .models import DoseLog

    start = phase.start_date
    end = phase.end_date or timezone.now().date()
    today = timezone.now().date()

    weeks = []
    d = start
    while d <= end:
        w_end = min(d + timedelta(days=6), end)
        weeks.append({"index": len(weeks), "start": d, "end": w_end})
        d += timedelta(days=7)

    anchor = protocol.started_on or start

    # All doses in the phase window in ONE query, bucketed by compound/supplement —
    # avoids a per-item query inside the loop below.
    logs_by_compound: dict[int, list] = {}
    logs_by_supplement: dict[int, list] = {}
    for cid, sid, ta, amt, st in DoseLog.objects.filter(
        owner=owner, taken_at__date__gte=start, taken_at__date__lte=end
    ).values_list("compound_id", "supplement_id", "taken_at", "amount", "status"):
        if cid is not None:
            logs_by_compound.setdefault(cid, []).append((ta, amt, st))
        elif sid is not None:
            logs_by_supplement.setdefault(sid, []).append((ta, amt, st))

    rows = []
    for item in protocol.items.select_related("compound", "supplement").all():
        obj = item.compound or item.supplement
        if obj is None:
            continue
        is_compound = item.compound_id is not None
        route = item.route or (item.compound.default_route if item.compound else "")
        injectable_anabolic = (
            is_compound
            and item.compound.compound_class == "anabolic"
            and route in INJECTABLE_ROUTES
        )
        mode = "weekly" if injectable_anabolic else "daily"
        per = Decimal(str(item.dose_amount)) if item.dose_amount is not None else None
        # Administrations per dosing day (e.g. Waking + Night = 2) — the daily dose
        # is the per-administration amount times this.
        times_per_day = times_per_day_count(item.times_of_day, item.frequency)
        # Subgroup for the dose table, so it can be split into per-class sections.
        if not is_compound:
            group = "Supplements"
        elif item.compound.compound_class == "anabolic":
            group = "Injectable steroids" if route in INJECTABLE_ROUTES else "Oral steroids"
        else:
            group = {
                "peptide": "Peptides",
                "sarm": "SARMs",
                "ancillary": "Ancillaries",
            }.get(item.compound.compound_class, "Other")

        log_val = item.compound_id if is_compound else item.supplement_id
        logs = (logs_by_compound if is_compound else logs_by_supplement).get(log_val, [])

        cells = []
        for w in weeks:
            ws, we = w["start"], w["end"]
            taken_amt, taken_n, skipped_n = Decimal("0"), 0, 0
            for ta, amt, status in logs:
                if ws <= ta.date() <= we:
                    if status == "skipped":
                        skipped_n += 1
                    else:
                        taken_n += 1
                        taken_amt += Decimal(str(amt or 0))
            sched_days = scheduled_dose_dates(
                item.frequency, item.days_of_week, ws, we, anchor
            )
            scheduled = len(sched_days) * times_per_day
            planned_amt = per * scheduled if per is not None else None
            future = ws > today
            if future:
                state = "planned" if scheduled else "none"
            elif taken_n:
                state = "done" if (not scheduled or taken_n >= scheduled) else "partial"
            elif skipped_n:
                state = "skipped"
            else:
                state = "none"
            cells.append(
                {
                    "week": w["index"],
                    "scheduled": scheduled,
                    "planned_amount": str(_q(planned_amt)) if planned_amt is not None else None,
                    "taken_count": taken_n,
                    "skipped_count": skipped_n,
                    "taken_amount": str(_q(taken_amt)),
                    "state": state,
                }
            )

        rows.append(
            {
                "item_id": item.id,
                "name": str(obj),
                "kind": "compound" if is_compound else "supplement",
                "group": group,
                "mode": mode,
                "unit": item.dose_unit,
                "daily_dose": str(_q(per * times_per_day)) if per is not None else None,
                "cells": cells,
            }
        )

    return {
        "phase": {
            "id": phase.id,
            "name": phase.name,
            "start_date": start.isoformat(),
            "end_date": phase.end_date.isoformat() if phase.end_date else None,
        },
        "weeks": [
            {"index": w["index"], "start": w["start"].isoformat(), "end": w["end"].isoformat()}
            for w in weeks
        ],
        "rows": rows,
    }


# Supplement nutrients are defined per serving; only count-based dose units scale
# them. A mass/volume unit (mg/g/iu/ml) counts as a single serving.
SERVING_UNITS = {"capsule", "tablet", "serving"}


def supplement_nutrient_contribution(owner, date):
    """{nutrient_id: amount} contributed by supplement doses logged on `date`.

    One DoseLog of a supplement = `amount` servings (amount defaults to 1). This
    is summed into the nutrition daily summary so micros from pills count too.
    """
    from .models import DoseLog

    totals: dict[int, Decimal] = {}
    qs = DoseLog.objects.filter(
        owner=owner, supplement__isnull=False, taken_at__date=date, status="taken"
    ).select_related("supplement").prefetch_related("supplement__supplement_nutrients")
    for log in qs:
        # Only count-based units (capsule/tablet/serving) scale the per-serving
        # nutrients. A mass/volume dose (mg, g, iu, ml) counts as ONE serving, so
        # logging fish oil as "1000 mg" doesn't multiply its macros by 1000.
        unit = (log.unit or "").lower()
        servings = Decimal(str(log.amount or 1)) if unit in SERVING_UNITS else Decimal("1")
        for sn in log.supplement.supplement_nutrients.all():
            add = _q(sn.amount_per_serving * servings)
            totals[sn.nutrient_id] = totals.get(sn.nutrient_id, Decimal("0")) + add
    return totals


def supplement_nutrient_contribution_range(owner, start_date, end_date):
    """{date: {nutrient_id: amount}} from supplement doses in [start, end] — one query.

    Windowed sibling of supplement_nutrient_contribution for batched callers (e.g. the
    weekly check-in), so they don't query supplements once per day.
    """
    from collections import defaultdict

    from .models import DoseLog

    out: dict = defaultdict(lambda: defaultdict(Decimal))
    qs = (
        DoseLog.objects.filter(
            owner=owner, supplement__isnull=False, status="taken",
            taken_at__date__gte=start_date, taken_at__date__lte=end_date,
        )
        .select_related("supplement")
        .prefetch_related("supplement__supplement_nutrients")
    )
    for log in qs:
        unit = (log.unit or "").lower()
        servings = Decimal(str(log.amount or 1)) if unit in SERVING_UNITS else Decimal("1")
        day = timezone.localtime(log.taken_at).date()
        for sn in log.supplement.supplement_nutrients.all():
            out[day][sn.nutrient_id] += _q(sn.amount_per_serving * servings)
    return {d: dict(m) for d, m in out.items()}


def flag_value(value, low, high) -> str:
    """low / in_range / high for a value against an explicit reference range."""
    v = Decimal(str(value))
    if low is not None and v < Decimal(str(low)):
        return "low"
    if high is not None and v > Decimal(str(high)):
        return "high"
    return "in_range"


def marker_range(marker, sex=None):
    """The marker's reference (low, high), preferring sex-specific bounds when set."""
    low, high = marker.ref_low, marker.ref_high
    if sex == "male" and marker.ref_low_male is not None:
        low, high = marker.ref_low_male, marker.ref_high_male
    elif sex == "female" and marker.ref_low_female is not None:
        low, high = marker.ref_low_female, marker.ref_high_female
    return low, high


def result_range(result, sex=None):
    """A result's effective range: its own ref if present, else the marker's."""
    if result.ref_low is not None or result.ref_high is not None:
        return result.ref_low, result.ref_high
    return marker_range(result.marker, sex)


def marker_in_range(value, marker, sex=None) -> str:
    """Flag a value using the marker's (sex-specific) reference range."""
    low, high = marker_range(marker, sex)
    return flag_value(value, low, high)


def marker_trend(owner, marker, sex=None):
    """Time series of a marker's results with per-result unit + reference-range flags."""
    from .models import BloodResult

    results = BloodResult.objects.filter(owner=owner, marker=marker).order_by("measured_on")
    out = []
    for r in results:
        low, high = result_range(r, sex)
        out.append(
            {
                "date": r.measured_on.isoformat(),
                "value": r.value,
                "unit": r.unit or marker.unit,
                "flag": flag_value(r.value, low, high),
            }
        )
    return out


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
        by_marker.setdefault(r.marker_id, {})[r.measured_on] = r

    rows = []
    for mid, marker in sorted(markers.items(), key=lambda kv: (kv[1].display_order, kv[1].name)):
        series = by_marker[mid]
        cells = []
        prev = None  # (value, unit)
        for d in dates:
            r = series.get(d)
            if r is None:
                cells.append(None)
                continue
            unit = r.unit or marker.unit
            low, high = result_range(r, sex)
            # %-change only between consecutive readings in the same unit.
            pct = None
            if prev is not None and prev[0] != 0 and prev[1] == unit:
                pct = round(float((r.value - prev[0]) / prev[0]) * 100, 1)
            cells.append(
                {"value": str(r.value), "unit": unit, "pct_change": pct,
                 "flag": flag_value(r.value, low, high)}
            )
            prev = (r.value, unit)
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
