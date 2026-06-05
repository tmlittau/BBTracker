#!/usr/bin/env python3
"""End-to-end verification of the Training module against the live stack.

Drives the exact HTTP API the SvelteKit UI calls (through the dev proxy or the
dockerized frontend on :5173, browser-style with a cookie jar + CSRF): build a
program, log a workout, and assert e1RM / PR detection / history / volume.

Run with the stack up:
    /opt/anaconda3/bin/python scripts/verify_training.py
"""
from __future__ import annotations

import http.cookiejar
import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://localhost:5173"  # through the frontend proxy → django
ALLAUTH = f"{BASE}/_allauth/browser/v1"
API = f"{BASE}/api/v1/training"
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


def items(payload):
    return payload["results"] if isinstance(payload, dict) and "results" in payload else payload


def main():
    email = f"train+{int(time.time())}@example.com"
    req("GET", f"{BASE}/api/v1/auth/csrf/")
    status, _ = req("POST", f"{ALLAUTH}/auth/signup", {"email": email, "password": PASSWORD})
    check("signup", status, 200)

    # Reference data seeded?
    _, muscles = req("GET", f"{API}/muscles/")
    check("muscles listed", len(items(muscles)) > 0, True)
    _, ex_page = req("GET", f"{API}/exercises/")
    exercises = items(ex_page)
    check("exercises seeded", len(exercises) >= 20, True)

    bench = next((e for e in exercises if "Bench Press" in e["name"]), exercises[0])

    # Build a program → day → slot → planned set.
    _, program = req("POST", f"{API}/programs/", {"name": "PPL"})
    check("create program", program.get("name"), "PPL")
    _, day = req("POST", f"{API}/training-days/",
                 {"program": program["id"], "name": "Push", "order": 0})
    _, slot = req("POST", f"{API}/exercise-slots/",
                  {"day": day["id"], "exercise": bench["id"], "order": 0})
    status, _ = req("POST", f"{API}/planned-sets/",
                    {"slot": slot["id"], "order": 0, "set_type": "working",
                     "target_reps_low": 5, "target_reps_high": 8})
    check("build program hierarchy", status, 201)

    _, full = req("GET", f"{API}/programs/{program['id']}/")
    nested_ok = full["days"][0]["slots"][0]["planned_sets"][0]["target_reps_low"] == 5
    check("nested program read", nested_ok, True)

    _, activated = req("POST", f"{API}/programs/{program['id']}/activate/")
    check("activate program", activated["is_active"], True)

    # Log a workout.
    _, session = req("POST", f"{API}/workout-sessions/",
                     {"name": "Push", "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")})
    _, le = req("POST", f"{API}/logged-exercises/",
                {"session": session["id"], "exercise": bench["id"], "order": 0})

    _, s1 = req("POST", f"{API}/logged-sets/",
                {"logged_exercise": le["id"], "order": 0, "set_type": "working",
                 "reps": 5, "weight": "100.00"})
    check("first set is a PR", s1.get("is_pr"), True)
    check("first set has e1rm", s1.get("e1rm") is not None, True)

    _, s2 = req("POST", f"{API}/logged-sets/",
                {"logged_exercise": le["id"], "order": 1, "set_type": "working",
                 "reps": 5, "weight": "110.00"})
    check("heavier set is a new PR", s2.get("is_pr"), True)
    check("e1rm increased", float(s2["e1rm"]) > float(s1["e1rm"]), True)

    _, s3 = req("POST", f"{API}/logged-sets/",
                {"logged_exercise": le["id"], "order": 2, "set_type": "working",
                 "reps": 3, "weight": "80.00"})
    check("lighter set is not a PR", s3.get("is_pr"), False)

    _, warm = req("POST", f"{API}/logged-sets/",
                  {"logged_exercise": le["id"], "order": 3, "set_type": "warmup",
                   "reps": 10, "weight": "40.00"})
    check("warmup never a PR", warm.get("is_pr"), False)

    _, finished = req("POST", f"{API}/workout-sessions/{session['id']}/finish/")
    check("finish workout", finished["is_completed"], True)

    # History + volume.
    _, hist = req("GET", f"{API}/exercises/{bench['id']}/history/")
    check("exercise history has a point", len(hist) >= 1, True)
    check("history top weight", hist[-1]["top_weight"], "110.00")

    _, vol = req("GET", f"{API}/volume/?days=30")
    chest = next((v for v in vol if v["muscle"] == "Chest"), None)
    # 3 working sets (warm-up excluded): 100*5 + 110*5 + 80*3 = 1290
    check("chest working sets counted (warmup excluded)", chest and chest["sets"], 3)
    check("chest tonnage", chest and chest["tonnage"], "1290.00")

    _, sessions = req("GET", f"{API}/workout-sessions/")
    check("session appears in history list", len(items(sessions)) >= 1, True)

    # --- Iteration 2: start-from-day, per-set rest countdown, prune, reorder ---
    # Add a warmup to the planned slot and set explicit rest on the working set.
    req("POST", f"{API}/planned-sets/", {"slot": slot["id"], "order": 1, "set_type": "warmup"})
    _, full2 = req("GET", f"{API}/programs/{program['id']}/")
    psets = full2["days"][0]["slots"][0]["planned_sets"]
    working_ps = next(p for p in psets if p["set_type"] == "working")
    req("PATCH", f"{API}/planned-sets/{working_ps['id']}/", {"rest_seconds": 200})

    st, started = req("POST", f"{API}/workout-sessions/start_from_day/", {"day": day["id"]})
    check("start_from_day status", st, 201)
    pre_sets = started["logged_exercises"][0]["sets"]
    check("pre-loaded pending sets", len(pre_sets), 2)
    check("all start pending", all(s["is_completed"] is False for s in pre_sets), True)
    w_set = next(s for s in pre_sets if s["set_type"] == "working")
    warm_set = next(s for s in pre_sets if s["set_type"] == "warmup")
    check("working rest carried from plan", w_set["rest_seconds"], 200)
    check("warmup rest defaulted by type", warm_set["rest_seconds"], 45)

    _, done = req("PATCH", f"{API}/logged-sets/{w_set['id']}/",
                  {"reps": 5, "weight": "100.00", "is_completed": True})
    check("pending set completes", done["is_completed"], True)
    check("completed set gets e1rm", done["e1rm"] is not None, True)

    _, fin = req("POST", f"{API}/workout-sessions/{started['id']}/finish/",
                 {"drop_incomplete": True})
    check("finish prunes incomplete", fin["is_completed"], True)
    remaining = [s for le in fin["logged_exercises"] for s in le["sets"]]
    check("only completed sets remain", len(remaining), 1)

    squat = next((e for e in exercises if "Squat" in e["name"]), exercises[1])
    _, slot2 = req("POST", f"{API}/exercise-slots/",
                   {"day": day["id"], "exercise": squat["id"], "order": 1})
    st, _ = req("POST", f"{API}/exercise-slots/reorder/",
                [{"id": slot2["id"], "order": 0}, {"id": slot["id"], "order": 1}])
    check("reorder slots status", st, 200)
    _, full3 = req("GET", f"{API}/programs/{program['id']}/")
    check("reorder puts squat first", full3["days"][0]["slots"][0]["exercise"], squat["id"])

    print(f"\nSUMMARY: PASS={passed} FAIL={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
