"""Nutrition analytics: scale foods to portions and roll a day up vs target.

Pure helpers (Decimal in/out) are unit-tested without the ORM; DB-aware wrappers
sit at the bottom.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.core.cache import cache

HUNDRED = Decimal("100")


def _q(value, places="0.01") -> Decimal:
    return Decimal(str(value)).quantize(Decimal(places), rounding=ROUND_HALF_UP)


def scale_amount(amount_per_100g, grams) -> Decimal:
    """Nutrient amount for `grams` of a food given its per-100 g amount."""
    if amount_per_100g is None or grams is None:
        return Decimal("0")
    return _q(Decimal(str(amount_per_100g)) * Decimal(str(grams)) / HUNDRED, "0.001")


def resolve_grams(quantity, serving_grams) -> Decimal | None:
    """Canonical grams for a food entry: quantity × serving size (in grams).

    If no serving is given, `quantity` is treated as grams directly.
    """
    if quantity is None:
        return None
    q = Decimal(str(quantity))
    if serving_grams is None:
        return _q(q)
    return _q(q * Decimal(str(serving_grams)))


def percent_of_target(amount, target) -> int | None:
    """Whole-percent of target met, floored (None if no/zero target).

    Floor (not round) so a goal-completion bar only reads 100% when the target is
    truly met — 99.5% should not display as 100%.
    """
    if not target:
        return None
    return int(Decimal(str(amount)) / Decimal(str(target)) * HUNDRED)


# --- DB-aware wrappers ---------------------------------------------------------


def resolve_entry_grams(entry) -> Decimal | None:
    """Compute `grams` for a DiaryEntry food log (None for recipe entries)."""
    if entry.food_id is None:
        return None
    serving_grams = entry.serving.grams if entry.serving_id else None
    return resolve_grams(entry.quantity, serving_grams)


def food_nutrient_amounts(food, grams) -> dict[int, Decimal]:
    """{nutrient_id: amount} for `grams` of a food."""
    out: dict[int, Decimal] = {}
    for fn in food.food_nutrients.all():
        out[fn.nutrient_id] = scale_amount(fn.amount_per_100g, grams)
    return out


def recipe_nutrients_per_serving(recipe) -> dict[int, Decimal]:
    """{nutrient_id: amount} for ONE serving of a recipe."""
    totals: dict[int, Decimal] = {}
    for item in recipe.items.all():
        for nid, amt in food_nutrient_amounts(item.food, item.grams).items():
            totals[nid] = totals.get(nid, Decimal("0")) + amt
    servings = Decimal(str(recipe.servings or 1)) or Decimal("1")
    return {nid: _q(amt / servings, "0.001") for nid, amt in totals.items()}


def daily_totals(entries) -> dict[int, Decimal]:
    """Aggregate {nutrient_id: amount} across diary entries (foods + recipes)."""
    totals: dict[int, Decimal] = {}

    def add(nid, amt):
        totals[nid] = totals.get(nid, Decimal("0")) + amt

    for entry in entries:
        if entry.food_id is not None:
            grams = entry.grams if entry.grams is not None else resolve_entry_grams(entry)
            for nid, amt in food_nutrient_amounts(entry.food, grams).items():
                add(nid, amt)
        elif entry.recipe_id is not None:
            qty = Decimal(str(entry.quantity or 0))
            for nid, amt in recipe_nutrients_per_serving(entry.recipe).items():
                add(nid, _q(amt * qty, "0.001"))
    return totals


# Reference data (Nutrients) rarely changes — it's seeded — so cache it instead of
# re-querying ~60 rows on every summary. `seed_nutrition` clears the key.
NUTRIENTS_CACHE_KEY = "ref:nutrients:v1"
REF_CACHE_TTL = 3600


def cached_nutrients():
    """All Nutrients as lightweight dicts (cached). Order matches Nutrient.objects.all()."""
    data = cache.get(NUTRIENTS_CACHE_KEY)
    if data is None:
        from .models import Nutrient

        data = [
            {
                "id": n.id, "name": n.name, "slug": n.slug, "unit": n.unit,
                "category": n.category, "rda": n.rda, "display_order": n.display_order,
            }
            for n in Nutrient.objects.all()
        ]
        cache.set(NUTRIENTS_CACHE_KEY, data, REF_CACHE_TTL)
    return data


def _macro_ids():
    """{slug: nutrient_id} for the macro slugs, from cached reference data."""
    return {
        n["slug"]: n["id"]
        for n in cached_nutrients()
        if n["slug"] in ("energy", "protein", "carbohydrate", "fat", "fiber")
    }


def daily_summary(owner, date):
    """Full day summary: per-nutrient totals vs the active target.

    Returns a dict with `date`, `totals` (macro headline numbers) and a
    `nutrients` list of {id,name,unit,category,amount,target,percent}.
    """
    from .models import DiaryEntry, NutritionTarget

    entries = (
        DiaryEntry.objects.filter(owner=owner, date=date)
        .select_related("food", "recipe", "serving")
        .prefetch_related("food__food_nutrients", "recipe__items__food__food_nutrients")
    )
    totals = daily_totals(entries)

    # Fold in micronutrients delivered by supplement doses logged today, so the
    # daily totals reflect pills too (Phase 3 integration). Function-local import
    # avoids a module cycle and keeps nutrition usable if protocols is absent.
    try:
        from apps.protocols.services import supplement_nutrient_contribution

        for nid, amt in supplement_nutrient_contribution(owner, date).items():
            totals[nid] = totals.get(nid, Decimal("0")) + amt
    except ImportError:
        pass

    target = (
        NutritionTarget.objects.filter(owner=owner, is_active=True)
        .prefetch_related("nutrient_targets")
        .first()
    )
    # Map nutrient_id -> target amount (macros come from dedicated columns).
    target_by_nutrient: dict[int, Decimal] = {}
    macro_targets = {}
    if target:
        macro_targets = {
            "energy": target.calories,
            "protein": target.protein_g,
            "carbohydrate": target.carb_g,
            "fat": target.fat_g,
            "fiber": target.fiber_g,
        }
        for nt in target.nutrient_targets.all():
            target_by_nutrient[nt.nutrient_id] = (nt.min_amount, nt.max_amount)

    nutrients = []
    for n in cached_nutrients():
        amount = totals.get(n["id"], Decimal("0"))
        # Custom per-micronutrient range (min floor / max ceiling), if set for this target.
        custom = target_by_nutrient.get(n["id"])
        tgt = custom[0] if custom else None
        tgt_max = custom[1] if custom else None
        if tgt is None and target:
            tgt = macro_targets.get(n["slug"])
        if tgt is None:
            tgt = n["rda"]  # fall back to RDA for the floor
        nutrients.append(
            {
                "id": n["id"],
                "name": n["name"],
                "slug": n["slug"],
                "unit": n["unit"],
                "category": n["category"],
                "amount": _q(amount, "0.001"),
                "target": tgt,
                "target_max": tgt_max,
                "percent": percent_of_target(amount, tgt),
            }
        )

    def macro(slug):
        n = next((x for x in nutrients if x["slug"] == slug), None)
        # Emit strings so the headline matches the per-nutrient `amount`
        # (DecimalField → string) instead of DictField's float coercion.
        return str(n["amount"] if n else Decimal("0.000"))

    headline = {
        "calories": macro("energy"),
        "protein_g": macro("protein"),
        "carb_g": macro("carbohydrate"),
        "fat_g": macro("fat"),
        "fiber_g": macro("fiber"),
    }

    # Per-meal macro rollup (for the meal headers in the diary).
    macro_id = {
        x["slug"]: x["id"]
        for x in nutrients
        if x["slug"] in ("energy", "protein", "carbohydrate", "fat")
    }
    by_meal: dict[int, list] = {}
    for entry in entries:
        if entry.meal_id is not None:
            by_meal.setdefault(entry.meal_id, []).append(entry)
    meals = []
    for meal_id, meal_entries in by_meal.items():
        mt = daily_totals(meal_entries)
        meals.append(
            {
                "meal": meal_id,
                "calories": str(_q(mt.get(macro_id.get("energy"), Decimal("0")), "0.001")),
                "protein_g": str(_q(mt.get(macro_id.get("protein"), Decimal("0")), "0.001")),
                "carb_g": str(_q(mt.get(macro_id.get("carbohydrate"), Decimal("0")), "0.001")),
                "fat_g": str(_q(mt.get(macro_id.get("fat"), Decimal("0")), "0.001")),
            }
        )

    return {
        "date": date.isoformat() if hasattr(date, "isoformat") else str(date),
        "has_target": target is not None,
        "target_name": target.name if target else None,
        "totals": headline,
        "nutrients": nutrients,
        "meals": meals,
    }


def macro_totals_by_day(owner, start_date, end_date):
    """{date: {"calories": Decimal, "protein_g": Decimal}} over [start, end] inclusive.

    Batched (one diary-entry query + one supplement query for the whole window),
    energy + protein only — for the dashboard headline and the weekly check-in,
    which don't need the full per-nutrient breakdown. Days with no intake are absent.
    """
    from collections import defaultdict

    from .models import DiaryEntry

    ids = _macro_ids()
    energy_id, protein_id = ids.get("energy"), ids.get("protein")
    by_day: dict = defaultdict(lambda: {"calories": Decimal("0"), "protein_g": Decimal("0")})

    entries = (
        DiaryEntry.objects.filter(owner=owner, date__gte=start_date, date__lte=end_date)
        .select_related("food", "recipe", "serving")
        .prefetch_related("food__food_nutrients", "recipe__items__food__food_nutrients")
    )
    grouped: dict = defaultdict(list)
    for e in entries:
        grouped[e.date].append(e)
    for day, day_entries in grouped.items():
        t = daily_totals(day_entries)
        by_day[day]["calories"] += t.get(energy_id, Decimal("0"))
        by_day[day]["protein_g"] += t.get(protein_id, Decimal("0"))

    # Fold in supplement-provided energy/protein (windowed; mirrors daily_summary).
    try:
        from apps.protocols.services import supplement_nutrient_contribution_range

        for day, contrib in supplement_nutrient_contribution_range(
            owner, start_date, end_date
        ).items():
            by_day[day]["calories"] += contrib.get(energy_id, Decimal("0"))
            by_day[day]["protein_g"] += contrib.get(protein_id, Decimal("0"))
    except ImportError:
        pass

    return dict(by_day)


def nutrition_headline(owner, date):
    """Lightweight macro headline for the dashboard: the day's calories + protein and
    the active target — without daily_summary's full per-nutrient list / per-meal work."""
    from .models import NutritionTarget

    day = macro_totals_by_day(owner, date, date).get(
        date, {"calories": Decimal("0"), "protein_g": Decimal("0")}
    )
    target = NutritionTarget.objects.filter(owner=owner, is_active=True).only("name").first()
    return {
        "has_target": target is not None,
        "calories": str(_q(day["calories"], "0.001")),
        "protein_g": str(_q(day["protein_g"], "0.001")),
        "target_name": target.name if target else None,
    }


