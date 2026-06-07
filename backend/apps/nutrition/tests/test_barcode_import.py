"""Tests for the Open Food Facts barcode import.

The OFF HTTP call is always mocked — these tests never hit the network. Two
mock seams are exercised:
  * `services.fetch_off_product` — for the endpoint / orchestration behaviour
  * `urllib.request.urlopen`     — for `fetch_off_product`'s own parsing/errors
plus the pure `map_off_nutriments` mapper (no DB, no network).
"""
import json
import urllib.error
from decimal import Decimal
from unittest import mock

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.nutrition.models import Food, FoodNutrient, Nutrient
from apps.nutrition.services import (
    OFF_USER_AGENT,
    UpstreamUnavailable,
    fetch_off_product,
    map_off_nutriments,
)

pytestmark = pytest.mark.django_db

URL = "/api/v1/nutrition/foods/import_barcode/"

# A trimmed OFF `product` payload (what `fetch_off_product` returns), modelled on
# a real branded product. Includes gram-based mineral values (to exercise unit
# conversion), a zero-valued macro + zero-valued micros, and an unmapped key.
OFF_PRODUCT = {
    "code": "3017620422003",
    "product_name": "Nutella",
    "brands": "Ferrero, Nutella",
    "serving_size": "15 g",
    "serving_quantity": 15,
    "nutriments": {
        "energy-kcal_100g": 539,
        "proteins_100g": 6.3,
        "carbohydrates_100g": 57.5,
        "sugars_100g": 56.3,
        "fat_100g": 30.9,
        "saturated-fat_100g": 10.6,
        "fiber_100g": 0,
        "sodium_100g": 0.0428,  # grams → 42.8 mg
        "salt_100g": 0.107,  # unmapped → ignored
        "calcium_100g": 0.108,  # grams → 108 mg
        "iron_100g": 0.0,  # zero micro → dropped
        "vitamin-c_100g": 0.0,  # zero micro → dropped
    },
}


@pytest.fixture
def user(db):
    return User.objects.create_user(email="a@example.com", password="x")


@pytest.fixture
def other(db):
    return User.objects.create_user(email="b@example.com", password="x")


