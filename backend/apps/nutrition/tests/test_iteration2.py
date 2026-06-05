"""Iteration-2 nutrition: per-day Meal objects, attachment, reorder, copy."""
from datetime import date

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.nutrition.models import Food, Meal

pytestmark = pytest.mark.django_db


@pytest.fixture
def user(db):
    return User.objects.create_user(email="m2@example.com", password="x")


@pytest.fixture
def api(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def chicken(db):
    return Food.objects.create(name="Chicken breast", source="seed", owner=None)


def test_create_meal_and_log_entry_into_it(api, user, chicken):
    meal = api.post(
        "/api/v1/nutrition/meals/",
        {"date": "2026-06-01", "name": "Breakfast", "order": 0},
        format="json",
    )
    assert meal.status_code == 201, meal.content
    mid = meal.json()["id"]
    assert Meal.objects.get(id=mid).owner == user

    entry = api.post(
        "/api/v1/nutrition/diary-entries/",
        {"date": "2026-06-01", "meal": mid, "food": chicken.id, "quantity": "150"},
        format="json",
    )
    assert entry.status_code == 201, entry.content
    assert entry.json()["meal"] == mid


def test_meals_filtered_by_date_and_owner(api, user):
    Meal.objects.create(owner=user, date=date(2026, 6, 1), name="Breakfast", order=0)
    Meal.objects.create(owner=user, date=date(2026, 6, 2), name="Lunch", order=0)
    other = User.objects.create_user(email="z@example.com", password="x")
    Meal.objects.create(owner=other, date=date(2026, 6, 1), name="Theirs", order=0)

    listed = api.get("/api/v1/nutrition/meals/?date=2026-06-01").json()["results"]
    assert {m["name"] for m in listed} == {"Breakfast"}


def test_cannot_log_into_others_meal(api, chicken):
    other = User.objects.create_user(email="z2@example.com", password="x")
    theirs = Meal.objects.create(owner=other, date=date(2026, 6, 1), name="Theirs", order=0)
    resp = api.post(
        "/api/v1/nutrition/diary-entries/",
        {"date": "2026-06-01", "meal": theirs.id, "food": chicken.id, "quantity": "100"},
        format="json",
    )
    assert resp.status_code == 403


def test_meal_reorder(api, user):
    a = Meal.objects.create(owner=user, date=date(2026, 6, 1), name="A", order=0)
    b = Meal.objects.create(owner=user, date=date(2026, 6, 1), name="B", order=1)
    resp = api.post(
        "/api/v1/nutrition/meals/reorder/",
        [{"id": a.id, "order": 1}, {"id": b.id, "order": 0}],
        format="json",
    )
    assert resp.status_code == 200 and resp.json()["updated"] == 2
    a.refresh_from_db()
    b.refresh_from_db()
    assert a.order == 1 and b.order == 0


def test_copy_yesterday_meals(api, user):
    Meal.objects.create(owner=user, date=date(2026, 6, 1), name="Breakfast", order=0)
    Meal.objects.create(owner=user, date=date(2026, 6, 1), name="Lunch", order=1)
    resp = api.post(
        "/api/v1/nutrition/meals/copy_yesterday/", {"date": "2026-06-02"}, format="json"
    )
    assert resp.status_code == 200
    copied = resp.json()
    assert {m["name"] for m in copied} == {"Breakfast", "Lunch"}
    assert all(m["date"] == "2026-06-02" for m in copied)
