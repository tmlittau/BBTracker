"""USDA FoodData Central generic-food search and review-draft tests."""

import json
import urllib.error
from decimal import Decimal
from unittest import mock

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.nutrition.models import Food, Nutrient
from apps.nutrition.services import (
    FDC_GENERIC_DATA_TYPES,
    FDC_USER_AGENT,
    FoodDataCentralNotFound,
    FoodDataCentralUnavailable,
    _fdc_request,
    lookup_fdc_food_draft,
    map_fdc_nutrients,
    search_fdc_foods,
)

pytestmark = pytest.mark.django_db

SEARCH_URL = "/api/v1/nutrition/foods/search_generic/"
LOOKUP_URL = "/api/v1/nutrition/foods/lookup_generic/"

FDC_SEARCH_RESPONSE = {
    "totalHits": 42,
    "foods": [
        {
            "fdcId": 171477,
            "description": "Chicken, breast, meat only, cooked, roasted",
            "dataType": "SR Legacy",
            "foodCategory": "Poultry Products",
            "publicationDate": "4/1/2019",
        }
    ],
}

FDC_DETAIL_RESPONSE = {
    "fdcId": 171477,
    "description": "Chicken, breast, meat only, cooked, roasted",
    "dataType": "SR Legacy",
    "foodCategory": {"description": "Poultry Products"},
    "publicationDate": "4/1/2019",
    "foodNutrients": [
        {"nutrient": {"number": "208", "unitName": "kcal"}, "amount": 165},
        {"nutrient": {"number": "203", "unitName": "g"}, "amount": 31.02},
        {"nutrient": {"number": "307", "unitName": "mg"}, "amount": 74},
        {"nutrient": {"number": "317", "unitName": "µg"}, "amount": 27.6},
        {"nutrient": {"number": "328", "unitName": "µg"}, "amount": 0.1},
        # Parallel vitamin-D IU value must not overwrite the canonical µg value.
        {"nutrient": {"number": "324", "unitName": "IU"}, "amount": 5},
        # An explicit zero remains a real value; absent nutrients remain absent.
        {"nutrient": {"number": "205", "unitName": "g"}, "amount": 0},
    ],
    "foodPortions": [
        {"amount": 1, "modifier": "cup, chopped", "gramWeight": 140},
        {"amount": 0.5, "modifier": "breast", "gramWeight": 86},
    ],
}


@pytest.fixture
def user(db):
    return User.objects.create_user(email="usda@example.com", password="x")


@pytest.fixture
def api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def nutrients(db):
    specs = [
        ("energy", "kcal", "energy"),
        ("protein", "g", "macro"),
        ("carbohydrate", "g", "macro"),
        ("sodium", "mg", "mineral"),
        ("selenium", "mcg", "mineral"),
        ("vitamin_d", "mcg", "vitamin"),
    ]
    return {
        slug: Nutrient.objects.create(
            name=slug.replace("_", " ").title(),
            slug=slug,
            unit=unit,
            category=category,
            is_energy=slug == "energy",
        )
        for slug, unit, category in specs
    }


@mock.patch("apps.nutrition.services._fdc_request", return_value=FDC_SEARCH_RESPONSE)
def test_search_service_filters_to_generic_data_and_paginates(mock_request):
    result = search_fdc_foods("  chicken   breast  ", page=2, page_size=10)

    assert result == {
        "total_hits": 42,
        "page": 2,
        "page_size": 10,
        "total_pages": 5,
        "results": [
            {
                "fdc_id": 171477,
                "description": "Chicken, breast, meat only, cooked, roasted",
                "data_type": "SR Legacy",
                "food_category": "Poultry Products",
                "publication_date": "4/1/2019",
            }
        ],
    }
    _, kwargs = mock_request.call_args
    assert kwargs["body"]["query"] == "chicken breast"
    assert kwargs["body"]["dataType"] == FDC_GENERIC_DATA_TYPES
    assert kwargs["body"]["pageNumber"] == 2


@mock.patch(
    "apps.nutrition.views.search_fdc_foods",
    return_value={"total_hits": 0, "page": 1, "page_size": 20, "total_pages": 0, "results": []},
)
def test_search_endpoint_validates_and_forwards_query(mock_search, api):
    response = api.get(SEARCH_URL, {"q": "oats"})
    assert response.status_code == 200
    mock_search.assert_called_once_with(query="oats", page=1, page_size=20)
    assert api.get(SEARCH_URL, {"q": "x"}).status_code == 400


def test_generic_endpoints_require_auth():
    client = APIClient()
    assert client.get(SEARCH_URL, {"q": "oats"}).status_code in (401, 403)
    assert client.post(LOOKUP_URL, {"fdc_id": 171477}, format="json").status_code in (401, 403)


