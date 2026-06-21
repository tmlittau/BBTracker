"""Access-control matrix for the coaching layer — the security-critical surface.

The contract: a coach can READ a client's data only via an *active* link, only
on safe methods (the X-Acting-Client header), and never write it. A header that
isn't authorised is a hard 403, never a silent fall back to the coach's own data.
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


def test_write_ignores_header(coach, client_user):
    """A POST with the header writes to the coach, never the client (read-only stage)."""
    link(coach, client_user)
    res = api(coach).post(
        "/api/v1/phases/",
        {"name": "Sneaky", "start_date": "2026-03-01"},
        format="json",
        HTTP_X_ACTING_CLIENT=str(client_user.id),
    )
    assert res.status_code == 201
    assert not Phase.objects.filter(owner=client_user, name="Sneaky").exists()
    assert Phase.objects.filter(owner=coach, name="Sneaky").exists()


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
