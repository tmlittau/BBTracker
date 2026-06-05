#!/usr/bin/env python3
"""End-to-end verification of the Nutrition module against the live stack.

Drives the HTTP API the SvelteKit UI calls (through the frontend proxy on :5173,
browser-style with a cookie jar + CSRF): set a target, log foods across meals,
and assert daily totals, percent-of-target, and the micronutrient breakdown.

Run with the stack up:
    /opt/anaconda3/bin/python scripts/verify_nutrition.py
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
API = f"{BASE}/api/v1/nutrition"
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
    email = f"nut+{int(time.time())}@example.com"
    day = "2026-05-30"
    req("GET", f"{BASE}/api/v1/auth/csrf/")
    status, _ = req("POST", f"{ALLAUTH}/auth/signup", {"email": email, "password": PASSWORD})
    check("signup", status, 200)

    # Reference data seeded?
    _, nutrients = req("GET", f"{API}/nutrients/")
    check("nutrients seeded", len(items(nutrients)) >= 20, True)
    _, food_page = req("GET", f"{API}/foods/")
    foods = items(food_page)
    check("foods seeded", len(foods) >= 10, True)

    chicken = next(f for f in foods if "Chicken" in f["name"])
    rice = next(f for f in foods if "rice" in f["name"].lower())

    # Custom food with nested servings + nutrients.
    protein_id = next(n["id"] for n in items(nutrients) if n["slug"] == "protein")
    energy_id = next(n["id"] for n in items(nutrients) if n["slug"] == "energy")
    status, shake = req("POST", f"{API}/foods/", {
        "name": "Test Shake",
        "servings": [{"label": "1 scoop (30 g)", "grams": "30.00", "is_default": True}],
        "food_nutrients": [
            {"nutrient": protein_id, "amount_per_100g": "80.0000"},
            {"nutrient": energy_id, "amount_per_100g": "400.0000"},
        ],
    })
    check("create custom food", status, 201)
    check("custom food is owned (not global)", shake.get("is_global"), False)

    # Set + activate a target.
    _, target = req("POST", f"{API}/targets/", {
        "name": "Cut", "calories": 2000, "protein_g": 180, "carb_g": 180, "fat_g": 55
    })
    check("create target", target.get("name"), "Cut")
    _, activated = req("POST", f"{API}/targets/{target['id']}/activate/")
    check("activate target", activated["is_active"], True)

    # Iteration 2: meals are dynamic per-day objects, not a fixed enum.
    _, lunch = req("POST", f"{API}/meals/", {"date": day, "name": "Lunch", "order": 0})
    check("create meal", lunch.get("name"), "Lunch")
    _, postw = req("POST", f"{API}/meals/", {"date": day, "name": "Post-workout", "order": 1})
    _, meals_today = req("GET", f"{API}/meals/?date={day}")
    check("meals listed for day", len(items(meals_today)), 2)
    st, _ = req("POST", f"{API}/meals/reorder/",
                [{"id": postw["id"], "order": 0}, {"id": lunch["id"], "order": 1}])
    check("meal reorder", st, 200)

    # Log foods into the meals.
    # 200 g chicken (165 kcal, 31 P /100g) → 330 kcal, 62 P
    _, e1 = req("POST", f"{API}/diary-entries/", {
        "date": day, "meal": lunch["id"], "food": chicken["id"], "quantity": "200"
    })
    check("log chicken resolves grams", e1.get("grams"), "200.00")
    check("entry attaches to meal", e1.get("meal"), lunch["id"])
    # 150 g rice (130 kcal, 2.7 P /100g) → 195 kcal, 4.05 P
    req("POST", f"{API}/diary-entries/", {
        "date": day, "meal": lunch["id"], "food": rice["id"], "quantity": "150"
    })
    # 2 scoops shake = 60 g (400 kcal, 80 P /100g) → 240 kcal, 48 P
    shake_serving = shake["servings"][0]["id"]
    _, e3 = req("POST", f"{API}/diary-entries/", {
        "date": day, "meal": postw["id"], "food": shake["id"],
        "serving": shake_serving, "quantity": "2"
    })
    check("log shake by serving resolves grams", e3.get("grams"), "60.00")

    # Diary list for the day.
    _, diary = req("GET", f"{API}/diary-entries/?date={day}")
    check("diary has 3 entries", len(items(diary)), 3)

    # Summary: totals + percent-of-target.
    _, summary = req("GET", f"{API}/summary/?date={day}")
    check("summary has target", summary["has_target"], True)
    # calories: 330 + 195 + 240 = 765
    check("total calories", summary["totals"]["calories"], "765.000")
    # protein: 62 + 4.05 + 48 = 114.05
    check("total protein", summary["totals"]["protein_g"], "114.050")

    by_slug = {n["slug"]: n for n in summary["nutrients"]}
    # 765 / 2000 = 38%
    check("calorie percent of target", by_slug["energy"]["percent"], 38)
    # 114.05 / 180 = 63%
    check("protein percent of target", by_slug["protein"]["percent"], 63)
    # Micros present with categories (from chicken/rice profiles).
    has_micros = any(n["category"] in ("vitamin", "mineral") for n in summary["nutrients"])
    check("micronutrients present in summary", has_micros, True)

    # Delete an entry → totals drop.
    req("DELETE", f"{API}/diary-entries/{e1['id']}/")
    _, summary2 = req("GET", f"{API}/summary/?date={day}")
    check("calories drop after delete", summary2["totals"]["calories"], "435.000")

    # Empty day has no target effect / zero totals.
    _, empty = req("GET", f"{API}/summary/?date=2020-01-01")
    check("empty day zero calories", empty["totals"]["calories"], "0.000")

    # --- Iteration 2: ml unit for liquids ------------------------------------
    _, drink = req("POST", f"{API}/foods/", {
        "name": "Test Cola", "unit": "ml",
        "servings": [{"label": "100 ml", "grams": "100", "is_default": True}],
        "food_nutrients": [{"nutrient": energy_id, "amount_per_100g": "42"}],
    })
    check("create ml food", drink.get("unit"), "ml")
    _, e_ml = req("POST", f"{API}/diary-entries/", {
        "date": day, "meal": lunch["id"], "food": drink["id"], "quantity": "330"})
    check("ml entry carries unit", e_ml.get("unit"), "ml")
    check("ml entry grams resolved (330 ml)", e_ml.get("grams"), "330.00")

    # --- Barcode import -------------------------------------------------------
    # Deterministic (no network): an existing food carrying a barcode is returned
    # as-is by import_barcode, short-circuiting the Open Food Facts lookup.
    status, owned = req("POST", f"{API}/foods/", {
        "name": "Barcoded snack", "barcode": "0001112223334",
        "servings": [{"label": "100 g", "grams": "100.00", "is_default": True}],
        "food_nutrients": [{"nutrient": energy_id, "amount_per_100g": "200.0000"}],
    })
    check("create food with barcode", status, 201)
    status, found = req("POST", f"{API}/foods/import_barcode/", {"barcode": "0001112223334"})
    check("import_barcode returns existing food", status, 200)
    check("existing food id matches", found.get("id"), owned.get("id"))
    # Malformed barcode is rejected by the serializer.
    status, _ = req("POST", f"{API}/foods/import_barcode/", {"barcode": "not-a-barcode"})
    check("invalid barcode rejected", status, 400)

    # Best-effort live import from Open Food Facts (Nutella). Skipped — not
    # failed — when OFF is unreachable/rate-limited so the suite stays offline-safe.
    status, imported = req("POST", f"{API}/foods/import_barcode/", {"barcode": "3017620422003"})
    if status in (200, 201):
        check("live OFF import source=off", imported.get("source"), "off")
        check("live OFF import is global", imported.get("is_global"), True)
        has_energy = any(n.get("slug") == "energy" for n in imported.get("food_nutrients", []))
        check("live OFF import has nutrients", has_energy, True)
    else:
        print(f"  SKIP  live OFF import (HTTP {status}; OFF unreachable or rate-limited)")

    print(f"\nSUMMARY: PASS={passed} FAIL={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
