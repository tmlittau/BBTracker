"""Phase 1 capture quick-wins: water logging + the chloride/caffeine seed."""
from datetime import date

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.nutrition.models import NutritionTarget, WaterLog

pytestmark = pytest.mark.django_db

D0 = date(2026, 7, 1)


@pytest.fixture
def user(db):
    return User.objects.create_user(email="w@example.com", password="x")


@pytest.fixture
def other(db):
    return User.objects.create_user(email="o@example.com", password="x")


@pytest.fixture
def api(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


def test_seed_includes_chloride_and_caffeine():
    from django.core.management import call_command

    call_command("seed_nutrition")
    from apps.nutrition.models import Nutrient

    by_slug = {n.slug: n for n in Nutrient.objects.all()}
    assert by_slug["chloride"].category == "mineral" and by_slug["chloride"].unit == "mg"
    assert by_slug["caffeine"].category == "other" and by_slug["caffeine"].unit == "mg"
    assert by_slug["caffeine"].rda is None


def test_water_quick_add_and_scoped_list(api, user):
    r = api.post("/api/v1/nutrition/water/", {"date": D0.isoformat(), "amount_ml": 250})
    assert r.status_code == 201
    assert r.json()["source"] == "manual"  # default, read-only
    api.post("/api/v1/nutrition/water/", {"date": D0.isoformat(), "amount_ml": 500})
    api.post("/api/v1/nutrition/water/", {"date": "2026-06-30", "amount_ml": 999})

    rows = api.get(f"/api/v1/nutrition/water/?date={D0.isoformat()}").json()
    rows = rows["results"] if isinstance(rows, dict) else rows
    assert sorted(x["amount_ml"] for x in rows) == [250, 500]


def test_water_is_owner_scoped(api, other):
    WaterLog.objects.create(owner=other, date=D0, amount_ml=750)
    rows = api.get(f"/api/v1/nutrition/water/?date={D0.isoformat()}").json()
    rows = rows["results"] if isinstance(rows, dict) else rows
    assert rows == []


def test_daily_summary_reports_water_total_and_goal(api, user):
    WaterLog.objects.create(owner=user, date=D0, amount_ml=300)
    WaterLog.objects.create(owner=user, date=D0, amount_ml=450)
    NutritionTarget.objects.create(owner=user, is_active=True, water_ml=3000)

    water = api.get(f"/api/v1/nutrition/summary/?date={D0.isoformat()}").json()["water"]
    assert water == {"total_ml": 750, "goal_ml": 3000}


def test_daily_summary_water_goal_null_without_target(api, user):
    water = api.get(f"/api/v1/nutrition/summary/?date={D0.isoformat()}").json()["water"]
    assert water == {"total_ml": 0, "goal_ml": None}