def weekly_macro_adherence(owner, start_date, end_date):
    """Avg calories/protein over days with intake in [start, end] + the active target —
    the weekly check-in's nutrition block, batched (no per-day round-trips)."""
    from .models import NutritionTarget

    by_day = macro_totals_by_day(owner, start_date, end_date)
    days = [v for v in by_day.values() if float(v["calories"]) > 0]
    cals = [float(v["calories"]) for v in days]
    prots = [float(v["protein_g"]) for v in days]
    target = NutritionTarget.objects.filter(owner=owner, is_active=True).only("name").first()
    return {
        "days_logged": len(days),
        "avg_calories": round(sum(cals) / len(cals), 0) if cals else None,
        "avg_protein_g": round(sum(prots) / len(prots), 1) if prots else None,
        "target_name": target.name if target else None,
    }


# --- Open Food Facts barcode import -------------------------------------------
#
# OFF exposes a product as `GET /api/v2/product/<barcode>.json`, whose
# `product.nutriments` carries per-100 g amounts under `<id>_100g` keys (e.g.
# `energy-kcal_100g`, `proteins_100g`). We map those onto our canonical Nutrient
# slugs, converting OFF's gram-based mass values into each nutrient's own unit.
# The network call is isolated in `fetch_off_product` so tests can mock it
# without hitting the wire.

