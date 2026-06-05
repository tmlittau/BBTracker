#!/usr/bin/env python3
"""End-to-end verification of the self-coaching layer against the live stack.

The payoff of the whole app: a Phase ties a nutrition target + program + protocol
to a date range, and the dashboard "Today" + weekly check-in aggregate every
domain by date. Drives the HTTP API browser-style (cookie jar + CSRF) through the
frontend proxy on :5173.

Run with the stack up + reference data seeded:
    /opt/anaconda3/bin/python scripts/verify_selfcoaching.py
"""
from __future__ import annotations

import http.cookiejar
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone

BASE = "http://localhost:5173"
ALLAUTH = f"{BASE}/_allauth/browser/v1"
V1 = f"{BASE}/api/v1"
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
    today = date.today().isoformat()
    now = datetime.now(timezone.utc).isoformat()
    req("GET", f"{V1}/auth/csrf/")
    email = f"coach+{int(time.time())}@example.com"
    check("signup", req("POST", f"{ALLAUTH}/auth/signup", {"email": email, "password": PASSWORD})[0], 200)

    # Build the things a phase links together.
    _, target = req("POST", f"{V1}/nutrition/targets/",
                    {"name": "Prep target", "calories": 2200, "protein_g": 200})
    _, program = req("POST", f"{V1}/training/programs/", {"name": "PPL"})
    _, protocol = req("POST", f"{V1}/protocols/protocols/", {"name": "TRT"})

    # Create a phase covering today, then a dated adjustment carrying the prescription.
    st, phase = req("POST", f"{V1}/phases/", {
        "name": "Spring prep", "phase_type": "prep", "start_date": "2026-01-01",
    })
    check("create phase", st, 201)
    check("phase is ongoing", phase["is_ongoing"], True)
    st, adj = req("POST", f"{V1}/phase-adjustments/", {
        "phase": phase["id"], "effective_date": "2026-01-01", "reason": "Start",
        "nutrition_target": target["id"], "program": program["id"], "protocol": protocol["id"],
    })
    check("create adjustment", st, 201)
    check("adjustment links target", adj["nutrition_target_name"], "Prep target")
    check("adjustment links program", adj["program_name"], "PPL")
    check("adjustment links protocol", adj["protocol_name"], "TRT")

    # Cross-app ownership guard: cannot link a second user's program via an adjustment.
    j2 = http.cookiejar.CookieJar()
    op2 = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(j2))
    r = urllib.request.Request(f"{V1}/auth/csrf/")
    op2.open(r)
    csrf2 = next((c.value for c in j2 if c.name == "csrftoken"), None)

    def req2(method, url, body):
        data = json.dumps(body).encode()
        rr = urllib.request.Request(url, data=data, method=method)
        rr.add_header("Content-Type", "application/json")
        # Read the CSRF token fresh each call (it rotates after signup/login).
        tok = next((c.value for c in j2 if c.name == "csrftoken"), None)
        if tok:
            rr.add_header("X-CSRFToken", tok)
        try:
            resp = op2.open(rr)
            return resp.status, json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, {}

    req2("POST", f"{ALLAUTH}/auth/signup", {"email": f"o+{int(time.time())}@e.com", "password": PASSWORD})
    _, ph2 = req2("POST", f"{V1}/phases/", {
        "name": "Mine", "phase_type": "bulk", "start_date": "2026-01-01",
    })
    st, _ = req2("POST", f"{V1}/phase-adjustments/", {
        "phase": ph2["id"], "effective_date": "2026-01-01", "program": program["id"],  # user A's
    })
    check("cannot link another user's program", st, 403)

    # Activate the nutrition target + log across domains for today.
    req("POST", f"{V1}/nutrition/targets/{target['id']}/activate/")
    _, foods = req("GET", f"{V1}/nutrition/foods/")
    chicken = next(f for f in items(foods) if "Chicken" in f["name"])
    _, lunch_meal = req("POST", f"{V1}/nutrition/meals/", {"date": today, "name": "Lunch"})
    req("POST", f"{V1}/nutrition/diary-entries/",
        {"date": today, "meal": lunch_meal["id"], "food": chicken["id"], "quantity": "200"})

    _, exs = req("GET", f"{V1}/training/exercises/")
    bench = next(e for e in items(exs) if "Bench" in e["name"])
    _, session = req("POST", f"{V1}/training/workout-sessions/", {"name": "Push", "started_at": now})
    _, le = req("POST", f"{V1}/training/logged-exercises/",
                {"session": session["id"], "exercise": bench["id"], "order": 0})
    req("POST", f"{V1}/training/logged-sets/",
        {"logged_exercise": le["id"], "order": 0, "set_type": "working", "reps": 5, "weight": "100"})

    _, comps = req("GET", f"{V1}/protocols/compounds/")
    test_e = next(c for c in items(comps) if "Enanthate" in c["name"])
    req("POST", f"{V1}/protocols/dose-logs/",
        {"compound": test_e["id"], "taken_at": now, "amount": "125", "unit": "mg"})

    req("POST", f"{V1}/diary/check-ins/",
        {"date": today, "bodyweight": "90.0", "energy": 4, "sleep": 4, "mood": 5,
         "motivation": 5, "soreness": 2})

    # Dashboard "Today" should reflect all of it + the current phase.
    _, dash = req("GET", f"{V1}/dashboard/today/")
    check("dashboard resolves current phase", dash["phase"]["name"], "Spring prep")
    check("dashboard shows prescribed target (via adjustment)",
          dash["phase"]["nutrition_target_name"], "Prep target")
    check("dashboard nutrition has target", dash["nutrition"]["has_target"], True)
    check("dashboard calories (200g chicken)", dash["nutrition"]["calories"], "330.000")
    check("dashboard workout present", dash["workout"]["count"], 1)
    check("dashboard workout PR counted", dash["workout"]["prs"], 1)
    check("dashboard dose present", len(dash["doses"]), 1)

    # Weekly check-in aggregates the trailing week.
    _, wk = req("GET", f"{V1}/checkin/weekly/")
    check("weekly resolves phase", wk["phase"]["name"], "Spring prep")
    check("weekly counts the session", wk["training"]["sessions"], 1)
    check("weekly counts the PR", wk["training"]["prs"], 1)
    check("weekly bodyweight present", wk["bodyweight"]["last"], 90.0)
    check("weekly subjective energy", wk["subjective"]["energy"], 4.0)
    check("weekly nutrition avg present", wk["nutrition"]["avg_calories"], 330.0)
    check("weekly counts the dose", wk["doses"], 1)
    check("weekly counts the check-in", wk["check_ins"], 1)

    # Phase owner-isolation on list.
    _, mine = req("GET", f"{V1}/phases/")
    check("only my phases listed", len(items(mine)), 1)

    print(f"\nSUMMARY: PASS={passed} FAIL={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
