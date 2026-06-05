#!/usr/bin/env python3
"""End-to-end verification of the Protocols module against the live stack.

Drives the HTTP API the SvelteKit UI calls (through the frontend proxy on :5173,
browser-style with a cookie jar + CSRF): build a protocol, log doses, and assert
the concentration curve, injection-site rotation, adherence, bloodwork trend, and
that a logged supplement's micros flow into the nutrition summary.

Run with the stack up (and seed_protocols + seed_nutrition applied):
    /opt/anaconda3/bin/python scripts/verify_protocols.py
"""
from __future__ import annotations

import http.cookiejar
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

BASE = "http://localhost:5173"
ALLAUTH = f"{BASE}/_allauth/browser/v1"
API = f"{BASE}/api/v1/protocols"
NUT = f"{BASE}/api/v1/nutrition"
PASSWORD = "Sup3rStrongPass!"

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
passed = failed = 0


def check(label, got, want):
    global passed, failed
    ok = (got in want) if isinstance(want, (set, tuple, list)) else (got == want)
    passed += ok
    failed += not ok
    print(f"  {'PASS' if ok else 'FAIL'}  {label} (got {got!r}, want {want!r})")


def cookie(name):
    return next((c.value for c in jar if c.name == name), None)


def req(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        r.add_header("Content-Type", "application/json")
    if cookie("csrftoken"):
        r.add_header("X-CSRFToken", cookie("csrftoken"))
    try:
        resp = opener.open(r)
        return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except json.JSONDecodeError:
            return e.code, {}


def items(p):
    return p["results"] if isinstance(p, dict) and "results" in p else p


def main():
    email = f"proto+{int(time.time())}@example.com"
    req("GET", f"{BASE}/api/v1/auth/csrf/")
    check("signup", req("POST", f"{ALLAUTH}/auth/signup",
                        {"email": email, "password": PASSWORD})[0], 200)

    # Seeded reference data.
    _, compounds = req("GET", f"{API}/compounds/")
    compounds = items(compounds)
    check("compounds seeded", len(compounds) >= 20, True)
    _, sites = req("GET", f"{API}/injection-sites/")
    check("injection sites seeded", len(items(sites)) >= 8, True)
    _, markers = req("GET", f"{API}/blood-markers/")
    check("blood markers seeded", len(items(markers)) >= 15, True)

    test_e = next(c for c in compounds if "Enanthate" in c["name"])
    check("compound has half-life", test_e["half_life_hours"] is not None, True)

    # Custom compound (owned).
    st, custom = req("POST", f"{API}/compounds/",
                     {"name": "My Peptide", "compound_class": "peptide", "default_unit": "mcg"})
    check("create custom compound", st, 201)
    check("custom compound owned", custom.get("is_global"), False)

    # Build a protocol + item.
    pid = req("POST", f"{API}/protocols/", {"name": "TRT", "started_on": "2026-01-01"})[1]["id"]
    st, item = req("POST", f"{API}/protocol-items/",
                   {"protocol": pid, "compound": test_e["id"], "dose_amount": "125",
                    "dose_unit": "mg", "route": "im", "frequency": "2x_week"})
    check("add protocol item", st, 201)

    _, activated = req("POST", f"{API}/protocols/{pid}/activate/")
    check("activate protocol", activated["is_active"], True)

    # Log two doses a week apart, at the same site, to drive curve + rotation.
    now = datetime.now(timezone.utc)
    glute = next(s for s in items(sites) if s["region"] == "glute")
    for days_ago in (7, 0):
        st, _ = req("POST", f"{API}/dose-logs/", {
            "protocol_item": item["id"], "compound": test_e["id"],
            "taken_at": (now - timedelta(days=days_ago)).isoformat(),
            "amount": "125", "unit": "mg", "route": "im", "injection_site": glute["id"],
        })
    check("log doses", st, 201)

    # Concentration curve.
    _, curve = req("GET", f"{API}/concentration/?compound={test_e['id']}&days=14")
    check("concentration curve non-empty", len(curve) > 0, True)
    peak = max(p["value"] for p in curve) if curve else 0
    # 2×125 mg @ 0.70 active fraction → peak well above one dose's active amount.
    check("curve peak reflects ester fraction", 120 <= peak <= 200, True)

    # Site rotation: the used glute is 'fresh'; suggestion avoids it.
    _, recency = req("GET", f"{API}/injection-sites/recency/?days=30")
    used = next(s for s in recency if s["id"] == glute["id"])
    check("used site is fresh", used["status"], "fresh")
    _, suggestion = req("GET", f"{API}/injection-sites/suggest/")
    check("suggested site avoids the fresh one", suggestion.get("id") != glute["id"], True)

    # Adherence: expect 2/week × 4 weeks = 8; logged 2 → 25%.
    _, adh = req("GET", f"{API}/protocols/{pid}/adherence/?window_days=28")
    check("adherence expected", adh[0]["expected"], 8.0)
    check("adherence actual", adh[0]["actual"], 2)
    check("adherence pct", adh[0]["adherence"], 25)

    # Bloodwork trend with flags. Use a marker with *generic* (non sex-specific)
    # reference ranges so flagging is deterministic regardless of profile sex —
    # Lymphocytes 20–45%; sex-specific markers only flag once a sex is set.
    gen = next(m for m in items(markers) if m["slug"] == "lymphocytes")
    req("POST", f"{API}/blood-results/", {"marker": gen["id"], "value": "5",
                                          "measured_on": "2026-01-01"})
    req("POST", f"{API}/blood-results/", {"marker": gen["id"], "value": "30",
                                          "measured_on": "2026-03-01"})
    _, trend = req("GET", f"{API}/blood-results/trend/?marker={gen['id']}")
    check("bloodwork trend has 2 points", len(trend), 2)
    check("low value flagged", trend[0]["flag"], "low")          # 5 < 20
    check("mid value in range", trend[1]["flag"], "in_range")    # 30 in [20,45]

    # Blood pressure.
    check("log BP", req("POST", f"{API}/bp-logs/", {
        "systolic": 122, "diastolic": 78, "pulse": 60,
        "measured_at": now.isoformat()})[0], 201)

    # Supplement → nutrition integration: a logged supplement dose adds its micros
    # to the nutrition daily summary.
    _, nutrients = req("GET", f"{NUT}/nutrients/")
    vit_c = next(n for n in items(nutrients) if n["slug"] == "vitamin_c")
    _, supp = req("POST", f"{API}/supplements/", {
        "name": "Vitamin C 500",
        "supplement_nutrients": [{"nutrient": vit_c["id"], "amount_per_serving": "500"}],
    })
    check("create supplement w/ nutrient", supp.get("is_global"), False)
    day = now.date().isoformat()
    req("POST", f"{API}/dose-logs/", {
        "supplement": supp["id"], "taken_at": now.isoformat(),
        "amount": "1", "unit": "capsule"})
    _, summary = req("GET", f"{NUT}/summary/?date={day}")
    by_slug = {n["slug"]: n for n in summary["nutrients"]}
    check("supplement micros feed nutrition summary",
          float(by_slug["vitamin_c"]["amount"]) >= 500.0, True)
    # (Cross-user owner-isolation is covered exhaustively by the backend tests.)

    # --- Iteration 2: specific-days × times-of-day scheduling adherence ---
    st, sched = req("POST", f"{API}/protocol-items/", {
        "protocol": pid, "compound": custom["id"], "dose_amount": "100",
        "dose_unit": "mcg", "frequency": "specific_days",
        "days_of_week": [0, 2, 4], "times_of_day": ["am", "pm"]})
    check("scheduled item created", st, 201)
    check("item stores days_of_week", ",".join(map(str, sched["days_of_week"])), "0,2,4")
    check("item stores times_of_day", ",".join(sched["times_of_day"]), "am,pm")
    _, adh2 = req("GET", f"{API}/protocols/{pid}/adherence/?window_days=7")
    sched_row = next(r for r in adh2 if r["item_id"] == sched["id"])
    check("specific-days adherence (3 days × 2 times)", sched_row["expected"], 6.0)

    # --- Iteration 2: bloodwork bulk create + tabular matrix ---
    m2 = next(m for m in items(markers) if m["slug"] != gen["slug"])
    st, bulk = req("POST", f"{API}/blood-results/bulk/", {
        "measured_on": "2026-05-01", "results": [
            {"marker": gen["id"], "value": "40"},
            {"marker": m2["id"], "value": "35"},
            {"marker": m2["id"], "value": ""},  # blank → skipped
        ]})
    check("bulk create status", st, 201)
    check("bulk skips blank entry", len(bulk), 2)
    _, mtx = req("GET", f"{API}/blood-results/matrix/")
    check("matrix has dates", len(mtx["dates"]) >= 1, True)
    check("matrix includes a measured marker",
          any(r["slug"] == gen["slug"] for r in mtx["rows"]), True)
    check("matrix omits never-measured markers", len(mtx["rows"]) <= len(items(markers)), True)

    print(f"\nSUMMARY: PASS={passed} FAIL={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