OFF_BASE_URL = "https://world.openfoodfacts.org/api/v2/product"
OFF_USER_AGENT = "BBTracker/0.1 (self-hosted; nutrition barcode import)"
OFF_TIMEOUT = 8  # seconds


class BarcodeImportError(Exception):
    """Base class for barcode-import failures."""


class ProductNotFound(BarcodeImportError):
    """The barcode has no product on Open Food Facts (HTTP 404 / status 0)."""


class NoNutrimentsError(BarcodeImportError):
    """A product was found but carries no nutrition data we can import."""


class UpstreamUnavailable(BarcodeImportError):
    """Open Food Facts could not be reached (network/HTTP error)."""


# OFF nutriment base-id -> our canonical Nutrient slug. Some nutrients have
# legacy/alias ids (niacin, folate); aliases are listed after the canonical key
# so the first present, non-empty value wins.
OFF_NUTRIENT_MAP: dict[str, str] = {
    "energy-kcal": "energy",
    "proteins": "protein",
    "carbohydrates": "carbohydrate",
    "sugars": "sugar",
    "fat": "fat",
    "saturated-fat": "saturated_fat",
    "fiber": "fiber",
    # Vitamins
    "vitamin-a": "vitamin_a",
    "vitamin-c": "vitamin_c",
    "vitamin-d": "vitamin_d",
    "vitamin-e": "vitamin_e",
    "vitamin-k": "vitamin_k",
    "vitamin-b1": "thiamin",
    "vitamin-b2": "riboflavin",
    "vitamin-pp": "niacin",
    "niacin": "niacin",
    "vitamin-b6": "vitamin_b6",
    "vitamin-b9": "folate",
    "folates": "folate",
    "vitamin-b12": "vitamin_b12",
    # Minerals
    "calcium": "calcium",
    "iron": "iron",
    "magnesium": "magnesium",
    "phosphorus": "phosphorus",
    "potassium": "potassium",
    "sodium": "sodium",
    "zinc": "zinc",
    "selenium": "selenium",
}

