from datetime import date, timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.models import Phase
from apps.diary.models import CheckIn
from apps.nutrition.models import Food, FoodNutrient, Nutrient, NutritionTarget
from apps.protocols.models import Compound, DoseLog
from apps.training.models import Exercise, LoggedExercise, LoggedSet, Program, WorkoutSession

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


def test_requires_auth():
    assert APIClient().get("/api/v1/phases/").status_code in (401, 403)


def test_phase_crud_and_adjustments(api, user):
    target = NutritionTarget.objects.create(owner=user, name="Cut", calories=2200)
    program = Program.objects.create(owner=user, name="PPL")
    resp = api.post(
        "/api/v1/phases/",
        {"name": "Summer prep", "phase_type": "prep", "start_date": "2026-05-01"},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    phase = resp.json()
    assert phase["is_ongoing"] is True
    assert phase["adjustments"] == []
    # The prescription lives in a dated adjustment.
    adj = api.post(
        "/api/v1/phase-adjustments/",
        {"phase": phase["id"], "effective_date": "2026-05-01", "reason": "Start",
         "nutrition_target": target.id, "program": program.id},
        format="json",
    )
    assert adj.status_code == 201, adj.content
    assert adj.json()["nutrition_target_name"] == "Cut"
    assert adj.json()["program_name"] == "PPL"
    full = api.get(f"/api/v1/phases/{phase['id']}/").json()
    assert len(full["adjustments"]) == 1


def test_cannot_link_others_target(api, other):
    theirs = NutritionTarget.objects.create(owner=other, name="Theirs")
    phase = api.post(
        "/api/v1/phases/",
        {"name": "P", "phase_type": "bulk", "start_date": "2026-05-01"},
        format="json",
    ).json()
    resp = api.post(
        "/api/v1/phase-adjustments/",
        {"phase": phase["id"], "effective_date": "2026-05-01", "nutrition_target": theirs.id},
        format="json",
    )
    assert resp.status_code == 403


def test_phase_owner_isolation(api, other):
    theirs = Phase.objects.create(owner=other, name="Theirs", start_date=date(2026, 1, 1))
    assert api.get(f"/api/v1/phases/{theirs.id}/").status_code == 404
    listed = api.get("/api/v1/phases/").json()["results"]
    assert theirs.id not in {p["id"] for p in listed}


def test_current_phase_resolution_on_dashboard(api, user):
    # An ongoing phase that started before today should surface on the dashboard.
    Phase.objects.create(owner=user, name="Off-season", phase_type="bulk",
                         start_date=date.today() - timedelta(days=10))
    resp = api.get("/api/v1/dashboard/today/")
    assert resp.status_code == 200
    assert resp.json()["phase"]["name"] == "Off-season"


def test_phase_adjustment_resolves_by_date(api, user):
    from apps.core.models import PhaseAdjustment

    t1 = NutritionTarget.objects.create(owner=user, name="Bulk 3000", calories=3000)
    t2 = NutritionTarget.objects.create(owner=user, name="Cut 2200", calories=2200)
    today = date.today()
    phase = Phase.objects.create(owner=user, name="Prep", phase_type="prep",
                                 start_date=today - timedelta(days=30))
    PhaseAdjustment.objects.create(phase=phase, effective_date=today - timedelta(days=30),
                                   nutrition_target=t1, reason="start")
    PhaseAdjustment.objects.create(phase=phase, effective_date=today - timedelta(days=7),
                                   nutrition_target=t2, reason="weight stalled")
    brief = api.get("/api/v1/dashboard/today/").json()["phase"]
    assert brief["name"] == "Prep"
    # The later adjustment (Cut 2200) is the one in force today.
    assert brief["nutrition_target_name"] == "Cut 2200"


def test_dashboard_aggregates_domains(api, user):
    today = date.today()
    # Nutrition: active target + a logged food.
    energy = Nutrient.objects.create(name="Calories", slug="energy", category="energy",
                                     unit="kcal", is_energy=True)
    protein = Nutrient.objects.create(name="Protein", slug="protein", category="macro",
                                      unit="g")
    NutritionTarget.objects.create(owner=user, name="Cut", is_active=True,
                                   calories=2000, protein_g=180)
    chicken = Food.objects.create(name="Chicken", source="seed")
    FoodNutrient.objects.create(food=chicken, nutrient=energy, amount_per_100g=165)
    FoodNutrient.objects.create(food=chicken, nutrient=protein, amount_per_100g=31)
    from apps.nutrition.models import DiaryEntry

    DiaryEntry.objects.create(owner=user, date=today, food=chicken, quantity=200)

    # Training: a session today with a PR.
    ex = Exercise.objects.create(name="Bench")
    session = WorkoutSession.objects.create(owner=user, name="Push", started_at=timezone.now())
    le = LoggedExercise.objects.create(session=session, exercise=ex, order=0)
    LoggedSet.objects.create(logged_exercise=le, order=0, set_type="working",
                             reps=5, weight=100, is_pr=True)

    # Protocols: a dose today.
    comp = Compound.objects.create(name="Test E")
    DoseLog.objects.create(owner=user, compound=comp, taken_at=timezone.now(),
                           amount=125, unit="mg")

    data = api.get("/api/v1/dashboard/today/").json()
    assert data["nutrition"]["has_target"] is True
    assert data["nutrition"]["calories"] == "330.000"
    assert data["workout"]["prs"] == 1
    assert data["workout"]["count"] == 1
    assert len(data["doses"]) == 1
    assert data["doses"][0]["item"] == "Test E"


def test_weekly_checkin_aggregates(api, user):
    end = date.today()
    # Two check-ins with bodyweight + scores.
    CheckIn.objects.create(owner=user, date=end - timedelta(days=5), bodyweight=85,
                           energy=4, sleep=3, mood=4, motivation=5, soreness=2)
    CheckIn.objects.create(owner=user, date=end, bodyweight=84,
                           energy=5, sleep=4, mood=5, motivation=5, soreness=1)
    # A session in-window.
    WorkoutSession.objects.create(owner=user, name="Pull",
                                  started_at=timezone.now() - timedelta(days=1))

    data = api.get("/api/v1/checkin/weekly/").json()
    assert data["check_ins"] == 2
    # Bodyweight trend 85 → 84.
    assert data["bodyweight"]["first"] == 85.0
    assert data["bodyweight"]["last"] == 84.0
    assert data["bodyweight"]["delta"] == -1.0
    # Subjective energy mean (4,5) = 4.5.
    assert data["subjective"]["energy"] == 4.5
    assert data["training"]["sessions"] == 1


def test_weekly_checkin_owner_isolation(api, other):
    # Another user's check-ins must not leak into my report.
    CheckIn.objects.create(owner=other, date=date.today(), bodyweight=100, energy=1)
    data = api.get("/api/v1/checkin/weekly/").json()
    assert data["check_ins"] == 0
    assert data["bodyweight"] is None


def test_weekly_checkin_batches_nutrition(django_assert_max_num_queries, user):
    """Weekly check-in must batch nutrition (one entries + one supplement query),
    not call daily_summary once per day."""
    from apps.core.services import weekly_checkin
    from apps.nutrition.models import DiaryEntry

    end = date.today()
    energy = Nutrient.objects.create(
        name="Calories", slug="energy", category="energy", unit="kcal", is_energy=True
    )
    Nutrient.objects.create(name="Protein", slug="protein", category="macro", unit="g")
    chicken = Food.objects.create(name="Chicken", source="seed")
    FoodNutrient.objects.create(food=chicken, nutrient=energy, amount_per_100g=165)
    for i in range(7):
        DiaryEntry.objects.create(
            owner=user, date=end - timedelta(days=i), food=chicken, quantity=200
        )
    with django_assert_max_num_queries(18):
        data = weekly_checkin(user, end)
    assert data["nutrition"]["days_logged"] == 7


def test_dashboard_uses_light_headline(django_assert_max_num_queries, user):
    """Dashboard headline must stay correct on the light (non per-nutrient) path."""
    from apps.core.services import dashboard_today
    from apps.nutrition.models import DiaryEntry

    energy = Nutrient.objects.create(
        name="Calories", slug="energy", category="energy", unit="kcal", is_energy=True
    )
    Nutrient.objects.create(name="Protein", slug="protein", category="macro", unit="g")
    chicken = Food.objects.create(name="Chicken", source="seed")
    FoodNutrient.objects.create(food=chicken, nutrient=energy, amount_per_100g=165)
    DiaryEntry.objects.create(owner=user, date=date.today(), food=chicken, quantity=200)
    with django_assert_max_num_queries(12):
        data = dashboard_today(user, date.today())
    assert data["nutrition"]["calories"] == "330.000"
