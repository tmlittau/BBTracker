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


def _item(protocol, compound):
    return ProtocolItem.objects.create(
        protocol=protocol, compound=compound, dose_amount="10", dose_unit="mg",
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

    xc = _row(m, "Xandrol")["cells"]
    yc = _row(m, "Yfenil")["cells"]
    # Dropped compound: logged in the early weeks, then nothing scheduled after.
    assert xc[0]["taken_count"] == 1 and xc[1]["taken_count"] == 1
    assert xc[2]["scheduled"] == 0 and xc[2]["state"] == "none"
    assert xc[3]["scheduled"] == 0 and xc[3]["state"] == "none"
    # New compound: not scheduled before its week; logged now; planned in the future.
    assert yc[0]["scheduled"] == 0 and yc[1]["scheduled"] == 0
    assert yc[2]["taken_count"] == 1
    assert yc[3]["scheduled"] > 0 and yc[3]["state"] == "planned"


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
