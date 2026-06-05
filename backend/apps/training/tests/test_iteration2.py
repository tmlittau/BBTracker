"""Iteration-2 training features: start-from-day, pending-set logging,
prune-on-finish, and the reorder action."""
import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.training.models import (
    Exercise,
    ExerciseSlot,
    LoggedSet,
    PlannedSet,
    Program,
    TrainingDay,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def user(db):
    return User.objects.create_user(email="m1@example.com", password="x")


@pytest.fixture
def api(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def bench(db):
    return Exercise.objects.create(name="Bench Press")


@pytest.fixture
def squat(db):
    return Exercise.objects.create(name="Squat")


def _day_with_sets(user, bench):
    program = Program.objects.create(owner=user, name="PPL")
    day = TrainingDay.objects.create(program=program, name="Push", order=0)
    slot = ExerciseSlot.objects.create(day=day, exercise=bench, order=0)
    PlannedSet.objects.create(slot=slot, order=0, set_type="warmup", rest_seconds=None)
    PlannedSet.objects.create(slot=slot, order=1, set_type="working", rest_seconds=200)
    return day


def test_start_from_day_instantiates_pending_sets(api, user, bench):
    day = _day_with_sets(user, bench)
    resp = api.post(
        "/api/v1/training/workout-sessions/start_from_day/", {"day": day.id}, format="json"
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["day"] == day.id and data["name"] == "Push"
    sets = data["logged_exercises"][0]["sets"]
    assert len(sets) == 2
    assert all(s["is_completed"] is False for s in sets)
    assert all(s["reps"] is None and s["weight"] is None for s in sets)
    warmup = next(s for s in sets if s["set_type"] == "warmup")
    working = next(s for s in sets if s["set_type"] == "working")
    assert warmup["rest_seconds"] == 45  # defaulted by set type
    assert working["rest_seconds"] == 200  # explicit plan value preserved


def test_start_from_day_rejects_others_day(api, bench):
    other = User.objects.create_user(email="x@example.com", password="x")
    program = Program.objects.create(owner=other, name="Theirs")
    day = TrainingDay.objects.create(program=program, name="Push", order=0)
    resp = api.post(
        "/api/v1/training/workout-sessions/start_from_day/", {"day": day.id}, format="json"
    )
    assert resp.status_code == 403


def test_logging_pending_set_completes_it(api, user, bench):
    day = _day_with_sets(user, bench)
    data = api.post(
        "/api/v1/training/workout-sessions/start_from_day/", {"day": day.id}, format="json"
    ).json()
    working = next(s for s in data["logged_exercises"][0]["sets"] if s["set_type"] == "working")
    resp = api.patch(
        f"/api/v1/training/logged-sets/{working['id']}/",
        {"reps": 5, "weight": "100.00", "is_completed": True},
        format="json",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_completed"] is True
    assert body["e1rm"] is not None  # recompute ran on completion


def test_finish_drop_incomplete_prunes(api, user, bench):
    day = _day_with_sets(user, bench)
    sess = api.post(
        "/api/v1/training/workout-sessions/start_from_day/", {"day": day.id}, format="json"
    ).json()
    sid = sess["id"]
    working = next(s for s in sess["logged_exercises"][0]["sets"] if s["set_type"] == "working")
    api.patch(
        f"/api/v1/training/logged-sets/{working['id']}/",
        {"reps": 5, "weight": "100", "is_completed": True},
        format="json",
    )
    resp = api.post(
        f"/api/v1/training/workout-sessions/{sid}/finish/", {"drop_incomplete": True}, format="json"
    )
    assert resp.status_code == 200
    remaining = LoggedSet.objects.filter(logged_exercise__session_id=sid)
    assert remaining.count() == 1
    assert remaining.first().is_completed is True


def test_reorder_slots_persists_and_isolates(api, user, bench, squat):
    program = Program.objects.create(owner=user, name="PPL")
    day = TrainingDay.objects.create(program=program, name="Push", order=0)
    s1 = ExerciseSlot.objects.create(day=day, exercise=bench, order=0)
    s2 = ExerciseSlot.objects.create(day=day, exercise=squat, order=1)
    resp = api.post(
        "/api/v1/training/exercise-slots/reorder/",
        [{"id": s1.id, "order": 1}, {"id": s2.id, "order": 0}],
        format="json",
    )
    assert resp.status_code == 200 and resp.json()["updated"] == 2
    s1.refresh_from_db()
    s2.refresh_from_db()
    assert s1.order == 1 and s2.order == 0

    # Another user's slot is silently ignored (not in the owner-scoped queryset).
    other = User.objects.create_user(email="y@example.com", password="x")
    op = Program.objects.create(owner=other, name="Theirs")
    od = TrainingDay.objects.create(program=op, name="X", order=0)
    os_ = ExerciseSlot.objects.create(day=od, exercise=bench, order=0)
    resp = api.post(
        "/api/v1/training/exercise-slots/reorder/", [{"id": os_.id, "order": 5}], format="json"
    )
    assert resp.status_code == 200 and resp.json()["updated"] == 0
    os_.refresh_from_db()
    assert os_.order == 0
