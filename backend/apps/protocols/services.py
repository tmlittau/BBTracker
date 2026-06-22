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


# A fixed Monday epoch used to phase interval cadences (eod / every-3 / weekly)
# when a protocol has no explicit start date. Keeping it a single global reference
# (instead of "today") means the cadence stays a true 1-in-N pattern that drifts
# across weekdays week to week — never collapsing to "every day" — and every view
# (week prep, quick log, release curves, dose matrix) agrees on the dosing days.
CADENCE_EPOCH = date(2000, 1, 3)


def dose_anchor(protocol):
    """Reference date for phasing a protocol's interval cadences: its start date if
    set, else the stable epoch (so the cadence never collapses to daily)."""
    started = getattr(protocol, "started_on", None) if protocol else None
    return started or CADENCE_EPOCH


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
    anchor = dose_anchor(protocol)

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


def phase_compound_levels(owner, start_date, end_date, step_days=1):
    """Per-compound serum-level (Bateman) curves over [start_date, end_date] built
    from the owner's *actual* logged doses — how concentrations really moved across
    a phase, capturing any mid-phase protocol/adjustment changes. `end_date` is
    clamped to today, so a current phase shows levels up to today. Same payload shape
    as `protocol_release_curves` (so the chart is shared); everything is observed
    (no projection)."""
    from .models import Compound, DoseLog

    today = timezone.localdate()
    end_date = min(end_date, today)
    empty = {"now": today.isoformat(), "today_day": 0, "start": None, "end": None,
             "unit": "relative", "compounds": [], "excluded": []}
    if end_date < start_date:
        return empty

    tz = timezone.get_current_timezone()
    start_dt = datetime.combine(start_date, time.min, tzinfo=tz)
    end_dt = datetime.combine(end_date, time.max, tzinfo=tz)
    total_days = (end_date - start_date).days

    # set() dedups regardless of the model's default ordering (which would otherwise
    # leak the taken_at column into the SELECT and defeat .distinct()).
    cids = sorted(set(
        DoseLog.objects.filter(
            owner=owner, compound__isnull=False, status="taken",
            taken_at__gte=start_dt, taken_at__lte=end_dt,
        ).values_list("compound_id", flat=True)
    ))
    if not cids:
        return empty
    compounds = {c.id: c for c in Compound.objects.filter(id__in=cids)}

    # Look back a few half-lives so residual from pre-phase dosing sets the left edge.
    max_hl_days = max(
        (float(c.half_life_hours) / 24.0 for c in compounds.values() if c.half_life_hours),
        default=1.0,
    )
    lookback_dt = start_dt - timedelta(days=min(180, int(math.ceil(5 * max_hl_days))))

    doses_by_compound: dict[int, list] = {}
    for cid, ta, amt in DoseLog.objects.filter(
        owner=owner, compound_id__in=cids, status="taken",
        taken_at__gte=lookback_dt, taken_at__lte=end_dt,
    ).values_list("compound_id", "taken_at", "amount"):
        if amt is not None:
            doses_by_compound.setdefault(cid, []).append((ta, amt))

    out, excluded = [], []
    for cid in cids:
        c = compounds[cid]
        factor = _MG_PER_UNIT.get(c.default_unit)
        if not c.half_life_hours or float(c.half_life_hours) <= 0 or factor is None:
            if c.name not in excluded:
                excluded.append(c.name)
            continue
        doses = [
            ((ta - start_dt).total_seconds() / 86400.0, float(amt) * factor)
            for ta, amt in doses_by_compound.get(cid, [])
        ]
        if not doses:
            continue
        series = concentration_series(
            doses, c.half_life_hours, c.tmax_hours, c.bioavailability,
            c.active_fraction, 0, total_days, step_days,
        )
        out.append({
            "compound_id": c.id,
            "name": c.name,
            "unit": "relative",
            "half_life_hours": float(c.half_life_hours),
            "active_fraction": float(c.active_fraction),
            "points": [
                {"day": int(day), "date": (start_date + timedelta(days=int(day))).isoformat(),
                 "rate": rate, "projected": False}
                for day, rate in series
            ],
        })
    out.sort(key=lambda x: x["name"])
    return {
        "now": today.isoformat(),
        "today_day": total_days,  # all observed → solid line, no projection
        "start": start_date.isoformat(),
        "end": end_date.isoformat(),
        "unit": "relative",
        "compounds": out,
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
    anchor = CADENCE_EPOCH  # fixed Monday → relative interval scheduling
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


def _matrix_row_meta(key, rep, obj):
    """Row metadata for the dose table — name / group / unit / mode + the current daily
    dose. `rep` is the most recent prescribing item (None for a logged-only / dropped
    row); `obj` is the underlying Compound or Supplement."""
    is_compound = key[0] == "compound"
    route = (rep.route if rep and rep.route else (obj.default_route if is_compound else "")) or ""
    injectable_anabolic = (
        is_compound and obj.compound_class == "anabolic" and route in INJECTABLE_ROUTES
    )
    if not is_compound:
        group = "Supplements"
    elif obj.compound_class == "anabolic":
        group = "Injectable steroids" if route in INJECTABLE_ROUTES else "Oral steroids"
    else:
        group = {"peptide": "Peptides", "sarm": "SARMs", "ancillary": "Ancillaries"}.get(
            obj.compound_class, "Other"
        )
    if rep is not None:
        per = Decimal(str(rep.dose_amount)) if rep.dose_amount is not None else None
        tpd = times_per_day_count(rep.times_of_day, rep.frequency)
        daily_dose = str(_q(per * tpd)) if per is not None else None
        unit, item_id = rep.dose_unit, rep.id
    else:  # dropped/logged-only row: no current plan, synthesise a stable unique id
        daily_dose, unit = None, (obj.default_unit if is_compound else "serving")
        item_id = -(key[1] if is_compound else key[1] + 10_000_000)
    return {
        "item_id": item_id,
        "name": str(obj),
        "kind": key[0],
        "group": group,
        "mode": "weekly" if injectable_anabolic else "daily",
        "unit": unit,
        "daily_dose": daily_dose,
    }


def phase_dose_matrix(owner, phase, protocol):
    """Week-by-week dose table for a phase — a historical + plan record across changes.

    Each row is a compound/supplement that was prescribed at any point in the phase OR
    logged during it; each column is a 7-day week. Each week's plan is resolved from the
    protocol in force that week (so a phase adjustment that drops a compound, adds one, or
    changes a dose is reflected per week), while past/current weeks show what was actually
    logged. An adjustment therefore changes upcoming weeks without erasing the compounds
    or doses that came before — a dropped compound keeps its logged history then reads
    `none`, and a newly-introduced one appears only from its week.
    Injectable anabolics report a summed **weekly** dose; everything else its **daily**
    dose. Cell `state`: done / partial / skipped / planned (future) / none.
    """
    from .models import Compound, DoseLog, Supplement

    start = phase.start_date
    end = phase.end_date or timezone.now().date()
    today = timezone.now().date()

    weeks = []
    d = start
    while d <= end:
        w_end = min(d + timedelta(days=6), end)
        weeks.append({"index": len(weeks), "start": d, "end": w_end})
        d += timedelta(days=7)

    def _key(it):
        return ("compound", it.compound_id) if it.compound_id else ("supplement", it.supplement_id)

    # The plan in force at the start of each week, indexed by (kind, ref_id). The protocol
    # can change across the phase via adjustments; resolve from the adjustment timeline
    # (fetched once, not per week) and fall back to the passed protocol.
    from apps.core.models import PhaseAdjustment

    adjustments = list(
        PhaseAdjustment.objects.filter(
            phase__owner=owner, protocol__isnull=False, effective_date__lte=end
        )
        .select_related("protocol")
        .order_by("-effective_date", "-id")
    )

    def _in_force(on):
        for adj in adjustments:
            if adj.effective_date <= on:
                return adj.protocol
        return protocol

    plan_cache: dict[int, dict] = {}
    week_plan = []  # per week: (protocol_or_None, {(kind, ref): item})
    for w in weeks:
        pf = _in_force(w["start"])
        if pf is None:
            week_plan.append((None, {}))
            continue
        if pf.id not in plan_cache:
            plan_cache[pf.id] = {
                _key(it): it
                for it in pf.items.select_related("compound", "supplement").all()
                if it.compound_id or it.supplement_id
            }
        week_plan.append((pf, plan_cache[pf.id]))

    # Every dose logged in the phase window, bucketed by (kind, ref_id) — one query.
    logs_by_key: dict[tuple, list] = {}
    for cid, sid, ta, amt, st in DoseLog.objects.filter(
        owner=owner, taken_at__date__gte=start, taken_at__date__lte=end
    ).values_list("compound_id", "supplement_id", "taken_at", "amount", "status"):
        key = ("compound", cid) if cid else ("supplement", sid) if sid else None
        if key is not None:
            logs_by_key.setdefault(key, []).append((ta, amt, st))

    # Rows = everything ever planned in the phase ∪ everything logged in it.
    keys = set(logs_by_key)
    for _pf, items in week_plan:
        keys |= set(items)

    # Underlying objects. Prescribed rows already carry their compound/supplement
    # (select_related on the items); only logged-only / dropped keys need a lookup.
    objs = {}
    for _pf, items in week_plan:
        for key, it in items.items():
            objs.setdefault(key, it.compound or it.supplement)
    miss_c = [r for (k, r) in keys if k == "compound" and (k, r) not in objs]
    miss_s = [r for (k, r) in keys if k == "supplement" and (k, r) not in objs]
    if miss_c:
        objs.update({("compound", c.id): c for c in Compound.objects.filter(id__in=miss_c)})
    if miss_s:
        objs.update({("supplement", s.id): s for s in Supplement.objects.filter(id__in=miss_s)})

    rows = []
    for key in keys:
        obj = objs.get(key)
        if obj is None:
            continue
        # Most recent week that prescribes this row → its current name/dose/unit.
        rep = next((items[key] for _pf, items in reversed(week_plan) if key in items), None)
        logs = logs_by_key.get(key, [])

        cells = []
        for wi, w in enumerate(weeks):
            ws, we = w["start"], w["end"]
            pf, items = week_plan[wi]
            item = items.get(key)  # this row's plan THIS week (None if not prescribed then)

            taken_amt, taken_n, skipped_n = Decimal("0"), 0, 0
            for ta, amt, status in logs:
                if ws <= ta.date() <= we:
                    if status == "skipped":
                        skipped_n += 1
                    else:
                        taken_n += 1
                        taken_amt += Decimal(str(amt or 0))

            if item is not None:
                per = Decimal(str(item.dose_amount)) if item.dose_amount is not None else None
                tpd = times_per_day_count(item.times_of_day, item.frequency)
                sched_days = scheduled_dose_dates(
                    item.frequency, item.days_of_week, ws, we, dose_anchor(pf)
                )
                scheduled = len(sched_days) * tpd
                planned_amt = per * scheduled if per is not None else None
            else:
                scheduled, planned_amt = 0, None

            if ws > today:
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

        rows.append({**_matrix_row_meta(key, rep, obj), "cells": cells})

    rows.sort(key=lambda r: r["name"].lower())

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


# --- Week prep: daily pill-box plan (every-day baseline + per-day diffs) -------

WEEK_PREP_SLOTS = ["waking", "am", "noon", "pm", "night", "anytime"]
_SLOT_LABELS = {
    "waking": "Waking", "am": "AM", "noon": "Noon",
    "pm": "PM", "night": "Night", "anytime": "Anytime",
}
_WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
# An item joins the "every day" baseline if dosed on at least this many of the 7
# days, so a 6/7 item shows once with a single "skip" note instead of six rows.
_BASELINE_MIN_DAYS = 5
_COUNT_UNITS = {"capsule", "tablet", "softgel", "serving", "scoop", "gummy"}


def _fmt_qty(value) -> str:
    """Trim trailing zeros: '0.250'→'0.25', '10.000'→'10', '2.0'→'2'."""
    d = Decimal(str(value)).normalize()
    if d == d.to_integral():
        d = d.quantize(Decimal(1))
    return f"{d:f}"


def protocol_in_force(owner, on_date):
    """The protocol prescribed on `on_date`: the latest phase adjustment (across the
    owner's phases) on/before that date that sets a protocol, carried forward; else
    the active protocol. The per-day resolution behind Week prep."""
    from apps.core.models import PhaseAdjustment

    from .models import Protocol

    adj = (
        PhaseAdjustment.objects.filter(
            phase__owner=owner, protocol__isnull=False, effective_date__lte=on_date
        )
        .select_related("protocol")
        .order_by("-effective_date", "-id")
        .first()
    )
    if adj:
        return adj.protocol
    return Protocol.objects.filter(owner=owner, is_active=True).first()


def sync_active_protocol(owner, on_date):
    """Make the protocol prescribed by the phase-adjustment timeline the active one.

    Lets a future-dated phase adjustment take effect on its own — the reminder
    worker calls this each pass, so when the effective date arrives the prescribed
    protocol becomes active (and drives reminders + the quick-log grid) without a
    manual "Activate". Idempotent: only writes when the in-force protocol differs
    from the current active flag. Returns the protocol it activated, or None.
    """
    from .models import Protocol

    in_force = protocol_in_force(owner, on_date)
    if in_force is None or in_force.is_active:
        return None
    Protocol.objects.filter(owner=owner, is_active=True).update(is_active=False)
    in_force.is_active = True
    in_force.save(update_fields=["is_active"])
    return in_force


def _pillbox_items(protocol):
    """Oral compounds + supplements of a protocol (injectables / PRN excluded)."""
    out = []
    for it in protocol.items.select_related("compound", "supplement").all():
        if it.frequency in ("prn", "as_needed"):
            continue
        route = it.route or (it.compound.default_route if it.compound_id else "")
        if it.supplement_id or route == "oral":
            out.append(it)
    return out


def _pill_entry(item):
    """(key, entry) for a pill-box item; key identifies 'the same pill' across days."""
    qty = item.dose_amount if item.dose_amount is not None else Decimal("1")
    q = _fmt_qty(qty)
    unit = item.dose_unit or ""
    if item.supplement_id:
        u = f"{unit}s" if (unit in _COUNT_UNITS and Decimal(str(qty)) != 1) else unit
        amount = f"{q} {u}".strip() if u else f"{q}x"
        name, kind, ref = item.supplement.name, "supplement", item.supplement_id
    else:
        amount = f"{q} {unit}".strip()
        name, kind, ref = item.compound.name, "compound", item.compound_id
    return f"{kind}:{ref}:{q}:{unit}", {"amount": amount, "name": name, "kind": kind}


def _owner_slot_labels(owner):
    """Slot display labels for an owner: their custom names over the defaults."""
    from apps.notifications.models import DEFAULT_SLOT_LABELS, ReminderSettings

    labels = dict(_SLOT_LABELS)
    rs = ReminderSettings.objects.filter(owner=owner).first()
    if rs:
        for slot in DEFAULT_SLOT_LABELS:
            labels[slot] = rs.label(slot)
    return labels


def week_prep_plan(owner, start_date):
    """Weekly pill-box plan for [start_date, +6 days].

    Resolves the protocol in force each day, collects the oral compounds +
    supplements due per time-of-day slot, then factors out an "every day" baseline
    (items dosed on >= _BASELINE_MIN_DAYS of the 7 days) so each day only lists its
    deviations: `added` (extra that day) and `removed` (baseline skipped that day).
    Slot labels honour the owner's custom names from their reminder settings.
    """
    days = [start_date + timedelta(days=i) for i in range(7)]
    labels = _owner_slot_labels(owner)
    item_cache: dict[int, list] = {}

    def items_for(proto):
        if proto is None:
            return []
        if proto.id not in item_cache:
            item_cache[proto.id] = _pillbox_items(proto)
        return item_cache[proto.id]

    # slot -> key -> {"entry": {...}, "days": set(day_index)}
    slots: dict[str, dict] = {s: {} for s in WEEK_PREP_SLOTS}
    day_meta = []
    protocols_seen: list[str] = []
    for i, d in enumerate(days):
        proto = protocol_in_force(owner, d)
        day_meta.append(
            {"date": d.isoformat(), "weekday": d.weekday(),
             "label": _WEEKDAY_LABELS[d.weekday()],
             "protocol": proto.name if proto else None}
        )
        if proto and proto.name not in protocols_seen:
            protocols_seen.append(proto.name)
        anchor = dose_anchor(proto)
        for it in items_for(proto):
            if not scheduled_dose_dates(it.frequency, it.days_of_week, d, d, anchor):
                continue
            key, entry = _pill_entry(it)
            for t in (it.times_of_day or ["anytime"]):
                slot = t if t in slots else "anytime"
                bucket = slots[slot].setdefault(key, {"entry": entry, "days": set()})
                bucket["days"].add(i)

    everyday = []
    added: dict[int, dict] = {i: {} for i in range(7)}
    removed: dict[int, dict] = {i: {} for i in range(7)}
    for slot in WEEK_PREP_SLOTS:
        base = []
        for info in slots[slot].values():
            present, entry = info["days"], info["entry"]
            if len(present) >= _BASELINE_MIN_DAYS:
                base.append(entry)
                for i in range(7):
                    if i not in present:
                        removed[i].setdefault(slot, []).append(entry)
            else:
                for i in present:
                    added[i].setdefault(slot, []).append(entry)
        if base:
            everyday.append({"slot": slot, "slot_label": labels[slot], "entries": base})

    def _slots(by_day):
        return [
            {"slot": s, "slot_label": labels[s], "entries": by_day[s]}
            for s in WEEK_PREP_SLOTS if s in by_day
        ]

    days_out = [
        {**day_meta[i], "added": _slots(added[i]), "removed": _slots(removed[i])}
        for i in range(7)
    ]
    return {
        "start": days[0].isoformat(),
        "end": days[-1].isoformat(),
        "protocols": protocols_seen,
        "everyday": everyday,
        "days": days_out,
    }
