from datetime import date

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.nutrition.models import (
    DiaryEntry,
    Food,
    FoodNutrient,
    Nutrient,
    NutritionTarget,
)

pytestmark = pytest.mark.django_db


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
    return {
        "energy": Nutrient.objects.create(
            name="Calories", slug="energy", category="energy", unit="kcal", is_energy=True
        ),
        "protein": Nutrient.objects.create(
            name="Protein", slug="protein", category="macro", unit="g", rda=56
        ),
        "vitamin_c": Nutrient.objects.create(
            name="Vitamin C", slug="vitamin_c", category="vitamin", unit="mg", rda=90
        ),
    }


@pytest.fixture
def chicken(db, nutrients):
    food = Food.objects.create(name="Chicken breast", source="seed", owner=None)
    FoodNutrient.objects.create(food=food, nutrient=nutrients["energy"], amount_per_100g=165)
    FoodNutrient.objects.create(food=food, nutrient=nutrients["protein"], amount_per_100g=31)
    return food


def test_requires_auth():
    assert APIClient().get("/api/v1/nutrition/foods/").status_code in (401, 403)


def test_global_food_visible(api, chicken):
    resp = api.get("/api/v1/nutrition/foods/")
    assert resp.status_code == 200
    names = [f["name"] for f in resp.json()["results"]]
    assert "Chicken breast" in names


def test_food_search(api, chicken):
    assert api.get("/api/v1/nutrition/foods/?q=chick").json()["count"] == 1
    assert api.get("/api/v1/nutrition/foods/?q=zzz").json()["count"] == 0


def test_create_custom_food_with_nested(api, user, nutrients):
    payload = {
        "name": "My Shake",
        "brand": "Homemade",
        "servings": [{"label": "1 scoop (30 g)", "grams": "30.00", "is_default": True}],
        "food_nutrients": [
            {"nutrient": nutrients["protein"].id, "amount_per_100g": "80.0000"},
            {"nutrient": nutrients["energy"].id, "amount_per_100g": "400.0000"},
        ],
    }
    resp = api.post("/api/v1/nutrition/foods/", payload, format="json")
    assert resp.status_code == 201, resp.content
    food = Food.objects.get(name="My Shake")
    assert food.owner == user
    assert food.source == "custom"
    assert food.servings.count() == 1
    assert food.food_nutrients.count() == 2


def test_cannot_edit_global_food(api, chicken):
    resp = api.patch(
        f"/api/v1/nutrition/foods/{chicken.id}/", {"name": "Hacked"}, format="json"
    )
    assert resp.status_code == 403
    chicken.refresh_from_db()
    assert chicken.name == "Chicken breast"