def test_map_fdc_nutrients_converts_units_and_preserves_zero():
    mapped = map_fdc_nutrients(
        FDC_DETAIL_RESPONSE["foodNutrients"],
        {
            "energy": "kcal",
            "protein": "g",
            "carbohydrate": "g",
            "sodium": "g",
            "selenium": "mg",
            "vitamin_d": "mcg",
        },
    )
    assert mapped["energy"] == Decimal("165.0000")
    assert mapped["carbohydrate"] == Decimal("0.0000")
    assert mapped["sodium"] == Decimal("0.0740")
    assert mapped["selenium"] == Decimal("0.0276")
    assert mapped["vitamin_d"] == Decimal("0.1000")


@mock.patch("apps.nutrition.services._fdc_request", return_value=FDC_DETAIL_RESPONSE)
def test_lookup_returns_reviewable_draft_without_saving(mock_request, nutrients):
    draft = lookup_fdc_food_draft(171477)

    assert draft["source"] == "usda"
    assert draft["source_id"] == "171477"
    assert draft["name"].startswith("Chicken")
    assert draft["nutrients"]["protein"] == "31.0200"
    assert draft["nutrients"]["carbohydrate"] == "0.0000"
    assert "fat" not in draft["nutrients"]
    assert draft["servings"][0] == {"label": "100 g", "grams": "100", "is_default": True}
    assert {row["label"] for row in draft["servings"]} == {"100 g", "cup, chopped", "0.5 breast"}
    assert Food.objects.count() == 0
    mock_request.assert_called_once_with("food/171477")


@mock.patch("apps.nutrition.services._fdc_request", return_value=FDC_DETAIL_RESPONSE)
def test_lookup_endpoint_returns_draft(mock_request, api, nutrients):
    response = api.post(LOOKUP_URL, {"fdc_id": 171477}, format="json")
    assert response.status_code == 200, response.content
    assert response.json()["source_id"] == "171477"
    assert Food.objects.count() == 0


def test_reviewed_usda_draft_saves_owned_snapshot_with_provenance(api, user, nutrients):
    response = api.post(
        "/api/v1/nutrition/foods/",
        {
            "name": "Chicken breast, cooked",
            "brand": "",
            "source": "usda",
            "source_id": "171477",
            "unit": "g",
            "barcode": "",
            "servings": [{"label": "100 g", "grams": 100, "is_default": True}],
            "food_nutrients": [{"nutrient": nutrients["protein"].id, "amount_per_100g": 31.02}],
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    food = Food.objects.get()
    assert food.owner == user
    assert food.source == "usda"
    assert food.source_id == "171477"
    assert response.json()["source_id"] == "171477"


def test_new_food_cannot_spoof_backend_owned_source(api):
    response = api.post(
        "/api/v1/nutrition/foods/",
        {"name": "Spoof", "source": "off", "source_id": "123"},
        format="json",
    )
    assert response.status_code == 400
    assert Food.objects.count() == 0


def test_saved_food_provenance_is_immutable(api, user):
    food = Food.objects.create(name="Custom", owner=user)

    response = api.patch(
        f"/api/v1/nutrition/foods/{food.id}/",
        {"source": "usda", "source_id": "171477"},
        format="json",
    )

    assert response.status_code == 400
    food.refresh_from_db()
    assert food.source == "custom"
    assert food.source_id == ""


class _FakeResponse:
    def __init__(self, payload):
        self.body = json.dumps(payload).encode()

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@override_settings(USDA_FDC_API_KEY="test-key", USDA_FDC_API_BASE="https://example.test/fdc/v1")
def test_fdc_request_keeps_key_server_side_and_posts_json():
    with mock.patch(
        "urllib.request.urlopen", return_value=_FakeResponse(FDC_SEARCH_RESPONSE)
    ) as mocked:
        result = _fdc_request("foods/search", body={"query": "oats"})
    assert result == FDC_SEARCH_RESPONSE
    request = mocked.call_args.args[0]
    assert request.full_url == "https://example.test/fdc/v1/foods/search?api_key=test-key"
    assert request.method == "POST"
    assert request.get_header("User-agent") == FDC_USER_AGENT
    assert json.loads(request.data) == {"query": "oats"}


@override_settings(USDA_FDC_API_KEY="test-key", USDA_FDC_API_BASE="https://example.test/fdc/v1")
def test_fdc_request_maps_not_found_and_rate_limit():
    with (
        mock.patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.HTTPError("u", 404, "Not found", {}, None),
        ),
        pytest.raises(FoodDataCentralNotFound),
    ):
        _fdc_request("food/1")
    with (
        mock.patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.HTTPError("u", 429, "Limited", {}, None),
        ),
        pytest.raises(FoodDataCentralUnavailable),
    ):
        _fdc_request("foods/search", body={"query": "oats"})