# Slugs kept even when the reported value is 0 — a real "0 g fat" is meaningful.
# Micros are only stored when present and > 0, to avoid a wall of misleading
# "0 µg" rows for nutrients the manufacturer simply didn't declare.
CORE_SLUGS = {"energy", "protein", "carbohydrate", "fat", "saturated_fat", "fiber", "sugar"}

# At least one of these must be present, else there's nothing worth importing.
REQUIRED_ANY = {"energy", "protein", "carbohydrate", "fat"}

# OFF normalises `_100g` mass values to grams; scale into each nutrient's unit.
_UNIT_FACTOR = {
    "g": Decimal("1"),
    "kcal": Decimal("1"),
    "mg": Decimal("1000"),
    "mcg": Decimal("1000000"),
}


def map_off_nutriments(nutriments: dict, units_by_slug: dict[str, str]) -> dict[str, Decimal]:
    """Map an OFF `nutriments` object to {our_slug: amount_per_100g} in our units.

    `units_by_slug` supplies each known nutrient's unit so OFF's gram-based
    `_100g` values can be converted (g → mg → µg). Slugs absent from
    `units_by_slug`, or whose unit isn't convertible (e.g. IU), are skipped.
    Micros that are missing or non-positive are dropped; core macros/energy are
    kept even at 0. Pure: no DB, no network.
    """
    out: dict[str, Decimal] = {}
    for off_key, slug in OFF_NUTRIENT_MAP.items():
        if slug in out or slug not in units_by_slug:
            continue
        raw = nutriments.get(f"{off_key}_100g")
        if raw is None or raw == "":
            continue
        factor = _UNIT_FACTOR.get(units_by_slug[slug])
        if factor is None:
            continue
        try:
            amount = _q(Decimal(str(raw)) * factor, "0.0001")
        except (InvalidOperation, ValueError):
            continue
        if slug not in CORE_SLUGS and amount <= 0:
            continue
        out[slug] = amount
    return out


