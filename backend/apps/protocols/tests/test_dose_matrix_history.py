"""The phase dose table preserves history across a protocol adjustment: a dropped
compound keeps its logged weeks (then reads `none`); a newly-introduced one only
appears from its week. Also covers the `protocol-in-force` endpoint."""
from datetime import datetime, time, timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.models import Phase, PhaseAdjustment
from apps.protocols.models import Compound, DoseLog, Protocol, ProtocolItem
from apps.protocols.services import phase_dose_matrix

pytestmark = pytest.mark.django_db

TODAY = timezone.now().date()


@pytest.fixture
def user():
    return User.objects.create_user(email="hist@example.com", password="x")


def _oral(user, name):
    return Compound.objects.create(
        owner=user, name=name, compound_class="other", default_unit="mg", default_route="oral"
    )


def _item(protocol, compound, dose="10"):
    return ProtocolItem.objects.create(
        protocol=protocol, compound=compound, dose_amount=dose, dose_unit="mg",
        route="oral", frequency="daily", times_of_day=["am"],
    )


def _log(user, compound, on):
    DoseLog.objects.create(
        owner=user, compound=compound,
        taken_at=timezone.make_aware(datetime.combine(on, time(9, 0))),
        amount="10", unit="mg", status="taken",
    )


def _row(matrix, name):
    return next(r for r in matrix["rows"] if r["name"] == name)


def test_matrix_preserves_history_across_adjustment(user):
    # Phase spans 2 past weeks + the current/next week.
    start = TODAY - timedelta(days=14)
    phase = Phase.objects.create(
        owner=user, name="Block", phase_type="bulk",
        start_date=start, end_date=TODAY + timedelta(days=7),
    )
    a = Protocol.objects.create(owner=user, name="A", is_active=False)
    b = Protocol.objects.create(owner=user, name="B", is_active=True)
    x = _oral(user, "Xandrol")  # only in A (dropped by the adjustment)
    y = _oral(user, "Yfenil")   # only in B (introduced by the adjustment)
    _item(a, x)
    _item(b, y)
    PhaseAdjustment.objects.create(phase=phase, effective_date=start, protocol=a)
    PhaseAdjustment.objects.create(phase=phase, effective_date=TODAY, protocol=b)

    _log(user, x, TODAY - timedelta(days=10))  # week 0 (A in force)
    _log(user, x, TODAY - timedelta(days=3))   # week 1 (A in force)
    _log(user, y, TODAY)                        # week 2 (B in force)

    m = phase_dose_matrix(user, phase, b)
    names = {r["name"] for r in m["rows"]}
    assert {"Xandrol", "Yfenil"} <= names  # both kept, not just the current protocol

    # Each week is labelled with the protocol in force; the adjustment is at week 2.
    assert [w["protocol"] for w in m["weeks"]] == ["A", "A", "B", "B"]

    xc = _row(m, "Xandrol")["cells"]
    yc = _row(m, "Yfenil")["cells"]
    # Dropped compound: logged in the early weeks, then nothing scheduled (and no dose
    # shown) after — it is not carried into the weeks the new protocol governs.
    assert xc[0]["taken_count"] == 1 and xc[1]["taken_count"] == 1
    assert xc[2]["scheduled"] == 0 and xc[2]["state"] == "none"
    assert xc[3]["scheduled"] == 0 and xc[3]["state"] == "none"
    assert xc[2]["daily_amount"] is None and xc[3]["daily_amount"] is None
    # New compound: not scheduled (no dose) before its week; logged now; planned ahead.
    assert yc[0]["scheduled"] == 0 and yc[1]["scheduled"] == 0
    assert yc[0]["daily_amount"] is None and yc[1]["daily_amount"] is None
    assert yc[2]["taken_count"] == 1
    assert yc[3]["scheduled"] > 0 and yc[3]["state"] == "planned"


def test_daily_dose_reflects_per_week_protocol(user):
    """A compound kept across the adjustment but at a different dose shows the dose in
    force *that* week — not the currently-active protocol's dose for every week."""
    start = TODAY - timedelta(days=14)
    phase = Phase.objects.create(
        owner=user, name="Block", phase_type="bulk",
        start_date=start, end_date=TODAY + timedelta(days=7),
    )
    a = Protocol.objects.create(owner=user, name="A", is_active=False)
    b = Protocol.objects.create(owner=user, name="B", is_active=True)
    shared = _oral(user, "Anavar")  # in both protocols; dose raised by the adjustment
    _item(a, shared, dose="10")
    _item(b, shared, dose="30")
    PhaseAdjustment.objects.create(phase=phase, effective_date=start, protocol=a)
    PhaseAdjustment.objects.create(phase=phase, effective_date=TODAY, protocol=b)

    cells = _row(phase_dose_matrix(user, phase, b), "Anavar")["cells"]
    assert float(cells[0]["daily_amount"]) == 10  # early weeks keep A's lower dose
    assert float(cells[1]["daily_amount"]) == 10
    assert float(cells[2]["daily_amount"]) == 30  # later weeks use B's raised dose
    assert float(cells[3]["daily_amount"]) == 30


def test_in_force_endpoint_returns_dated_protocol(user):
    start = TODAY - timedelta(days=14)
    phase = Phase.objects.create(owner=user, name="Block", phase_type="bulk", start_date=start)
    a = Protocol.objects.create(owner=user, name="A")
    b = Protocol.objects.create(owner=user, name="B", is_active=True)
    PhaseAdjustment.objects.create(phase=phase, effective_date=start, protocol=a)
    PhaseAdjustment.objects.create(phase=phase, effective_date=TODAY, protocol=b)

    c = APIClient()
    c.force_authenticate(user)
    yday = (TODAY - timedelta(days=1)).isoformat()
    assert c.get(f"/api/v1/protocols/in-force/?date={yday}").json()["name"] == "A"
    assert c.get(f"/api/v1/protocols/in-force/?date={TODAY.isoformat()}").json()["name"] == "B"