@pytest.fixture
def api(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def nutrients(db):
    """The slugs/units the OFF_PRODUCT maps onto (mirrors seed_nutrition)."""
    specs = [
        ("energy", "kcal"),
        ("protein", "g"),
        ("carbohydrate", "g"),
        ("sugar", "g"),
        ("fat", "g"),
        ("saturated_fat", "g"),
        ("fiber", "g"),
        ("sodium", "mg"),
        ("calcium", "mg"),
        ("iron", "mg"),
        ("vitamin_c", "mg"),
    ]
    cat = {"energy": "energy"}
    return {
        slug: Nutrient.objects.create(
            name=slug.replace("_", " ").title(),
            slug=slug,
            unit=unit,
            category=cat.get(slug, "macro" if unit == "g" else "mineral"),
            is_energy=slug == "energy",
        )
        for slug, unit in specs
    }


# --- Endpoint: create from OFF ------------------------------------------------


@mock.patch("apps.nutrition.services.fetch_off_product", return_value=OFF_PRODUCT)
def test_import_creates_global_food_from_off(mock_fetch, api, nutrients):
    resp = api.post(URL, {"barcode": "3017620422003"}, format="json")

    assert resp.status_code == 201, resp.content
    mock_fetch.assert_called_once_with("3017620422003")
    data = resp.json()
    assert data["source"] == "off"
    assert data["is_global"] is True
    assert data["brand"] == "Ferrero"
    assert data["barcode"] == "3017620422003"

    food = Food.objects.get(barcode="3017620422003")
    assert food.owner_id is None  # global
    assert food.name == "Nutella"
    assert food.source_id == "3017620422003"
    assert food.is_verified is False

    # A 100 g default serving, plus OFF's own 15 g serving (non-default).
    default = food.servings.get(is_default=True)
    assert default.label == "100 g" and default.grams == Decimal("100.00")
    assert {s.label for s in food.servings.all()} == {"100 g", "15 g"}

    amounts = {
        fn.nutrient.slug: fn.amount_per_100g
        for fn in food.food_nutrients.select_related("nutrient")
    }
    assert amounts["energy"] == Decimal("539.0000")
    assert amounts["protein"] == Decimal("6.3000")
    assert amounts["carbohydrate"] == Decimal("57.5000")
    assert amounts["fat"] == Decimal("30.9000")
    assert amounts["saturated_fat"] == Decimal("10.6000")
    assert amounts["fiber"] == Decimal("0.0000")  # core macro kept at 0
    assert amounts["sodium"] == Decimal("42.8000")  # 0.0428 g → 42.8 mg
    assert amounts["calcium"] == Decimal("108.0000")  # 0.108 g → 108 mg
    # Zero-valued micros dropped; unmapped `salt` ignored.
    assert "iron" not in amounts
    assert "vitamin_c" not in amounts


# --- Endpoint: existing food short-circuits (no fetch) ------------------------


@mock.patch("apps.nutrition.services.fetch_off_product")
def test_existing_owned_food_short_circuits(mock_fetch, api, user):
    food = Food.objects.create(
        name="My snack", owner=user, source="custom", barcode="1234567890"
    )
    resp = api.post(URL, {"barcode": "1234567890"}, format="json")
    assert resp.status_code == 200, resp.content
    assert resp.json()["id"] == food.id
    mock_fetch.assert_not_called()


@mock.patch("apps.nutrition.services.fetch_off_product")
def test_existing_global_food_returned(mock_fetch, api):
    food = Food.objects.create(
        name="Seeded bar", owner=None, source="seed", barcode="5901234123457"
    )
    resp = api.post(URL, {"barcode": "5901234123457"}, format="json")
    assert resp.status_code == 200
    assert resp.json()["id"] == food.id
    mock_fetch.assert_not_called()


@mock.patch("apps.nutrition.services.fetch_off_product", return_value=None)
def test_other_users_food_does_not_short_circuit(mock_fetch, api, other):
    # Another user's *custom* food with the same barcode must NOT be returned;
    # the import falls through to OFF (here: not found → 404).
    Food.objects.create(name="Theirs", owner=other, source="custom", barcode="999999999999")
    resp = api.post(URL, {"barcode": "999999999999"}, format="json")
    assert resp.status_code == 404
    mock_fetch.assert_called_once()


# --- Endpoint: graceful failure modes -----------------------------------------


@mock.patch("apps.nutrition.services.fetch_off_product", return_value=None)
def test_not_found_returns_404(mock_fetch, api, nutrients):
    resp = api.post(URL, {"barcode": "00000000"}, format="json")
    assert resp.status_code == 404
    assert Food.objects.filter(barcode="00000000").count() == 0


@mock.patch(
    "apps.nutrition.services.fetch_off_product",
    return_value={"code": "111", "product_name": "Mystery", "nutriments": {}},
)
def test_no_nutriments_returns_422(mock_fetch, api, nutrients):
    resp = api.post(URL, {"barcode": "11111111"}, format="json")
    assert resp.status_code == 422
    assert Food.objects.filter(barcode="11111111").count() == 0  # nothing created


@mock.patch(
    "apps.nutrition.services.fetch_off_product",
    side_effect=UpstreamUnavailable("boom"),
)
def test_upstream_error_returns_502(mock_fetch, api, nutrients):
    resp = api.post(URL, {"barcode": "22222222"}, format="json")
    assert resp.status_code == 502


@mock.patch("apps.nutrition.services.fetch_off_product")
def test_invalid_barcode_returns_400(mock_fetch, api):
    resp = api.post(URL, {"barcode": "not-a-barcode"}, format="json")
    assert resp.status_code == 400
    mock_fetch.assert_not_called()


def test_import_requires_auth():
    resp = APIClient().post(URL, {"barcode": "12345678"}, format="json")
    assert resp.status_code in (401, 403)


# --- Endpoint: lookup_barcode (draft only — nothing persisted) ----------------

LOOKUP_URL = "/api/v1/nutrition/foods/lookup_barcode/"


@mock.patch("apps.nutrition.services.fetch_off_product", return_value=OFF_PRODUCT)
def test_lookup_returns_draft_without_saving(mock_fetch, api, nutrients):
    resp = api.post(LOOKUP_URL, {"barcode": "3017620422003"}, format="json")

    assert resp.status_code == 200, resp.content
    data = resp.json()
    assert data["name"] == "Nutella"
    assert data["brand"] == "Ferrero"
    assert data["unit"] == "g"
    assert data["barcode"] == "3017620422003"
    # Nutrients keyed by our canonical slug, in our units (mass converted to mg).
    assert data["nutrients"]["energy"] == "539.0000"
    assert data["nutrients"]["sodium"] == "42.8000"  # 0.0428 g → 42.8 mg
    # Crucially: nothing was persisted — the user confirms in the form first.
    assert Food.objects.filter(barcode="3017620422003").count() == 0


@mock.patch("apps.nutrition.services.fetch_off_product")
def test_lookup_uses_existing_food(mock_fetch, api, user, nutrients):
    food = Food.objects.create(
        name="My snack", owner=user, source="custom", barcode="1234567890", unit="g"
    )
    FoodNutrient.objects.create(
        food=food, nutrient=nutrients["protein"], amount_per_100g=Decimal("12.5")
    )
    resp = api.post(LOOKUP_URL, {"barcode": "1234567890"}, format="json")

    assert resp.status_code == 200, resp.content
    data = resp.json()
    assert data["name"] == "My snack"
    assert data["nutrients"]["protein"] == "12.5000"
    mock_fetch.assert_not_called()


@mock.patch("apps.nutrition.services.fetch_off_product", return_value=None)
def test_lookup_not_found_returns_404(mock_fetch, api, nutrients):
    resp = api.post(LOOKUP_URL, {"barcode": "00000000"}, format="json")
    assert resp.status_code == 404


def test_lookup_requires_auth():
    resp = APIClient().post(LOOKUP_URL, {"barcode": "12345678"}, format="json")
    assert resp.status_code in (401, 403)


# --- Pure mapper: map_off_nutriments ------------------------------------------


class TestMapOffNutriments:
    units = {
        "energy": "kcal",
        "protein": "g",
        "fat": "g",
        "fiber": "g",
        "sodium": "mg",
        "calcium": "mg",
        "selenium": "mcg",
        "niacin": "mg",
    }

    def test_macros_and_energy_passthrough(self):
        out = map_off_nutriments(
            {"energy-kcal_100g": 200, "proteins_100g": 10, "fat_100g": 5}, self.units
        )
        assert out["energy"] == Decimal("200.0000")
        assert out["protein"] == Decimal("10.0000")
        assert out["fat"] == Decimal("5.0000")

    def test_mg_and_mcg_unit_conversion(self):
        out = map_off_nutriments(
            {"sodium_100g": 0.5, "calcium_100g": 0.12, "selenium_100g": 0.00005},
            self.units,
        )
        assert out["sodium"] == Decimal("500.0000")  # 0.5 g → 500 mg
        assert out["calcium"] == Decimal("120.0000")  # 0.12 g → 120 mg
        assert out["selenium"] == Decimal("50.0000")  # 0.00005 g → 50 µg

    def test_zero_micro_dropped_but_core_macro_kept(self):
        out = map_off_nutriments({"fiber_100g": 0, "sodium_100g": 0}, self.units)
        assert out["fiber"] == Decimal("0.0000")  # core macro kept at 0
        assert "sodium" not in out  # zero-valued micro dropped

    def test_unknown_slug_skipped(self):
        # vitamin_d isn't in this units map → skipped even though present.
        assert map_off_nutriments({"vitamin-d_100g": 0.00002}, self.units) == {}

    def test_alias_fills_when_canonical_absent(self):
        # 'niacin' alias maps to slug niacin when canonical 'vitamin-pp' is absent.
        out = map_off_nutriments({"niacin_100g": 0.016}, self.units)
        assert out["niacin"] == Decimal("16.0000")  # 0.016 g → 16 mg

    def test_blank_and_missing_values_skipped(self):
        assert map_off_nutriments({"proteins_100g": "", "fat_100g": None}, self.units) == {}


# --- Network seam: fetch_off_product (urlopen mocked) -------------------------


class _FakeResp:
    """Minimal stand-in for an http.client response usable as a context manager."""

    def __init__(self, body: bytes):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TestFetchOffProduct:
    def test_success_returns_product_and_builds_request(self):
        payload = {"status": 1, "product": {"product_name": "X", "nutriments": {}}}
        body = json.dumps(payload).encode()
        with mock.patch(
            "urllib.request.urlopen", return_value=_FakeResp(body)
        ) as m:
            product = fetch_off_product("3017620422003")
        assert product == payload["product"]
        request = m.call_args.args[0]
        assert request.full_url.endswith("/api/v2/product/3017620422003.json")
        assert request.get_header("User-agent") == OFF_USER_AGENT

    def test_status_zero_is_not_found(self):
        body = json.dumps({"status": 0, "status_verbose": "not found"}).encode()
        with mock.patch("urllib.request.urlopen", return_value=_FakeResp(body)):
            assert fetch_off_product("0000") is None

    def test_http_404_is_not_found(self):
        err = urllib.error.HTTPError("u", 404, "Not Found", {}, None)
        with mock.patch("urllib.request.urlopen", side_effect=err):
            assert fetch_off_product("0000") is None

    def test_http_500_raises_upstream(self):
        err = urllib.error.HTTPError("u", 500, "Server Error", {}, None)
        with mock.patch("urllib.request.urlopen", side_effect=err):
            with pytest.raises(UpstreamUnavailable):
                fetch_off_product("0000")

    def test_network_error_raises_upstream(self):
        with mock.patch(
            "urllib.request.urlopen", side_effect=urllib.error.URLError("down")
        ):
            with pytest.raises(UpstreamUnavailable):
                fetch_off_product("0000")
