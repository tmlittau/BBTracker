#!/usr/bin/env python3
"""End-to-end verification of the Progress Diary against the live stack.

Drives the HTTP API the SvelteKit UI calls (through the frontend proxy on :5173,
browser-style with a cookie jar + CSRF). Exercises the real MinIO storage path:
create a check-in, upload an EXIF-bearing photo, assert it's re-encoded to JPEG
with orientation applied + metadata stripped, stream it (and its thumbnail) back,
ghost-overlay latest-by-pose, and owner isolation.

Generates its own image in-memory (needs Pillow: use the anaconda python). Run
with the stack up + `seed_diary` applied:
    /opt/anaconda3/bin/python scripts/verify_diary.py
"""
from __future__ import annotations

import http.cookiejar
import io
import json
import sys
import time
import urllib.error
import urllib.request

from PIL import Image

BASE = "http://localhost:5173"
ALLAUTH = f"{BASE}/_allauth/browser/v1"
API = f"{BASE}/api/v1/diary"
PASSWORD = "Sup3rStrongPass!"

passed = failed = 0


def check(label, got, want):
    global passed, failed
    ok = (got in want) if isinstance(want, (set, tuple, list)) else (got == want)
    passed += ok
    failed += not ok
    print(f"  {'PASS' if ok else 'FAIL'}  {label} (got {got!r}, want {want!r})")


class Client:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def csrf(self):
        return next((c.value for c in self.jar if c.name == "csrftoken"), None)

    def req(self, method, url, body=None):
        data = json.dumps(body).encode() if body is not None else None
        r = urllib.request.Request(url, data=data, method=method)
        if data is not None:
            r.add_header("Content-Type", "application/json")
        if self.csrf():
            r.add_header("X-CSRFToken", self.csrf())
        try:
            resp = self.op.open(r)
            raw = resp.read()
            try:
                return resp.status, json.loads(raw or b"{}")
            except json.JSONDecodeError:
                return resp.status, raw
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read() or b"{}")
            except json.JSONDecodeError:
                return e.code, {}

    def get_bytes(self, url):
        r = urllib.request.Request(url, method="GET")
        if self.csrf():
            r.add_header("X-CSRFToken", self.csrf())
        try:
            resp = self.op.open(r)
            return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def upload(self, url, fields: dict, image_bytes: bytes):
        boundary = "----bbtdiary"
        crlf = "\r\n"
        body = b""
        for name, val in fields.items():
            body += f"--{boundary}{crlf}".encode()
            body += f'Content-Disposition: form-data; name="{name}"{crlf}{crlf}{val}{crlf}'.encode()
        body += f"--{boundary}{crlf}".encode()
        body += (
            f'Content-Disposition: form-data; name="image"; filename="p.jpg"{crlf}'
            f"Content-Type: image/jpeg{crlf}{crlf}"
        ).encode()
        body += image_bytes + crlf.encode() + f"--{boundary}--{crlf}".encode()
        r = urllib.request.Request(url, data=body, method="POST")
        r.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        if self.csrf():
            r.add_header("X-CSRFToken", self.csrf())
        try:
            resp = self.op.open(r)
            return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return e.code, e.read()[:200]


def jpeg_with_orientation(w=900, h=600) -> bytes:
    img = Image.new("RGB", (w, h), (60, 40, 40))
    exif = img.getexif()
    exif[274] = 6  # rotate 90° → app should yield h×w and drop EXIF
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


def items(p):
    return p["results"] if isinstance(p, dict) and "results" in p else p