def test_log_diary_entry_resolves_grams(api, chicken):
    # 1.5 × 100 g serving → but no serving given, so quantity is grams.
    resp = api.post(
        "/api/v1/nutrition/diary-entries/",
        {"date": "2026-05-30", "food": chicken.id, "quantity": "150"},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    assert resp.json()["grams"] == "150.00"


def test_diary_entry_with_serving(api, chicken):
    serving = chicken.servings.create(label="1 fillet", grams=200, is_default=True)
    resp = api.post(
        "/api/v1/nutrition/diary-entries/",
        {"date": "2026-05-30", "food": chicken.id,
         "serving": serving.id, "quantity": "2"},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    # 2 servings × 200 g = 400 g
    assert resp.json()["grams"] == "400.00"


def test_diary_requires_food_or_recipe(api):
    resp = api.post(
        "/api/v1/nutrition/diary-entries/",
        {"date": "2026-05-30", "quantity": "1"},
        format="json",
    )
    assert resp.status_code == 400


def test_summary_totals_and_target(api, user, chicken, nutrients):
    # Target: 2000 kcal, 150 g protein.
    target = NutritionTarget.objects.create(
        owner=user, name="Cut", is_active=True, calories=2000, protein_g=150
    )
    target.nutrient_targets.create(nutrient=nutrients["vitamin_c"], amount=90)

    # Log 200 g chicken → 330 kcal, 62 g protein.
    DiaryEntry.objects.create(
        owner=user, date=date(2026, 5, 30), food=chicken, quantity=200
    )

    resp = api.get("/api/v1/nutrition/summary/?date=2026-05-30")
    assert resp.status_code == 200, resp.content
    data = resp.json()
    assert data["has_target"] is True
    assert data["target_name"] == "Cut"
    assert data["totals"]["calories"] == "330.000"
    assert data["totals"]["protein_g"] == "62.000"

    by_slug = {n["slug"]: n for n in data["nutrients"]}
    # protein: 62 / 150 = 41%
    assert by_slug["protein"]["percent"] == 41
    # energy: 330 / 2000 = 16%
    assert by_slug["energy"]["percent"] == 16


def test_summary_empty_day(api, user, nutrients):
    resp = api.get("/api/v1/nutrition/summary/?date=2026-01-01")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_target"] is False
    assert data["totals"]["calories"] == "0.000"


def test_target_activate_is_exclusive(api):
    t1 = api.post("/api/v1/nutrition/targets/", {"name": "A"}, format="json").json()["id"]
    t2 = api.post("/api/v1/nutrition/targets/", {"name": "B"}, format="json").json()["id"]
    api.post(f"/api/v1/nutrition/targets/{t1}/activate/")
    api.post(f"/api/v1/nutrition/targets/{t2}/activate/")
    assert NutritionTarget.objects.get(id=t1).is_active is False
    assert NutritionTarget.objects.get(id=t2).is_active is True


def test_diary_owner_isolation(api, other, chicken):
    theirs = DiaryEntry.objects.create(
        owner=other, date=date(2026, 5, 30), food=chicken, quantity=100
    )
    assert api.get(f"/api/v1/nutrition/diary-entries/{theirs.id}/").status_code == 404
    # And another user's entries never appear in the date listing.
    listed = api.get("/api/v1/nutrition/diary-entries/?date=2026-05-30").json()["results"]
    assert theirs.id not in {e["id"] for e in listed}


def test_can_log_global_food_but_not_others_custom(api, other, nutrients):
    others_food = Food.objects.create(name="Their secret food", owner=other, source="custom")
    resp = api.post(
        "/api/v1/nutrition/diary-entries/",
        {"date": "2026-05-30", "food": others_food.id, "quantity": "100"},
        format="json",
    )
    assert resp.status_code == 403


def test_meal_template_create_and_apply(api, user, chicken):
    """Create a meal template, then apply it to a meal → diary entries appear."""
    resp = api.post(
        "/api/v1/nutrition/meal-templates/",
        {"name": "Breakfast staple", "items": [{"food": chicken.id, "quantity": "150"}]},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    tid = resp.json()["id"]
    assert resp.json()["items"][0]["food_name"] == "Chicken breast"

    meal = api.post(
        "/api/v1/nutrition/meals/", {"date": "2026-06-12", "name": "Breakfast"}, format="json"
    ).json()
    applied = api.post(
        f"/api/v1/nutrition/meal-templates/{tid}/apply/", {"meal": meal["id"]}, format="json"
    )
    assert applied.status_code == 201, applied.content
    assert applied.json()["created"] == 1
    entry = DiaryEntry.objects.get(owner=user, meal_id=meal["id"])
    assert entry.food_id == chicken.id
    assert str(entry.quantity) == "150.00"
    assert str(entry.date) == "2026-06-12"


def test_meal_template_from_meal(api, user, chicken):
    """Save an existing meal's foods as a template."""
    meal = api.post(
        "/api/v1/nutrition/meals/", {"date": "2026-06-12", "name": "Lunch"}, format="json"
    ).json()
    api.post(
        "/api/v1/nutrition/diary-entries/",
        {"date": "2026-06-12", "meal": meal["id"], "food": chicken.id, "quantity": "200"},
        format="json",
    )
    resp = api.post(
        "/api/v1/nutrition/meal-templates/from_meal/", {"meal": meal["id"]}, format="json"
    )
    assert resp.status_code == 201, resp.content
    assert resp.json()["name"] == "Lunch"
    assert [i["food"] for i in resp.json()["items"]] == [chicken.id]


def test_meal_template_owner_isolation(api, other):
    from apps.nutrition.models import MealTemplate

    theirs = MealTemplate.objects.create(owner=other, name="Theirs")
    assert api.get(f"/api/v1/nutrition/meal-templates/{theirs.id}/").status_code == 404


def test_nutrition_headline_matches_daily_summary(user, chicken):
    """The light dashboard headline equals daily_summary's headline numbers."""
    from apps.nutrition.models import DiaryEntry, Meal
    from apps.nutrition.services import daily_summary, nutrition_headline

    d = date(2026, 6, 1)
    m = Meal.objects.create(owner=user, date=d, name="Lunch")
    DiaryEntry.objects.create(owner=user, date=d, meal=m, food=chicken, quantity=150)
    full = daily_summary(user, d)
    light = nutrition_headline(user, d)
    assert light["calories"] == full["totals"]["calories"]
    assert light["protein_g"] == full["totals"]["protein_g"]
    assert light["has_target"] == full["has_target"]
    assert light["target_name"] == full["target_name"]


def test_cached_nutrients_caches_until_cleared(db):
    from django.core.cache import cache

    from apps.nutrition.models import Nutrient
    from apps.nutrition.services import NUTRIENTS_CACHE_KEY, cached_nutrients

    cache.delete(NUTRIENTS_CACHE_KEY)
    Nutrient.objects.create(name="Calories", slug="energy", category="energy", unit="kcal")
    first = cached_nutrients()
    assert any(n["slug"] == "energy" for n in first)
    # A nutrient added after the cache is warm isn't seen until the key is cleared.
    Nutrient.objects.create(name="Zinc", slug="zinc", category="mineral", unit="mg")
    assert cached_nutrients() == first
    cache.delete(NUTRIENTS_CACHE_KEY)
    assert any(n["slug"] == "zinc" for n in cached_nutrients())


def test_weekly_macro_adherence_averages_days_with_intake(user, chicken):
    from datetime import timedelta

    from apps.nutrition.models import DiaryEntry
    from apps.nutrition.services import weekly_macro_adherence

    end = date(2026, 6, 7)
    DiaryEntry.objects.create(owner=user, date=end, food=chicken, quantity=200)  # 330 kcal
    DiaryEntry.objects.create(owner=user, date=end - timedelta(days=2), food=chicken, quantity=100)
    res = weekly_macro_adherence(user, end - timedelta(days=6), end)
    assert res["days_logged"] == 2
    assert res["avg_calories"] == round((330 + 165) / 2, 0)
