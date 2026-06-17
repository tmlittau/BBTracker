"""Body-analysis math: anthropometric body composition, fat distribution, energy
(BMR / TDEE incl. an adaptive expenditure estimate) and bloodwork-derived ratios,
plus a rule-based assessment engine.

Everything here is closed-form (O(1)) — no ML, no heavy compute. Pure helpers take
floats and return floats/None; the DB-aware `body_analysis` aggregator at the bottom
stitches the user's data together (cross-app imports are function-local, like core).
Nothing here is medical advice: every output carries a source + caveat for the UI.
"""
from __future__ import annotations

import math
from datetime import timedelta

# kcal per kg of body-mass change (mixed lean/fat tissue approximation) — used to
# turn a weight trend into an energy figure for the adaptive expenditure estimate.
ENERGY_PER_KG = 7700.0


def _f(v):
    """Best-effort float, or None."""
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


# --- Body composition ---------------------------------------------------------


def navy_body_fat(sex, height_cm, neck_cm, waist_cm, hip_cm=None):
    """US Navy (Hodgdon-Beckett) body-fat %; ~±3-4% vs DEXA. None if insufficient."""
    h, neck, waist = _f(height_cm), _f(neck_cm), _f(waist_cm)
    if not (h and neck and waist):
        return None
    try:
        if sex == "female":
            hip = _f(hip_cm)
            if not hip or (waist + hip - neck) <= 0:
                return None
            val = 163.205 * math.log10(waist + hip - neck) - 97.684 * math.log10(h) - 78.387
        else:
            if (waist - neck) <= 0:
                return None
            val = 86.010 * math.log10(waist - neck) - 70.041 * math.log10(h) + 36.76
    except ValueError:
        return None
    return round(val, 1) if 2 < val < 70 else None


def rfm(sex, height_cm, waist_cm):
    """Relative Fat Mass (Woolcott 2018) body-fat % from height/waist. None if missing."""
    h, waist = _f(height_cm), _f(waist_cm)
    if not (h and waist):
        return None
    val = 64.0 - 20.0 * (h / waist) + (12.0 if sex == "female" else 0.0)
    return round(val, 1) if 2 < val < 70 else None


def lean_fat_mass(weight_kg, body_fat_pct):
    """(fat_mass_kg, lean_mass_kg) from weight + body-fat %."""
    w, bf = _f(weight_kg), _f(body_fat_pct)
    if w is None or bf is None:
        return None, None
    fat = w * bf / 100.0
    return round(fat, 2), round(w - fat, 2)


def ffmi(fat_free_mass_kg, height_cm):
    """(ffmi, normalized_ffmi) — fat-free-mass index + height-normalized variant."""
    ffm, h = _f(fat_free_mass_kg), _f(height_cm)
    if not (ffm and h):
        return None, None
    hm = h / 100.0
    raw = ffm / (hm * hm)
    return round(raw, 1), round(raw + 6.1 * (1.8 - hm), 1)


# --- Fat distribution ---------------------------------------------------------


def waist_to_height(waist_cm, height_cm):
    waist, h = _f(waist_cm), _f(height_cm)
    return round(waist / h, 3) if waist and h else None


def waist_to_hip(waist_cm, hip_cm):
    waist, hip = _f(waist_cm), _f(hip_cm)
    return round(waist / hip, 3) if waist and hip else None


# --- Energy -------------------------------------------------------------------


def bmr_mifflin(sex, weight_kg, height_cm, age):
    """Mifflin-St Jeor BMR (kcal/day). None if inputs missing."""
    w, h, a = _f(weight_kg), _f(height_cm), _f(age)
    if not (w and h) or a is None:
        return None
    s = -161.0 if sex == "female" else 5.0
    return round(10.0 * w + 6.25 * h - 5.0 * a + s)


def bmr_katch_mcardle(fat_free_mass_kg):
    """FFM-based BMR (Katch-McArdle) — more accurate for lean/muscular people."""
    ffm = _f(fat_free_mass_kg)
    return round(370.0 + 21.6 * ffm) if ffm else None


