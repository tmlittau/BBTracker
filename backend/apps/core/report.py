"""Shareable check-in report → PDF (WeasyPrint).

Assembles a coach-facing progress report for a date window (typically a phase):
snapshot stats, weight trend, progress photos, training + nutrition summaries,
the protocol in force, bloodwork and final measurements. Sensitive sections
(protocols, bloodwork) are gated by the caller's `include` set. Light theme for
print. Reuses analysis.body_analysis so the numbers match the Analysis tab.
"""
from __future__ import annotations

import base64
import html

ALL_SECTIONS = {"training", "nutrition", "photos", "protocols", "bloodwork"}
_RELAXED_POSES = ["front-relaxed", "back-relaxed", "side-relaxed-left", "side-relaxed-right"]


def _f(v, d=1):
    return "—" if v is None else f"{float(v):.{d}f}"


def _esc(v):
    return html.escape(str(v)) if v is not None else ""


def _amt(value, unit):
    """Format a dose amount without trailing Decimal zeros, e.g. 250.000mg → '250 mg'."""
    if value is None:
        return ""
    s = f"{value}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return f"{s} {unit}"


def _weight_chart_svg(points):
    """Tiny inline SVG line of (iso_date, weight) over the window."""
    pts = [(d, float(w)) for d, w in points if w is not None]
    if len(pts) < 2:
        return ""
    w, h, pad = 680, 150, 8
    ys = [p[1] for p in pts]
    lo, hi = min(ys), max(ys)
    span = (hi - lo) or 1.0
    n = len(pts)

    def sx(i):
        return pad + (w - 2 * pad) * (i / (n - 1))

    def sy(v):
        return pad + (h - 2 * pad) * (1 - (v - lo) / span)

    line = " ".join(f"{sx(i):.1f},{sy(v):.1f}" for i, (_, v) in enumerate(pts))
    return (
        f'<svg viewBox="0 0 {w} {h}" width="100%" preserveAspectRatio="none" '
        f'xmlns="http://www.w3.org/2000/svg">'
        f'<polyline fill="none" stroke="#f97316" stroke-width="2" points="{line}"/>'
        f'<text x="{pad}" y="14" font-size="11" fill="#999">{hi:.1f} kg</text>'
        f'<text x="{pad}" y="{h - 2}" font-size="11" fill="#999">{lo:.1f} kg</text>'
        f"</svg>"
    )


def _b64(storage, key):
    try:
        return "data:image/jpeg;base64," + base64.b64encode(storage.get(key)).decode()
    except Exception:
        return None


def _stat(label, value, sub=""):
    sub_html = f'<div class="sub">{_esc(sub)}</div>' if sub else ""
    return (
        f'<div class="stat"><div class="lbl">{_esc(label)}</div>'
        f'<div class="val">{value}</div>{sub_html}</div>'
    )