def fetch_off_product(barcode: str) -> dict | None:
    """Fetch a product from Open Food Facts; return its `product` dict or None.

    None signals a definitive 'not found' (HTTP 404 or `status == 0`). Network
    or non-404 HTTP failures raise `UpstreamUnavailable` so callers can tell a
    missing product apart from an unreachable API.
    """
    url = f"{OFF_BASE_URL}/{barcode}.json"
    request = urllib.request.Request(url, headers={"User-Agent": OFF_USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=OFF_TIMEOUT) as resp:
            payload = json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise UpstreamUnavailable(f"Open Food Facts returned HTTP {exc.code}.") from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise UpstreamUnavailable("Could not reach Open Food Facts.") from exc
    if not payload or payload.get("status") == 0:
        return None
    return payload.get("product") or None


def _off_brand(product: dict) -> str:
    """First brand from OFF's comma-separated `brands` field."""
    first = (product.get("brands") or "").split(",")[0].strip()
    return first[:120]


def _off_name(product: dict, barcode: str) -> str:
    for key in ("product_name", "product_name_en", "generic_name"):
        name = (product.get(key) or "").strip()
        if name:
            return name[:160]
    return f"Food {barcode}"


def find_existing_food_by_barcode(user, barcode: str):
    """Return a global or user-owned Food with this barcode, or None."""
    from django.db.models import Q

    from .models import Food

    return (
        Food.objects.filter(barcode=barcode)
        .filter(Q(owner__isnull=True) | Q(owner_id=user.id))
        .order_by("owner_id")  # NULLs (global) first
        .first()
    )


def _add_off_serving(food, product: dict) -> None:
    """Add OFF's own serving (e.g. '30 g') as a non-default option, when sane."""
    from .models import ServingSize

    try:
        grams = _q(Decimal(str(product.get("serving_quantity"))))
    except (InvalidOperation, ValueError, TypeError):
        return
    if grams <= 0 or grams == Decimal("100.00"):
        return
    label = (product.get("serving_size") or "").strip() or f"{grams} g"
    ServingSize.objects.create(food=food, label=label[:80], grams=grams, is_default=False)


def import_food_from_barcode(user, barcode: str):
    """Resolve a barcode to a Food, importing from Open Food Facts if needed.

    Returns ``(food, created)``. If a Food with this barcode already exists
    (global or owned by ``user``) it is returned with ``created=False`` and no
    network call is made. Otherwise the product is fetched from OFF and a new
    GLOBAL food (``source='off'``) is created with a 100 g default serving and
    the mapped FoodNutrient rows.

    Raises ``ProductNotFound`` / ``NoNutrimentsError`` / ``UpstreamUnavailable``.
    """
    from django.db import transaction

    from .enums import FoodSource
    from .models import Food, FoodNutrient, Nutrient, ServingSize

    existing = find_existing_food_by_barcode(user, barcode)
    if existing is not None:
        return existing, False

    # Network is done outside any DB transaction (don't hold a tx across HTTP).
    product = fetch_off_product(barcode)
    if product is None:
        raise ProductNotFound(f"No product found for barcode {barcode}.")

    nutrients = {n.slug: n for n in Nutrient.objects.all()}
    units_by_slug = {slug: n.unit for slug, n in nutrients.items()}
    mapped = map_off_nutriments(product.get("nutriments") or {}, units_by_slug)
    if not (mapped.keys() & REQUIRED_ANY):
        raise NoNutrimentsError("That product has no usable nutrition data.")

    with transaction.atomic():
        food = Food.objects.create(
            owner=None,
            name=_off_name(product, barcode),
            brand=_off_brand(product),
            source=FoodSource.OFF,
            source_id=str(product.get("code") or barcode)[:64],
            barcode=barcode,
            is_verified=False,
        )
        ServingSize.objects.create(
            food=food, label="100 g", grams=Decimal("100"), is_default=True
        )
        _add_off_serving(food, product)
        FoodNutrient.objects.bulk_create(
            [
                FoodNutrient(food=food, nutrient=nutrients[slug], amount_per_100g=amount)
                for slug, amount in mapped.items()
            ]
        )
    return food, True


def lookup_barcode_draft(user, barcode: str) -> dict:
    """Resolve a barcode to a New-Food draft WITHOUT persisting anything.

    Prefers an existing global/owned Food (so the form starts from current data);
    otherwise fetches + maps the Open Food Facts product. Returns
    ``{name, brand, unit, barcode, nutrients}`` where ``nutrients`` maps our
    canonical slug -> amount per 100 (string). Raises the same exceptions as
    ``import_food_from_barcode`` (ProductNotFound / NoNutrimentsError /
    UpstreamUnavailable) so the client can confirm before saving.
    """
    from .models import Nutrient

    existing = find_existing_food_by_barcode(user, barcode)
    if existing is not None:
        return {
            "name": existing.name,
            "brand": existing.brand,
            "unit": existing.unit,
            "barcode": barcode,
            "nutrients": {
                fn.nutrient.slug: str(fn.amount_per_100g)
                for fn in existing.food_nutrients.select_related("nutrient").all()
            },
        }

    product = fetch_off_product(barcode)
    if product is None:
        raise ProductNotFound(f"No product found for barcode {barcode}.")
    nutrients = {n.slug: n for n in Nutrient.objects.all()}
    units_by_slug = {slug: n.unit for slug, n in nutrients.items()}
    mapped = map_off_nutriments(product.get("nutriments") or {}, units_by_slug)
    if not (mapped.keys() & REQUIRED_ANY):
        raise NoNutrimentsError("That product has no usable nutrition data.")
    return {
        "name": _off_name(product, barcode),
        "brand": _off_brand(product),
        "unit": "g",
        "barcode": barcode,
        "nutrients": {slug: str(amount) for slug, amount in mapped.items()},
    }
