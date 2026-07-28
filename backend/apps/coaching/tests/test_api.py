"""Access-control matrix for the coaching layer — the security-critical surface.

The contract: a coach can READ a client's data only via an *active* link (the
X-Acting-Client header). For WRITES the coach may only touch the client's
*prescriptions* (phases, nutrition targets, programs, protocols) and only when
the link grants `can_edit_prescriptions`; logged data is never writable. A header
that isn't authorised is a hard 403, never a silent fall back to the coach's own data.
"""
from datetime import date

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.coaching.models import CoachClientLink, LinkStatus
from apps.core.models import Phase
from apps.diary.models import CheckIn

pytestmark = pytest.mark.django_db


@pytest.fixture
def coach():
    return User.objects.create_user(email="coach@x.com", password="x", is_coach=True)


@pytest.fixture
def client_user():
    u = User.objects.create_user(email="client@x.com", password="x")
    # Profile is auto-created by a signal; just set what body_analysis needs.
    u.profile.height_cm = 180
    u.profile.save(update_fields=["height_cm"])
    Phase.objects.create(owner=u, name="Client Prep", start_date=date(2026, 1, 1))
    CheckIn.objects.create(owner=u, date=date(2026, 1, 2), bodyweight=80)
    return u


@pytest.fixture
def outsider():
    return User.objects.create_user(email="outsider@x.com", password="x")