def checkin_report_html(user, start, end, include):
    from apps.analysis.services import body_analysis
    from apps.diary.models import CheckIn, ProgressPhoto
    from apps.diary.storage import get_storage

    include = set(include) & ALL_SECTIONS
    a = body_analysis(user, end, window_start=start)
    comp = a["composition"]
    energy = a["energy"]
    adaptive = energy.get("adaptive") or {}
    name = (user.get_full_name() or "").strip() or user.email

    # --- snapshot stats (always shown) ---
    stats = "".join([
        _stat("Body fat", f"{_f(comp.get('body_fat_pct'))}%",
              f"{comp.get('body_fat_source') or '—'} · lean {_f(comp.get('lean_mass_kg'))} kg"),
        _stat("FFMI (norm.)", _f(comp.get("ffmi_normalized")), f"raw {_f(comp.get('ffmi'))}"),
        _stat("Waist-to-height", _f(a["distribution"].get("waist_to_height"), 2), "healthy < 0.5"),
        _stat("Expenditure", f"{adaptive.get('tdee', '—')} kcal",
              f"{adaptive.get('confidence', '')} conf."),
        _stat("Energy balance",
              (f"{energy['balance']:+d} kcal" if energy.get("balance") is not None else "—"),
              "avg vs expenditure"),
        _stat("BMR", f"{energy.get('bmr') or '—'} kcal", ""),
        _stat("Bodyweight", f"{_f(comp.get('weight_kg'))} kg", ""),
    ])

    sections = []

    # --- weight trend (always) ---
    weights = [
        (c.date.isoformat(), c.bodyweight)
        for c in CheckIn.objects.filter(owner=user, date__gte=start, date__lte=end).order_by("date")
        if c.bodyweight is not None
    ]
    chart = _weight_chart_svg(weights)
    if chart:
        sections.append(f'<div class="card"><h2>Weight trend</h2>{chart}</div>')

    # --- coach insights (always) ---
    if a.get("insights"):
        rows = "".join(
            f'<li><b>{_esc(i["title"])}</b> — {_esc(i["detail"])}</li>' for i in a["insights"]
        )
        sections.append(f'<div class="card"><h2>Coach insights</h2><ul>{rows}</ul></div>')

    # --- assessments (always) ---
    if a.get("assessments"):
        rows = "".join(
            f'<tr><td>{_esc(x["label"])}</td><td class="num">{_esc(x["value"])}</td>'
            f'<td>{_esc(x["detail"])}</td></tr>'
            for x in a["assessments"]
        )
        sections.append(f'<div class="card"><h2>Assessments</h2><table>{rows}</table></div>')

    # --- progress photos ---
    if "photos" in include:
        storage = get_storage()
        imgs = []
        for slug in _RELAXED_POSES:
            p = (
                ProgressPhoto.objects.filter(
                    owner=user, pose__slug=slug, taken_on__gte=start, taken_on__lte=end
                )
                .order_by("-taken_on").first()
            )
            uri = _b64(storage, p.thumb_key or p.object_key) if p else None
            if uri:
                imgs.append(
                    f'<figure><img src="{uri}"/>'
                    f'<figcaption>{_esc(p.pose.name)} · {p.taken_on}</figcaption></figure>'
                )
        if imgs:
            sections.append(
                f'<div class="card"><h2>Progress photos</h2>'
                f'<div class="photos">{"".join(imgs)}</div></div>'
            )

    # --- training summary ---
    if "training" in include:
        sections.append(_training_section(user, start, end))

    # --- nutrition summary ---
    if "nutrition" in include:
        sections.append(_nutrition_section(user, start, end))

    # --- protocol in force ---
    if "protocols" in include:
        sections.append(_protocol_section(user, end))

    # --- bloodwork ---
    if "bloodwork" in include:
        trends = a.get("bloodwork", {}).get("trends", [])
        if trends:
            rows = "".join(
                f'<tr><td>{_esc(t["marker"])}</td>'
                f'<td class="num">{_esc(t["value"])} {_esc(t["unit"])}</td>'
                f'<td>{_esc(t.get("note", ""))}</td></tr>'
                for t in trends
            )
            sections.append(
                f'<div class="card"><h2>Bloodwork (latest in range)</h2>'
                f'<table>{rows}</table></div>'
            )

    # --- final measurements (always) ---
    meas = a.get("measurements") or []
    if meas:
        rows = "".join(
            f'<tr><td>{_esc(m["type"].replace("_", " ").title())}</td>'
            f'<td class="num">{_esc(m["value"])} {_esc(m["unit"])}</td>'
            f'<td>{_esc(m["date"])}</td></tr>'
            for m in meas
        )
        sections.append(f'<div class="card"><h2>Final measurements</h2><table>{rows}</table></div>')

    body = "\n".join(sections)
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{_CSS}</style></head><body>
<header>
  <div class="brand">BBTracker</div>
  <h1>Check-in report</h1>
  <div class="meta">{_esc(name)} · {start.isoformat()} → {end.isoformat()}</div>
