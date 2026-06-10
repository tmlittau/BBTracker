
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.training.models import (
    Exercise,
    LoggedExercise,
    LoggedSet,
    Muscle,
    Program,
    WorkoutSession,
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
def bench(db):
    chest = Muscle.objects.create(name="Chest", slug="chest", group="chest")
    ex = Exercise.objects.create(name="Bench Press")  # global
    ex.primary_muscles.add(chest)
    return ex


def test_requires_auth():
    assert APIClient().get("/api/v1/training/exercises/").status_code in (401, 403)


def test_global_exercises_visible(api, bench):
    resp = api.get("/api/v1/training/exercises/")
    assert resp.status_code == 200
    names = [e["name"] for e in resp.json()["results"]]
    assert "Bench Press" in names


def test_exercise_search(api, bench):
    assert api.get("/api/v1/training/exercises/?q=bench").json()["count"] == 1
    assert api.get("/api/v1/training/exercises/?q=zzz").json()["count"] == 0


def test_custom_exercise_is_owned(api, user):
    resp = api.post("/api/v1/training/exercises/", {"name": "My Curl"}, format="json")
    assert resp.status_code == 201
    assert Exercise.objects.get(name="My Curl").owner == user


def test_cannot_edit_global_exercise(api, bench):
    resp = api.patch(
        f"/api/v1/training/exercises/{bench.id}/", {"name": "Hacked"}, format="json"
    )
    assert resp.status_code == 403
    bench.refresh_from_db()
    assert bench.name == "Bench Press"


def test_program_owner_isolation(api, user, other):
    mine = Program.objects.create(owner=user, name="PPL")
    theirs = Program.objects.create(owner=other, name="Theirs")

    listed = api.get("/api/v1/training/programs/").json()["results"]
    ids = {p["id"] for p in listed}
    assert mine.id in ids
    assert theirs.id not in ids

    # And cannot fetch the other user's program directly.
    assert api.get(f"/api/v1/training/programs/{theirs.id}/").status_code == 404


def test_cannot_attach_day_to_others_program(api, other):
    theirs = Program.objects.create(owner=other, name="Theirs")
    resp = api.post(
        "/api/v1/training/training-days/",
        {"program": theirs.id, "name": "Push", "order": 0},
        format="json",
    )
    assert resp.status_code == 403


def test_build_program_hierarchy(api, bench):
    pid = api.post("/api/v1/training/programs/", {"name": "PPL"}, format="json").json()["id"]
    did = api.post(
        "/api/v1/training/training-days/",
        {"program": pid, "name": "Push", "order": 0},
        format="json",
    ).json()["id"]
    sid = api.post(
        "/api/v1/training/exercise-slots/",
        {"day": did, "exercise": bench.id, "order": 0},
        format="json",
    ).json()["id"]
    ps = api.post(
        "/api/v1/training/planned-sets/",
        {"slot": sid, "order": 0, "set_type": "working",
         "target_reps_low": 5, "target_reps_high": 8},
        format="json",
    )
    assert ps.status_code == 201

    # Nested read returns the whole tree.
    program = api.get(f"/api/v1/training/programs/{pid}/").json()
    assert program["days"][0]["slots"][0]["planned_sets"][0]["target_reps_low"] == 5


def test_activate_program_is_exclusive(api):
    p1 = api.post("/api/v1/training/programs/", {"name": "A"}, format="json").json()["id"]
    p2 = api.post("/api/v1/training/programs/", {"name": "B"}, format="json").json()["id"]
    api.post(f"/api/v1/training/programs/{p1}/activate/")
    api.post(f"/api/v1/training/programs/{p2}/activate/")
    assert Program.objects.get(id=p1).is_active is False
    assert Program.objects.get(id=p2).is_active is True


def test_log_workout_and_pr_detection(api, user, bench):
    started = timezone.now().isoformat()
    sid = api.post(
        "/api/v1/training/workout-sessions/",
        {"name": "Push", "started_at": started},
        format="json",
    ).json()["id"]
    leid = api.post(
        "/api/v1/training/logged-exercises/",
        {"session": sid, "exercise": bench.id, "order": 0},
        format="json",
    ).json()["id"]

    # First working set → PR, with computed e1RM.
    s1 = api.post(
        "/api/v1/training/logged-sets/",
        {"logged_exercise": leid, "order": 0, "set_type": "working",
         "reps": 5, "weight": "100.00"},
        format="json",
    ).json()
    assert s1["is_pr"] is True
    assert s1["e1rm"] is not None

    # Heavier set → new PR.
    s2 = api.post(
        "/api/v1/training/logged-sets/",
        {"logged_exercise": leid, "order": 1, "set_type": "working",
         "reps": 5, "weight": "110.00"},
        format="json",
    ).json()
    assert s2["is_pr"] is True
    assert float(s2["e1rm"]) > float(s1["e1rm"])

    # Lighter set → not a PR.
    s3 = api.post(
        "/api/v1/training/logged-sets/",
        {"logged_exercise": leid, "order": 2, "set_type": "working",
         "reps": 3, "weight": "80.00"},
        format="json",
    ).json()
    assert s3["is_pr"] is False


def test_exercise_history_and_volume(api, user, bench):
    session = WorkoutSession.objects.create(
        owner=user, name="Push", started_at=timezone.now()
    )
    le = LoggedExercise.objects.create(session=session, exercise=bench, order=0)
    from apps.training.services import recompute_set_metrics

    s = LoggedSet(logged_exercise=le, order=0, set_type="working", reps=5, weight=100)
    recompute_set_metrics(s)
    s.save()

    hist = api.get(f"/api/v1/training/exercises/{bench.id}/history/").json()
    assert len(hist) == 1
    assert hist[0]["top_weight"] == "100.00"

    vol = api.get("/api/v1/training/volume/?days=30").json()
    chest_row = next(r for r in vol if r["muscle"] == "Chest")
    assert chest_row["sets"] == 1
    assert chest_row["tonnage"] == "500.00"


def test_session_owner_isolation(api, other):
    theirs = WorkoutSession.objects.create(
        owner=other, name="Theirs", started_at=timezone.now()
    )
    assert api.get(f"/api/v1/training/workout-sessions/{theirs.id}/").status_code == 404


def test_delete_own_session(api, user):
    """A workout (e.g. started by accident) can be deleted from history."""
    s = WorkoutSession.objects.create(owner=user, name="Oops", started_at=timezone.now())
    assert api.delete(f"/api/v1/training/workout-sessions/{s.id}/").status_code == 204
    assert api.get(f"/api/v1/training/workout-sessions/{s.id}/").status_code == 404


def test_cannot_delete_others_session(api, other):
    theirs = WorkoutSession.objects.create(
        owner=other, name="Theirs", started_at=timezone.now()
    )
    # The owner-scoped queryset hides another user's session → 404, and it survives.
    assert api.delete(f"/api/v1/training/workout-sessions/{theirs.id}/").status_code == 404
    assert WorkoutSession.objects.filter(id=theirs.id).exists()


def test_session_date_range_filter(api, user):
    now = timezone.now()
    WorkoutSession.objects.create(owner=user, name="Recent", started_at=now)
    WorkoutSession.objects.create(owner=user, name="Old", started_at=now - timedelta(days=20))
    assert len(api.get("/api/v1/training/workout-sessions/").json()["results"]) == 2
    frm = (now - timedelta(days=7)).date().isoformat()
    res = api.get(f"/api/v1/training/workout-sessions/?from={frm}").json()["results"]
    assert [s["name"] for s in res] == ["Recent"]
    to = (now - timedelta(days=10)).date().isoformat()
    res2 = api.get(f"/api/v1/training/workout-sessions/?to={to}").json()["results"]
    assert [s["name"] for s in res2] == ["Old"]