def api(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


def link(coach, client_user, status=LinkStatus.ACTIVE):
    return CoachClientLink.objects.create(coach=coach, client=client_user, status=status)


def rows(res):
    """List payload, tolerating DRF pagination ({results: [...]}) or a bare list."""
    j = res.json()
    return j["results"] if isinstance(j, dict) and "results" in j else j


# --- the effective-owner header on the read surface ---------------------------

def test_active_link_coach_reads_client_data(coach, client_user):
    link(coach, client_user)
    c = api(coach)
    res = c.get("/api/v1/phases/", HTTP_X_ACTING_CLIENT=str(client_user.id))
    assert res.status_code == 200
    assert [p["name"] for p in rows(res)] == ["Client Prep"]  # client's phase, not coach's

    dash = c.get("/api/v1/dashboard/today/", HTTP_X_ACTING_CLIENT=str(client_user.id))
    assert dash.status_code == 200
    assert dash.json()["phase"]["name"] == "Client Prep"


@pytest.mark.parametrize("status", [LinkStatus.PENDING, LinkStatus.DECLINED, LinkStatus.REVOKED])
def test_inactive_link_forbidden(coach, client_user, status):
    link(coach, client_user, status=status)
    res = api(coach).get("/api/v1/phases/", HTTP_X_ACTING_CLIENT=str(client_user.id))
    assert res.status_code == 403


def test_no_link_forbidden(coach, client_user):
    res = api(coach).get("/api/v1/phases/", HTTP_X_ACTING_CLIENT=str(client_user.id))
    assert res.status_code == 403


def test_non_coach_forbidden_even_with_link(outsider, client_user):
    # A link whose "coach" is not flagged is_coach must still be rejected.
    CoachClientLink.objects.create(coach=outsider, client=client_user, status=LinkStatus.ACTIVE)
    res = api(outsider).get("/api/v1/phases/", HTTP_X_ACTING_CLIENT=str(client_user.id))
    assert res.status_code == 403


def test_header_absent_is_self_scoped(coach, client_user):
    link(coach, client_user)
    res = api(coach).get("/api/v1/phases/")  # no header → coach's own (empty)
    assert res.status_code == 200 and rows(res) == []


def test_write_to_logged_data_ignores_header(coach, client_user):
    """A POST to LOGGED data with the header writes to the coach, never the client —
    coaches may only write prescriptions (see the prescription tests below)."""
    link(coach, client_user)
    res = api(coach).post(
        "/api/v1/diary/check-ins/",
        {"date": "2026-05-01", "bodyweight": 70},
        format="json",
        HTTP_X_ACTING_CLIENT=str(client_user.id),
    )
    assert res.status_code == 201
    assert not CheckIn.objects.filter(owner=client_user, date=date(2026, 5, 1)).exists()
    assert CheckIn.objects.filter(owner=coach, date=date(2026, 5, 1)).exists()


# --- Stage 2: a coach writes a client's PRESCRIPTIONS -------------------------

def test_coach_edits_client_phase(coach, client_user):
    link(coach, client_user)  # can_edit_prescriptions defaults to True
    res = api(coach).post(
        "/api/v1/phases/",
        {"name": "Coach Block", "start_date": "2026-02-01"},
        format="json",
        HTTP_X_ACTING_CLIENT=str(client_user.id),
    )
    assert res.status_code == 201
    assert Phase.objects.filter(owner=client_user, name="Coach Block").exists()
    assert not Phase.objects.filter(owner=coach, name="Coach Block").exists()


def test_coach_sets_client_nutrition_target(coach, client_user):
    from apps.nutrition.models import NutritionTarget

    link(coach, client_user)
    res = api(coach).post(
        "/api/v1/nutrition/targets/",
        {"name": "Cut", "calories": "2500"},
        format="json",
        HTTP_X_ACTING_CLIENT=str(client_user.id),
    )
    assert res.status_code == 201, res.content
    assert NutritionTarget.objects.filter(owner=client_user, name="Cut").exists()


def test_read_only_coach_can_read_not_write(coach, client_user):
    CoachClientLink.objects.create(
        coach=coach, client=client_user, status=LinkStatus.ACTIVE,
        can_edit_prescriptions=False,
    )
    c = api(coach)
    assert c.get("/api/v1/phases/", HTTP_X_ACTING_CLIENT=str(client_user.id)).status_code == 200
    res = c.post(
        "/api/v1/phases/", {"name": "Nope", "start_date": "2026-02-01"},
        format="json", HTTP_X_ACTING_CLIENT=str(client_user.id),
    )
    assert res.status_code == 403
    assert not Phase.objects.filter(name="Nope").exists()


def test_client_toggles_write_permission(coach, client_user):
    cl = link(coach, client_user)
    resp = api(client_user).post(
        f"/api/v1/coaching/links/{cl.id}/permission/",
        {"can_edit_prescriptions": False}, format="json",
    )
    assert resp.status_code == 200 and resp.json()["can_edit_prescriptions"] is False
    res = api(coach).post(
        "/api/v1/phases/", {"name": "X", "start_date": "2026-02-01"},
        format="json", HTTP_X_ACTING_CLIENT=str(client_user.id),
    )
    assert res.status_code == 403


def test_only_client_toggles_permission(coach, client_user):
    cl = link(coach, client_user)
    # the coach cannot change their own edit permission (not the link's client)
    res = api(coach).post(
        f"/api/v1/coaching/links/{cl.id}/permission/",
        {"can_edit_prescriptions": False}, format="json",
    )
    assert res.status_code == 404


# --- coach builds a program / protocol from scratch (full nested chain) -------

def test_coach_builds_program_chain(coach, client_user):
    from apps.training.models import Exercise, Program, TrainingDay

    link(coach, client_user)
    ex = Exercise.objects.create(name="Bench")  # global exercise (owner=None)
    c = api(coach)
    h = {"HTTP_X_ACTING_CLIENT": str(client_user.id)}

    prog = c.post("/api/v1/training/programs/", {"name": "Coach Prog"}, format="json", **h)
    assert prog.status_code == 201, prog.content
    pid = prog.json()["id"]
    assert Program.objects.get(id=pid).owner_id == client_user.id

    day = c.post(
        "/api/v1/training/training-days/",
        {"program": pid, "name": "Push", "order": 0}, format="json", **h,
    )
    assert day.status_code == 201, day.content
    did = day.json()["id"]
    assert TrainingDay.objects.get(id=did).program.owner_id == client_user.id

    slot = c.post(
        "/api/v1/training/exercise-slots/",
        {"day": did, "exercise": ex.id, "order": 0}, format="json", **h,
    )
    assert slot.status_code == 201, slot.content
    sid = slot.json()["id"]

    ps = c.post(
        "/api/v1/training/planned-sets/",
        {"slot": sid, "order": 0, "set_type": "working"}, format="json", **h,
    )
    assert ps.status_code == 201, ps.content


def test_coach_builds_protocol_chain(coach, client_user):
    from apps.protocols.models import Compound, Protocol, ProtocolItem

    link(coach, client_user)
    cmp = Compound.objects.create(name="Test E", default_unit="mg", half_life_hours="168")
    c = api(coach)
    h = {"HTTP_X_ACTING_CLIENT": str(client_user.id)}

    proto = c.post("/api/v1/protocols/protocols/", {"name": "Off-season"}, format="json", **h)
    assert proto.status_code == 201, proto.content
    pid = proto.json()["id"]
    assert Protocol.objects.get(id=pid).owner_id == client_user.id

    item = c.post(
        "/api/v1/protocols/protocol-items/",
        {"protocol": pid, "compound": cmp.id, "dose_amount": "250",
         "dose_unit": "mg", "frequency": "daily"},
        format="json", **h,
    )
    assert item.status_code == 201, item.content
    assert ProtocolItem.objects.get(id=item.json()["id"]).protocol.owner_id == client_user.id


def test_read_only_coach_cannot_build(coach, client_user):
    CoachClientLink.objects.create(
        coach=coach, client=client_user, status=LinkStatus.ACTIVE,
        can_edit_prescriptions=False,
    )
    res = api(coach).post(
        "/api/v1/training/programs/", {"name": "X"},
        format="json", HTTP_X_ACTING_CLIENT=str(client_user.id),
    )
    assert res.status_code == 403


def test_coach_views_client_analysis_and_training(coach, client_user):
    """The 'view as client' drill-ins read the client's Analysis + Training data."""
    from django.utils import timezone

    from apps.training.models import WorkoutSession

    link(coach, client_user)
    WorkoutSession.objects.create(owner=client_user, name="Push", started_at=timezone.now())
    c = api(coach)
    h = {"HTTP_X_ACTING_CLIENT": str(client_user.id)}

    assert c.get("/api/v1/analysis/body/", **h).status_code == 200
    sessions = c.get("/api/v1/training/workout-sessions/", **h)
    assert sessions.status_code == 200
    assert any(s["name"] == "Push" for s in rows(sessions))


# --- invite / accept / revoke lifecycle --------------------------------------

def test_invite_lifecycle(coach, client_user):
    cc = api(coach)
    # invite by email
    inv = cc.post("/api/v1/coaching/invites/", {"email": client_user.email}, format="json")
    assert inv.status_code == 201
    link_id = inv.json()["id"]
    assert inv.json()["status"] == LinkStatus.PENDING
    # not yet a client; header access denied
    assert cc.get("/api/v1/phases/", HTTP_X_ACTING_CLIENT=str(client_user.id)).status_code == 403

    # client sees + accepts
    clc = api(client_user)
    received = clc.get("/api/v1/coaching/invites/").json()["received"]
    assert [r["id"] for r in received] == [link_id]
    acc = clc.post(f"/api/v1/coaching/invites/{link_id}/respond/", {"accept": True}, format="json")
    assert acc.status_code == 200 and acc.json()["status"] == LinkStatus.ACTIVE

    # now an active client + readable
    clients = cc.get("/api/v1/coaching/clients/").json()
    assert [c["client_id"] for c in clients] == [client_user.id]
    assert cc.get("/api/v1/phases/", HTTP_X_ACTING_CLIENT=str(client_user.id)).status_code == 200

    # revoke kills access
    cc.post(f"/api/v1/coaching/links/{link_id}/revoke/")
    assert cc.get("/api/v1/coaching/clients/").json() == []
    assert cc.get("/api/v1/phases/", HTTP_X_ACTING_CLIENT=str(client_user.id)).status_code == 403


def test_invite_requires_coach(outsider, client_user):
    res = api(outsider).post(
        "/api/v1/coaching/invites/", {"email": client_user.email}, format="json"
    )
    assert res.status_code == 403


def test_invite_unknown_email(coach):
    res = api(coach).post("/api/v1/coaching/invites/", {"email": "nobody@x.com"}, format="json")
    assert res.status_code == 400


def test_client_list_requires_coach(outsider):
    assert api(outsider).get("/api/v1/coaching/clients/").status_code == 403


def test_overview_requires_active_link(coach, client_user):
    assert api(coach).get(f"/api/v1/coaching/clients/{client_user.id}/overview/").status_code == 403
    link(coach, client_user)
    res = api(coach).get(f"/api/v1/coaching/clients/{client_user.id}/overview/")
    assert res.status_code == 200
    body = res.json()
    assert body["client"]["id"] == client_user.id
    assert "dashboard" in body and "body" in body and "weekly_check_in" in body


# --- Stage 3: a coach curates a client's reference LIBRARY --------------------
# Exercises / compounds / supplements / foods are global-or-owned. A coach with
# edit access may add (and edit/delete) the *client's* own custom items so they
# show up in that client's builders; the shared global seeds stay read-only.

def test_coach_adds_custom_exercise_to_client_library(coach, client_user):
    from apps.training.models import Exercise

    link(coach, client_user)
    res = api(coach).post(
        "/api/v1/training/exercises/",
        {"name": "Coach Curl"},
        format="json",
        HTTP_X_ACTING_CLIENT=str(client_user.id),
    )
    assert res.status_code == 201, res.content
    assert Exercise.objects.filter(owner=client_user, name="Coach Curl").exists()
    assert not Exercise.objects.filter(owner=coach, name="Coach Curl").exists()


def test_coach_adds_custom_compound_to_client_library(coach, client_user):
    from apps.protocols.models import Compound

    link(coach, client_user)
    res = api(coach).post(
        "/api/v1/protocols/compounds/",
        {"name": "Coach Compound", "compound_class": "anabolic",
         "default_unit": "mg", "default_route": "im"},
        format="json",
        HTTP_X_ACTING_CLIENT=str(client_user.id),
    )
    assert res.status_code == 201, res.content
    assert Compound.objects.filter(owner=client_user, name="Coach Compound").exists()


def test_coach_cannot_edit_or_delete_global_library_item(coach, client_user):
    """Global seeds (owner is null) are read-only from the console — never mutate
    shared reference data for everyone."""
    from apps.training.models import Exercise

    link(coach, client_user)
    glob = Exercise.objects.create(name="Global Bench", owner=None)
    h = {"HTTP_X_ACTING_CLIENT": str(client_user.id)}
    patched = api(coach).patch(
        f"/api/v1/training/exercises/{glob.id}/",
        {"name": "Hijacked"}, format="json", **h,
    )
    assert patched.status_code == 403
    deleted = api(coach).delete(f"/api/v1/training/exercises/{glob.id}/", **h)
    assert deleted.status_code == 403
    glob.refresh_from_db()
    assert glob.name == "Global Bench" and glob.owner_id is None


def test_readonly_coach_cannot_add_library_item(coach, client_user):
    from apps.training.models import Exercise

    CoachClientLink.objects.create(
        coach=coach, client=client_user, status=LinkStatus.ACTIVE,
        can_edit_prescriptions=False,
    )
    res = api(coach).post(
        "/api/v1/training/exercises/",
        {"name": "Nope Exercise"},
        format="json",
        HTTP_X_ACTING_CLIENT=str(client_user.id),
    )
    assert res.status_code == 403
    assert not Exercise.objects.filter(name="Nope Exercise").exists()


# --- Meal plans: a coach authors a full-day plan the client can import ---------

def test_coach_authors_client_meal_plan(coach, client_user):
    from apps.nutrition.models import Food, MealPlan

    link(coach, client_user)
    h = {"HTTP_X_ACTING_CLIENT": str(client_user.id)}
    food = Food.objects.create(name="Oats", owner=None, unit="g", source="custom")

    r = api(coach).post(
        "/api/v1/nutrition/meal-plans/", {"name": "Cutting day"}, format="json", **h
    )
    assert r.status_code == 201, r.content
    plan_id = r.json()["id"]
    assert MealPlan.objects.filter(owner=client_user, name="Cutting day").exists()
    assert not MealPlan.objects.filter(owner=coach).exists()

    m = api(coach).post(
        "/api/v1/nutrition/meal-plan-meals/",
        {"plan": plan_id, "name": "Breakfast", "order": 0}, format="json", **h,
    )
    assert m.status_code == 201, m.content
    meal_id = m.json()["id"]

    it = api(coach).post(
        "/api/v1/nutrition/meal-plan-items/",
        {"meal": meal_id, "food": food.id, "quantity": "80"}, format="json", **h,
    )
    assert it.status_code == 201, it.content

    got = api(coach).get(f"/api/v1/nutrition/meal-plans/{plan_id}/", **h).json()
    assert got["meals"][0]["name"] == "Breakfast"
    assert got["meals"][0]["items"][0]["food"] == food.id


def test_readonly_coach_cannot_author_meal_plan(coach, client_user):
    CoachClientLink.objects.create(
        coach=coach, client=client_user, status=LinkStatus.ACTIVE,
        can_edit_prescriptions=False,
    )
    r = api(coach).post(
        "/api/v1/nutrition/meal-plans/", {"name": "Nope"}, format="json",
        HTTP_X_ACTING_CLIENT=str(client_user.id),
    )
    assert r.status_code == 403


def test_client_applies_meal_plan_to_diary(client_user):
    from apps.nutrition.models import (
        DiaryEntry,
        Food,
        Meal,
        MealPlan,
        MealPlanItem,
        MealPlanMeal,
    )

    food = Food.objects.create(name="Rice", owner=None, unit="g", source="custom")
    plan = MealPlan.objects.create(owner=client_user, name="Day A")
    meal = MealPlanMeal.objects.create(plan=plan, name="Lunch", order=0)
    MealPlanItem.objects.create(meal=meal, food=food, quantity=150)

    r = api(client_user).post(
        f"/api/v1/nutrition/meal-plans/{plan.id}/apply/",
        {"date": "2026-05-10"}, format="json",
    )
    assert r.status_code == 201, r.content
    assert r.json() == {"meals": 1, "entries": 1}
    assert Meal.objects.filter(owner=client_user, date="2026-05-10", name="Lunch").exists()
    assert DiaryEntry.objects.filter(owner=client_user, date="2026-05-10", food=food).exists()


# --- Check-in review loop -----------------------------------------------------

def test_coach_review_queue_lists_client_checkins(coach, client_user, outsider):
    from apps.diary.models import CheckIn

    link(coach, client_user)
    # an unrelated user's check-in must NOT appear
    CheckIn.objects.create(owner=outsider, date=date(2026, 3, 1), bodyweight=90)
    CheckIn.objects.create(
        owner=client_user, date=date(2026, 3, 2), bodyweight=80, notes="rough week"
    )

    res = api(coach).get("/api/v1/coaching/check-ins/")
    assert res.status_code == 200
    rows = res.json()
    owners = {r["client_id"] for r in rows}
    assert client_user.id in owners and outsider.id not in owners
    row = next(r for r in rows if r["client_id"] == client_user.id)
    assert row["reviewed"] is False and row["has_notes"] is True


def test_non_coach_has_no_review_queue(client_user):
    assert api(client_user).get("/api/v1/coaching/check-ins/").status_code == 403


def test_coach_reviews_checkin_and_comments(coach, client_user):
    from apps.diary.models import CheckIn

    link(coach, client_user)
    ci = CheckIn.objects.create(owner=client_user, date=date(2026, 3, 3), bodyweight=79, energy=4)

    detail = api(coach).get(f"/api/v1/coaching/check-ins/{ci.id}/")
    assert detail.status_code == 200
    body = detail.json()
    assert body["check_in"]["bodyweight"] == 79.0
    assert body["client"]["id"] == client_user.id
    assert "weekly" in body and body["comments"] == []

    posted = api(coach).post(
        f"/api/v1/coaching/check-ins/{ci.id}/comments/",
        {"body": "Great adherence — hold calories, add 10 min cardio."}, format="json",
    )
    assert posted.status_code == 201
    assert posted.json()["by_coach"] is True

    # now the queue shows it reviewed, and the client can read the coach's feedback
    row = next(r for r in api(coach).get("/api/v1/coaching/check-ins/").json() if r["id"] == ci.id)
    assert row["reviewed"] is True and row["comment_count"] == 1
    client_view = api(client_user).get(f"/api/v1/coaching/check-ins/{ci.id}/").json()
    assert len(client_view["comments"]) == 1
    assert client_view["comments"][0]["by_coach"] is True


def test_outsider_cannot_review_or_comment(client_user, outsider):
    from apps.diary.models import CheckIn

    ci = CheckIn.objects.create(owner=client_user, date=date(2026, 3, 4), bodyweight=79)
    assert api(outsider).get(f"/api/v1/coaching/check-ins/{ci.id}/").status_code == 403
    assert (
        api(outsider)
        .post(f"/api/v1/coaching/check-ins/{ci.id}/comments/", {"body": "hi"}, format="json")
        .status_code
        == 403
    )


def test_client_can_reply_on_own_checkin(client_user):
    from apps.diary.models import CheckIn

    ci = CheckIn.objects.create(owner=client_user, date=date(2026, 3, 5), bodyweight=79)
    res = api(client_user).post(
        f"/api/v1/coaching/check-ins/{ci.id}/comments/", {"body": "Felt strong!"}, format="json",
    )
    assert res.status_code == 201 and res.json()["by_coach"] is False


# --- Templates: coach owns programs/protocols/meal-plans; applies them to clients ---

def test_coach_applies_program_template_to_client(coach, client_user):
    from apps.training.models import Exercise, ExerciseSlot, PlannedSet, Program, TrainingDay

    link(coach, client_user)
    # a template program owned by the coach (built with no acting header)
    ex = Exercise.objects.create(name="Bench", owner=None)
    tmpl = Program.objects.create(owner=coach, name="Upper/Lower", is_active=True)
    day = TrainingDay.objects.create(program=tmpl, name="Upper", order=0)
    slot = ExerciseSlot.objects.create(day=day, exercise=ex, order=0)
    PlannedSet.objects.create(
        slot=slot, set_type="working", target_reps_low=8, target_reps_high=12, order=0
    )

    res = api(coach).post(
        "/api/v1/coaching/templates/apply/",
        {"kind": "program", "id": tmpl.id, "client": client_user.id}, format="json",
    )
    assert res.status_code == 201, res.content

    copy = Program.objects.get(owner=client_user, name="Upper/Lower")
    assert copy.id != tmpl.id and copy.is_active is False
    assert copy.days.count() == 1
    cslot = copy.days.first().slots.first()
    assert cslot.exercise_id == ex.id and cslot.planned_sets.count() == 1
    # the coach's template is untouched
    assert Program.objects.filter(owner=coach, name="Upper/Lower").count() == 1


def test_coach_applies_meal_plan_template(coach, client_user):
    from apps.nutrition.models import Food, MealPlan, MealPlanItem, MealPlanMeal

    link(coach, client_user)
    food = Food.objects.create(name="Oats", owner=None, unit="g", source="custom")
    tmpl = MealPlan.objects.create(owner=coach, name="Cut day")
    meal = MealPlanMeal.objects.create(plan=tmpl, name="Breakfast", order=0)
    MealPlanItem.objects.create(meal=meal, food=food, quantity=80, order=0)

    res = api(coach).post(
        "/api/v1/coaching/templates/apply/",
        {"kind": "meal_plan", "id": tmpl.id, "client": client_user.id}, format="json",
    )
    assert res.status_code == 201, res.content
    copy = MealPlan.objects.get(owner=client_user, name="Cut day")
    assert copy.meals.first().items.first().food_id == food.id


def test_readonly_link_cannot_apply_template(coach, client_user):
    from apps.training.models import Program

    CoachClientLink.objects.create(
        coach=coach, client=client_user, status=LinkStatus.ACTIVE, can_edit_prescriptions=False,
    )
    tmpl = Program.objects.create(owner=coach, name="X")
    res = api(coach).post(
        "/api/v1/coaching/templates/apply/",
        {"kind": "program", "id": tmpl.id, "client": client_user.id}, format="json",
    )
    assert res.status_code == 403
    assert not Program.objects.filter(owner=client_user).exists()


def test_cannot_apply_another_coachs_template(coach, client_user, outsider):
    from apps.training.models import Program

    link(coach, client_user)
    foreign = Program.objects.create(owner=outsider, name="Not yours")
    res = api(coach).post(
        "/api/v1/coaching/templates/apply/",
        {"kind": "program", "id": foreign.id, "client": client_user.id}, format="json",
    )
    assert res.status_code == 404