</header>
<div class="stats">{stats}</div>
{body}
<footer>Generated by BBTracker · estimates from anthropometric / PK formulas —
informational, not medical advice.</footer>
</body></html>"""


def _training_section(user, start, end):
    from apps.training.models import LoggedSet, WorkoutSession

    sessions = WorkoutSession.objects.filter(
        owner=user, started_at__date__gte=start, started_at__date__lte=end
    )
    n_sessions = sessions.count()
    sets = LoggedSet.objects.filter(
        logged_exercise__session__owner=user,
        logged_exercise__session__started_at__date__gte=start,
        logged_exercise__session__started_at__date__lte=end,
    )
    n_pr = sets.filter(is_pr=True).count()
    best: dict = {}
    for name, e1 in sets.filter(e1rm__isnull=False).values_list(
        "logged_exercise__exercise__name", "e1rm"
    ):
        if e1 is not None and (name not in best or e1 > best[name]):
            best[name] = e1
    top = sorted(best.items(), key=lambda kv: kv[1], reverse=True)[:6]
    rows = "".join(
        f'<tr><td>{_esc(n)}</td><td class="num">{_f(v)} kg e1RM</td></tr>' for n, v in top
    )
    return (
        f'<div class="card"><h2>Training</h2>'
        f'<p class="kv">{n_sessions} sessions · {n_pr} PRs</p>'
        f'{("<table>" + rows + "</table>") if rows else ""}</div>'
    )


def _nutrition_section(user, start, end):
    from apps.nutrition.models import NutritionTarget
    from apps.nutrition.services import macro_totals_by_day

    by_day = macro_totals_by_day(user, start, end) or {}
    days = [v for v in by_day.values() if (v.get("calories") or 0) > 0]
    n = len(days)
    avg_kcal = round(sum(float(v.get("calories") or 0) for v in days) / n) if n else None
    avg_pro = round(sum(float(v.get("protein_g") or 0) for v in days) / n) if n else None
    total_days = (end - start).days + 1
    target = NutritionTarget.objects.filter(owner=user, is_active=True).first()
    tline = f" · target {int(target.calories)} kcal" if target and target.calories else ""
    return (
        f'<div class="card"><h2>Nutrition</h2>'
        f'<p class="kv">logged {n}/{total_days} days{tline}</p>'
        f'<p class="kv">avg {avg_kcal or "—"} kcal · {avg_pro or "—"} g protein</p></div>'
    )


def _protocol_section(user, on_date):
    from apps.protocols.services import protocol_in_force

    proto = protocol_in_force(user, on_date)
    if not proto:
        return '<div class="card"><h2>Protocol</h2><p class="kv">No protocol in force.</p></div>'
    rows = ""
    for it in proto.items.select_related("compound", "supplement").all():
        ref = it.compound or it.supplement
        if not ref:
            continue
        amt = _amt(it.dose_amount, it.dose_unit)
        freq = _esc(it.get_frequency_display())
        route = f" · {_esc(it.route)}" if it.route else ""
        rows += (
            f'<tr><td>{_esc(ref.name)}</td><td class="num">{_esc(amt)}</td>'
            f'<td>{freq}{route}</td></tr>'
        )
    return f'<div class="card"><h2>Protocol · {_esc(proto.name)}</h2><table>{rows}</table></div>'


def build_checkin_report_pdf(user, start, end, include):
    """Return (filename, pdf_bytes)."""
    from weasyprint import HTML

    html_str = checkin_report_html(user, start, end, include)
    pdf = HTML(string=html_str).write_pdf()
    slug = (user.get_full_name() or user.email.split("@")[0]).strip().replace(" ", "-").lower()
    return f"bbtracker-checkin-{slug}-{end.isoformat()}.pdf", pdf


_CSS = """
@page { size: A4; margin: 16mm 14mm; }
* { box-sizing: border-box; }
body { font-family: 'DejaVu Sans', sans-serif; color: #1f2937; font-size: 11px; margin: 0; }
header { border-bottom: 3px solid #f97316; padding-bottom: 8px; margin-bottom: 12px; }
.brand { font-size: 12px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase;
         color: #f97316; }
h1 { font-size: 22px; margin: 2px 0 2px; }
.meta { color: #6b7280; font-size: 12px; }
.stats { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
.stat { flex: 1 1 22%; min-width: 120px; border: 1px solid #e5e7eb; border-radius: 6px;
        padding: 7px 9px; }
.stat .lbl { font-size: 9px; text-transform: uppercase; letter-spacing: .06em; color: #9ca3af; }
.stat .val { font-size: 16px; font-weight: 700; }
.stat .sub { font-size: 9px; color: #9ca3af; }
.card { border: 1px solid #e5e7eb; border-radius: 8px; padding: 10px 12px; margin-bottom: 10px;
        break-inside: avoid; }
.card h2 { font-size: 13px; margin: 0 0 6px; color: #ea580c; }
.kv { margin: 2px 0; }
table { width: 100%; border-collapse: collapse; }
td { padding: 3px 4px; border-top: 1px solid #f1f5f9; vertical-align: top; }
td.num { white-space: nowrap; font-variant-numeric: tabular-nums; font-weight: 600; width: 1%; }
ul { margin: 4px 0; padding-left: 16px; }
li { margin: 2px 0; }
.photos { display: flex; gap: 8px; }
.photos figure { margin: 0; flex: 1; text-align: center; }
.photos img { width: 100%; height: 200px; object-fit: cover; border-radius: 6px; }
.photos figcaption { font-size: 9px; color: #9ca3af; margin-top: 2px; }
footer { margin-top: 12px; padding-top: 6px; border-top: 1px solid #e5e7eb; color: #9ca3af;
         font-size: 9px; }
"""
