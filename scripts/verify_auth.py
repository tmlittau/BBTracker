#!/usr/bin/env python3
"""End-to-end auth verification for BBTracker against the live stack.

Exercises the full django-allauth (headless) flow over HTTP with a real cookie
jar and CSRF handling — signup, reauthenticate, TOTP enroll + activate, logout,
2FA-gated login, second factor, and the authenticated `me` endpoint.

Pure stdlib (urllib) so it has no dependencies. Run while `docker compose up` is
healthy:  /opt/anaconda3/bin/python scripts/verify_auth.py
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import http.cookiejar
import json
import struct
import sys
import time
import urllib.error
import urllib.request

BASE = "http://localhost:8000"
ALLAUTH = f"{BASE}/_allauth/browser/v1"
PASSWORD = "Sup3rStrongPass!"

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

passed = 0
failed = 0


def check(label: str, got, want) -> None:
    global passed, failed
    # `want` may be a set/tuple of acceptable values.
    ok = got in want if isinstance(want, (set, tuple, list)) else got == want
    passed += ok
    failed += not ok
    print(f"  {'PASS' if ok else 'FAIL'}  {label} (got {got!r}, want {want!r})")


def cookie(name: str) -> str | None:
    return next((c.value for c in jar if c.name == name), None)


def req(method: str, url: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        r.add_header("Content-Type", "application/json")
    csrf = cookie("csrftoken")
    if csrf:
        r.add_header("X-CSRFToken", csrf)
    try:
        resp = opener.open(r)
        status = resp.status
        payload = resp.read()
    except urllib.error.HTTPError as e:
        status = e.code
        payload = e.read()
    try:
        return status, json.loads(payload or b"{}")
    except json.JSONDecodeError:
        return status, {}


def totp(secret: str, *, fresh: bool = False) -> str:
    key = base64.b32decode(secret + "=" * ((8 - len(secret) % 8) % 8))

    def code_at(ts: float) -> str:
        h = hmac.new(key, struct.pack(">Q", int(ts) // 30), hashlib.sha1).digest()
        o = h[19] & 0x0F
        return "%06d" % ((struct.unpack(">I", h[o : o + 4])[0] & 0x7FFFFFFF) % 1_000_000)

    if fresh:
        last = code_at(time.time())
        while code_at(time.time()) == last:  # wait for a new, unused window
            time.sleep(1)
    return code_at(time.time())


def main() -> int:
    email = f"verify+{int(time.time())}@example.com"

    status, _ = req("GET", f"{BASE}/api/v1/healthz/")
    check("backend healthy", status, 200)

    req("GET", f"{BASE}/api/v1/auth/csrf/")  # seed csrftoken cookie

    status, _ = req("POST", f"{ALLAUTH}/auth/signup", {"email": email, "password": PASSWORD})
    check("signup", status, 200)

    status, _ = req("GET", f"{BASE}/api/v1/auth/me/")
    check("me after signup", status, 200)

    # allauth gates MFA enrollment behind a fresh password confirmation.
    status, _ = req("POST", f"{ALLAUTH}/auth/reauthenticate", {"password": PASSWORD})
    check("reauthenticate", status, 200)

    _, body = req("GET", f"{ALLAUTH}/account/authenticators/totp")
    meta = body.get("meta") or body.get("data", {}).get("meta", {})
    secret = meta.get("secret", "")
    check("enrollment secret present", bool(secret), True)

    status, _ = req(
        "POST", f"{ALLAUTH}/account/authenticators/totp", {"code": totp(secret)}
    )
    check("TOTP activation", status, 200)

    req("DELETE", f"{ALLAUTH}/auth/session")  # logout
    req("GET", f"{BASE}/api/v1/auth/csrf/")  # refresh csrftoken for clean session

    status, body = req("POST", f"{ALLAUTH}/auth/login", {"email": email, "password": PASSWORD})
    pending = [f["id"] for f in body.get("data", {}).get("flows", []) if f.get("is_pending")]
    check("password login gated", status, 401)
    check("pending flow is mfa_authenticate", "mfa_authenticate" in pending, True)

    status, _ = req("GET", f"{BASE}/api/v1/auth/me/")
    # DRF IsAuthenticated returns 403 for a half-authenticated (mid-2FA) session;
    # allauth's own endpoints use 401. Either means "blocked".
    check("me blocked before 2nd factor", status, {401, 403})

    status, _ = req(
        "POST", f"{ALLAUTH}/auth/2fa/authenticate", {"code": totp(secret, fresh=True)}
    )
    check("2fa authenticate", status, 200)

    status, body = req("GET", f"{BASE}/api/v1/auth/me/")
    check("me ok after 2FA", status, 200)
    check("me returns correct user", body.get("email"), email)

    print(f"\nSUMMARY: PASS={passed} FAIL={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
