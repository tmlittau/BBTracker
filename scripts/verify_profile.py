#!/usr/bin/env python3
"""End-to-end verification of profile editing + its effect on bloodwork flagging.

Drives the API browser-style (cookie jar + CSRF) through the frontend proxy on
:5173: a fresh user has sex "unspecified", so a sex-specific marker (Total
Testosterone, male-ranged) can't be flagged; after PATCHing the profile to
sex=male, the same lab values flag low/high.

Run with the stack up and `seed_protocols` applied:
    /opt/anaconda3/bin/python scripts/verify_profile.py
"""
from __future__ import annotations

import http.cookiejar
import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://localhost:5173"
ALLAUTH = f"{BASE}/_allauth/browser/v1"
AUTH = f"{BASE}/api/v1/auth"
PROTO = f"{BASE}/api/v1/protocols"
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
    email = f"profile+{int(time.time())}@example.com"
    req("GET", f"{AUTH}/csrf/")
    check("signup", req("POST", f"{ALLAUTH}/auth/signup",
                        {"email": email, "password": PASSWORD})[0], 200)

    # Fresh profile defaults to unspecified sex.
    _, me = req("GET", f"{AUTH}/me/")
    check("new profile sex is unspecified", me["profile"]["sex"], "unspecified")
    check("email present", me["email"], email)

    # Seeded male-ranged marker.
    _, markers = req("GET", f"{PROTO}/blood-markers/")
    tt = next(m for m in items(markers) if m["slug"] == "testosterone")
    check("Testosterone has male range only", tt["ref_low_male"] is not None and tt["ref_low"] is None, True)

    # Log a low and a high value.
    req("POST", f"{PROTO}/blood-results/",
        {"marker": tt["id"], "value": "250", "measured_on": "2026-01-01"})   # < 300
    req("POST", f"{PROTO}/blood-results/",
        {"marker": tt["id"], "value": "1200", "measured_on": "2026-03-01"})  # > 1000

    # Before setting sex: no applicable range → both in_range.
    _, trend = req("GET", f"{PROTO}/blood-results/trend/?marker={tt['id']}")
    flags_before = [p["flag"] for p in trend]
    # (join to a string — check() treats a list `want` as membership, not equality)
    check("unspecified sex → no flagging", ",".join(flags_before), "in_range,in_range")

    # Edit the profile via PATCH /me/.
    st, updated = req("PATCH", f"{AUTH}/me/",
                      {"profile": {"sex": "male", "height_cm": "182.5"}})
    check("PATCH me ok", st, 200)
    check("profile sex updated", updated["profile"]["sex"], "male")
    # height_cm is DecimalField(decimal_places=1) → serialises as "182.5".
    check("profile height updated", updated["profile"]["height_cm"], "182.5")
    check("email still read-only", updated["email"], email)

    # PATCH persists.
    _, me2 = req("GET", f"{AUTH}/me/")
    check("profile change persisted", me2["profile"]["sex"], "male")

    # After setting sex=male: 250 flags low, 1200 flags high.
    _, trend2 = req("GET", f"{PROTO}/blood-results/trend/?marker={tt['id']}")
    flags_after = [p["flag"] for p in trend2]
    check("male sex → 250 flags low", flags_after[0], "low")
    check("male sex → 1200 flags high", flags_after[1], "high")
    check("male sex → flags now differ from in_range", ",".join(flags_after), "low,high")

    # Email cannot be changed through the profile endpoint.
    st, body = req("PATCH", f"{AUTH}/me/", {"email": "hacked@example.com"})
    check("email change is ignored", body.get("email"), email)

    print(f"\nSUMMARY: PASS={passed} FAIL={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