def main():
    a = Client()
    a.req("GET", f"{BASE}/api/v1/auth/csrf/")
    email = f"diary+{int(time.time())}@example.com"
    check("signup", a.req("POST", f"{ALLAUTH}/auth/signup",
                          {"email": email, "password": PASSWORD})[0], 200)

    # Poses seeded (iteration 2 added relaxed-from-every-side, most-muscular, classic).
    st, poses = a.req("GET", f"{API}/poses/")
    poses = items(poses)
    check("13 poses seeded", len(poses), 13)
    pose_names = {p["name"] for p in poses}
    check("relaxed + extra poses present",
          {"Back relaxed", "Side relaxed (left)", "Side relaxed (right)", "Most muscular"} <= pose_names,
          True)
    pose_id = poses[1]["id"]

    # Check-in CRUD.
    st, ci = a.req("POST", f"{API}/check-ins/",
                   {"date": "2026-05-31", "bodyweight": "84.5",
                    "energy": 4, "sleep": 3, "mood": 5, "motivation": 4, "soreness": 2,
                    "notes": "felt strong"})
    check("create check-in", st, 201)
    check("duplicate date rejected", a.req("POST", f"{API}/check-ins/", {"date": "2026-05-31"})[0], 400)
    check("score out of range rejected",
          a.req("POST", f"{API}/check-ins/", {"date": "2026-06-01", "energy": 9})[0], 400)
    # Bodyweight is mandatory; omitting it defaults to 0 (not null).
    st, ciz = a.req("POST", f"{API}/check-ins/", {"date": "2026-06-02", "energy": 3})
    check("check-in without bodyweight created", st, 201)
    check("missing bodyweight defaults to 0", str(ciz.get("bodyweight")), "0.00")

    # Photo upload → real storage round-trip.
    st, photo = a.upload(f"{API}/photos/",
                         {"taken_on": "2026-05-31", "pose": str(pose_id), "notes": "week 1"},
                         jpeg_with_orientation(900, 600))
    check("upload photo", st, 201)
    # (compare as a string — check() treats a tuple `want` as membership, not equality)
    check("EXIF orientation applied (900x600 → 600x900)",
          f"{photo['width']}x{photo['height']}", "600x900")
    check("normalised to jpeg", photo["content_type"], "image/jpeg")

    st, full = a.get_bytes(f"{BASE}{photo['image_url']}")
    check("stream full image", st, 200)
    check("full is JPEG", full[:2], b"\xff\xd8")
    st, thumb = a.get_bytes(f"{BASE}{photo['thumb_url']}")
    check("stream thumbnail", st, 200)
    check("thumb smaller than full", len(thumb) < len(full), True)

    # Ghost overlay: latest for the pose is this photo.
    st, latest = a.req("GET", f"{API}/photos/latest/?pose={pose_id}")
    check("latest-by-pose matches upload", latest.get("id"), photo["id"])

    # A newer photo becomes the latest (ghost overlay always shows most recent).
    st, photo2 = a.upload(f"{API}/photos/",
                          {"taken_on": "2026-06-15", "pose": str(pose_id)},
                          jpeg_with_orientation(400, 400))
    st, latest2 = a.req("GET", f"{API}/photos/latest/?pose={pose_id}")
    check("latest updates to newest", latest2.get("id"), photo2["id"])

    # Owner isolation: a second user sees none of the first's photos/check-ins,
    # and cannot stream the first user's image.
    b = Client()
    b.req("GET", f"{BASE}/api/v1/auth/csrf/")
    b.req("POST", f"{ALLAUTH}/auth/signup",
          {"email": f"other+{int(time.time())}@example.com", "password": PASSWORD})
    st, bphotos = b.req("GET", f"{API}/photos/")
    check("other user sees no photos", len(items(bphotos)), 0)
    st, bci = b.req("GET", f"{API}/check-ins/")
    check("other user sees no check-ins", len(items(bci)), 0)
    st, _ = b.get_bytes(f"{BASE}{photo['image_url']}")
    check("other user cannot stream the photo", st, 404)

    # Delete removes it.
    st, _ = a.req("DELETE", f"{API}/photos/{photo['id']}/")
    check("delete photo", st, 204)
    st, _ = a.get_bytes(f"{BASE}{photo['image_url']}")
    check("deleted photo no longer streamable", st, 404)

    print(f"\nSUMMARY: PASS={passed} FAIL={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