def _slope_per_day(points):
    """Least-squares slope (y per unit x) for [(x, y)]; None if degenerate."""
    n = len(points)
    if n < 2:
        return None
    mx = sum(p[0] for p in points) / n
    my = sum(p[1] for p in points) / n
    denom = sum((x - mx) ** 2 for x, _ in points)
    if denom == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in points) / denom


def adaptive_tdee(intake_by_day, weight_by_day, min_days=10):
    """Estimate expenditure from the energy-balance identity over a window.

    TDEE ≈ mean daily intake − (kg/day weight slope × ENERGY_PER_KG). Needs at least
    `min_days` weight points (least-squares slope to damp daily noise) and enough
    logged-intake days. Returns a dict or None when there isn't enough data.
    """
    weights = sorted((d, _f(w)) for d, w in weight_by_day.items() if _f(w))
    if len(weights) < min_days:
        return None
    base = weights[0][0]
    slope = _slope_per_day([((d - base).days, w) for d, w in weights])
    if slope is None:
        return None
    intakes = [_f(v) for v in intake_by_day.values() if _f(v) and _f(v) > 0]
    if len(intakes) < max(7, min_days // 2):
        return None
    mean_intake = sum(intakes) / len(intakes)
    tdee = mean_intake - slope * ENERGY_PER_KG
    if not (800 < tdee < 8000):  # implausible → not enough signal yet
        return None
    span = (weights[-1][0] - weights[0][0]).days + 1
    return {
        "tdee": round(tdee),
        "weight_slope_kg_wk": round(slope * 7, 3),
        "days": span,
        "intake_days": len(intakes),
        "confidence": "high" if span >= 21 and len(intakes) >= 14 else "medium",
    }


# --- DB-aware aggregator ------------------------------------------------------


def _age(dob, on_date):
    if not dob:
        return None
    return on_date.year - dob.year - ((on_date.month, on_date.day) < (dob.month, dob.day))


def _latest_measurements(owner, on_date):
    """{type: {value, date, method}} — most recent measurement per type on/before date."""
    from .models import BodyMeasurement

    out: dict = {}
    for m in (
        BodyMeasurement.objects.filter(owner=owner, date__lte=on_date).order_by("date")
    ):
        out[m.type] = {"value": m.value, "date": m.date, "method": m.method}  # latest wins
    return out


def _measurements_payload(latest):
    from .models import unit_for

    return [
        {
            "type": t,
            "value": _f(m["value"]),
            "unit": unit_for(t),
            "date": m["date"].isoformat(),
            "method": m["method"],
        }
        for t, m in latest.items()
    ]


def _intake_by_day(owner, start, end):
    try:
        from apps.nutrition.services import macro_totals_by_day
    except ImportError:
        return {}
    return {d: v["calories"] for d, v in macro_totals_by_day(owner, start, end).items()}


def _bloodwork_metrics(owner):
    """Latest value per blood marker (one query) + a few atherogenic ratios.

    Marker slugs are matched defensively (the SI seed names can vary), and TG/HDL is
    converted to mg/dL so the conventional cutoff applies; LDL/HDL + ApoB/ApoA1 are
    unitless ratios.
    """
    from apps.protocols.models import BloodResult

    latest: dict = {}
    for r in (
        BloodResult.objects.filter(owner=owner).select_related("marker").order_by("measured_on")
    ):
        latest[r.marker.slug] = _f(r.value)  # ascending → latest wins

    def pick(*slugs):
        for s in slugs:
            if latest.get(s) is not None:
                return latest[s]
        return None

    hdl = pick("hdl", "hdl_cholesterol", "hdl_c")
    ldl = pick("ldl", "ldl_cholesterol", "ldl_c")
    tg = pick("triglycerides", "triglyceride", "trig")
    apob = pick("apolipoprotein_b", "apob", "apo_b")
    apoa1 = pick("apolipoprotein_a1", "apoa1", "apo_a1")

    ratios: dict = {}
    if tg and hdl:
        ratios["tg_hdl"] = round((tg * 88.57) / (hdl * 38.67), 2)  # SI → mg/dL-equivalent
    if ldl and hdl:
        ratios["ldl_hdl"] = round(ldl / hdl, 2)
    if apob and apoa1:
        ratios["apob_apoa1"] = round(apob / apoa1, 2)
    return {"ratios": ratios}


def body_analysis(owner, on_date):
    """The full Body Analysis payload for `on_date` across profile, check-ins,
    measurements, nutrition and bloodwork."""
    from apps.diary.models import CheckIn

    profile = getattr(owner, "profile", None)
    sex = profile.sex if profile else "unspecified"
    height = _f(profile.height_cm) if profile else None
    age = _age(getattr(profile, "date_of_birth", None), on_date) if profile else None

    check_ins = list(CheckIn.objects.filter(owner=owner, date__lte=on_date).order_by("-date"))
    weight = next((_f(c.bodyweight) for c in check_ins if _f(c.bodyweight)), None)
    bp = next(((c.systolic, c.diastolic) for c in check_ins if c.systolic and c.diastolic), None)

    latest = _latest_measurements(owner, on_date)
    waist = _f(latest["waist"]["value"]) if "waist" in latest else None
    neck = _f(latest["neck"]["value"]) if "neck" in latest else None
    hip = _f(latest["hip"]["value"]) if "hip" in latest else None

    # Body fat: measured (DEXA/BIA…) > Navy circumference > RFM.
    if "body_fat" in latest:
        body_fat = _f(latest["body_fat"]["value"])
        bf_source = latest["body_fat"]["method"] or "measured"
    elif (navy := navy_body_fat(sex, height, neck, waist, hip)) is not None:
        body_fat, bf_source = navy, "navy"
    elif (r := rfm(sex, height, waist)) is not None:
        body_fat, bf_source = r, "rfm"
    else:
        body_fat, bf_source = None, None

    fat_mass, lean_mass = lean_fat_mass(weight, body_fat)
    raw_ffmi, norm_ffmi = ffmi(lean_mass, height)

    composition = {
        "weight_kg": weight,
        "height_cm": height,
        "body_fat_pct": body_fat,
        "body_fat_source": bf_source,
        "fat_mass_kg": fat_mass,
        "lean_mass_kg": lean_mass,
        "ffmi": raw_ffmi,
        "ffmi_normalized": norm_ffmi,
    }
    distribution = {
        "waist_to_height": waist_to_height(waist, height),
        "waist_to_hip": waist_to_hip(waist, hip),
        "rfm": rfm(sex, height, waist),
    }

    bmr_m = bmr_mifflin(sex, weight, height, age)
    bmr_lbm = bmr_katch_mcardle(lean_mass)
    window_start = on_date - timedelta(days=27)
    weight_by_day = {
        c.date: _f(c.bodyweight)
        for c in check_ins
        if c.date >= window_start and _f(c.bodyweight)
    }
    adaptive = adaptive_tdee(_intake_by_day(owner, window_start, on_date), weight_by_day)
    energy = {
        "bmr_mifflin": bmr_m,
        "bmr_katch_mcardle": bmr_lbm,
        "bmr": bmr_lbm or bmr_m,  # prefer FFM-based when body fat is known
        "adaptive": adaptive,
    }
    if adaptive:
        recent = _intake_by_day(owner, on_date - timedelta(days=6), on_date)
        vals = [_f(v) for v in recent.values() if _f(v) and _f(v) > 0]
        if vals:
            energy["recent_intake"] = round(sum(vals) / len(vals))
            energy["balance"] = round(energy["recent_intake"] - adaptive["tdee"])
        if energy["bmr"]:
            energy["activity_factor"] = round(adaptive["tdee"] / energy["bmr"], 2)

    bloodwork = _bloodwork_metrics(owner)
    assessments = _assess(sex, composition, distribution, energy, bp, bloodwork)

    return {
        "date": on_date.isoformat(),
        "sex": sex,
        "composition": composition,
        "distribution": distribution,
        "energy": energy,
        "blood_pressure": ({"systolic": bp[0], "diastolic": bp[1]} if bp else None),
        "bloodwork": bloodwork,
        "assessments": assessments,
        "measurements": _measurements_payload(latest),
    }


# --- Rule-based assessment engine ---------------------------------------------


def _assess(sex, comp, dist, energy, bp, blood):
    """Turn the metrics into explained good/watch/risk cards (deterministic)."""
    out = []

    whtr = dist.get("waist_to_height")
    if whtr is not None:
        if whtr < 0.4:
            status, detail = "watch", "Below 0.4 — unusually low; check the waist value."
        elif whtr < 0.5:
            status, detail = "good", "Healthy central-fat range (below 0.5)."
        elif whtr < 0.6:
            status, detail = "watch", "0.5–0.6 — raised central adiposity; trend the waist down."
        else:
            status, detail = "risk", "Above 0.6 — high central-adiposity / cardiometabolic risk."
        out.append(_card("whtr", "Waist-to-height", status, whtr, detail,
                         "Ashwell meta-analysis (0.5 cutoff)"))

    nffmi = comp.get("ffmi_normalized")
    if nffmi is not None and sex != "female":
        if nffmi >= 25:
            detail = "At/above ~25 — the documented drug-free upper limit."
        elif nffmi >= 22:
            detail = "Highly muscular (22–25)."
        else:
            detail = "Fat-free-mass index, height-normalized."
        out.append(_card("ffmi", "FFMI (normalized)", "good", nffmi, detail, "Kouri 1995"))

    bf = comp.get("body_fat_pct")
    if bf is not None:
        if sex == "female":
            low, bands = 14, [(24, "Athletic/fit range."), (32, "Average range.")]
        else:
            low, bands = 6, [(14, "Athletic/fit range."), (20, "Average range.")]
        status, detail = "good", "Above average — a cut would improve markers."
        for cap, text in bands:
            if bf < cap:
                status, detail = "good", text
                break
        else:
            status = "watch"
        if bf < low:
            status, detail = "watch", "Very low — sustainable only short-term (e.g. peak week)."
        out.append(_card("body_fat", "Body fat %", status, bf, detail,
                         comp.get("body_fat_source")))

    bal = energy.get("balance")
    if bal is not None and energy.get("adaptive"):
        rate = energy["adaptive"]["weight_slope_kg_wk"]
        direction = "deficit" if bal < 0 else "surplus" if bal > 0 else "maintenance"
        out.append(_card("energy_balance", "Energy balance", "good", bal,
                         f"~{abs(bal)} kcal/day {direction}; weight trend {rate:+.2f} kg/wk.",
                         "Adaptive expenditure (intake vs weight trend)"))

    if bp:
        sysv, diav = bp
        if sysv < 120 and diav < 80:
            status, detail = "good", "Normal."
        elif sysv < 130 and diav < 80:
            status, detail = "watch", "Elevated."
        elif sysv < 140 or diav < 90:
            status, detail = "watch", "Stage 1 hypertension range."
        else:
            status, detail = "risk", "Stage 2 range — monitor closely (esp. on anabolics)."
        out.append(_card("blood_pressure", "Blood pressure", status, f"{sysv}/{diav}", detail,
                         "ACC/AHA 2017"))

    ratios = blood.get("ratios", {})
    if "apob_apoa1" in ratios:
        v = ratios["apob_apoa1"]
        status = "good" if v < 0.7 else "watch" if v < 0.9 else "risk"
        out.append(_card("apob_apoa1", "ApoB/ApoA1", status, v,
                         "Atherogenic-particle ratio.", "AMORIS"))
    elif "ldl_hdl" in ratios:
        v = ratios["ldl_hdl"]
        status = "good" if v < 2.5 else "watch" if v < 3.5 else "risk"
        out.append(_card("ldl_hdl", "LDL/HDL", status, v, "Cholesterol ratio.", "Lipid guidelines"))

    return out


def _card(key, label, status, value, detail, source):
    return {
        "key": key,
        "label": label,
        "status": status,
        "value": value,
        "detail": detail,
        "source": source,
    }
