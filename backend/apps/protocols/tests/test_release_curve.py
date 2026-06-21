from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.protocols.models import Compound, DoseLog, Protocol, ProtocolItem
from apps.protocols.services import protocol_release_curves

pytestmark = pytest.mark.django_db


def test_release_rate_accumulates_with_steady_dosing(db):
    """Steady daily dosing makes the active serum-level curve RISE toward a steady
    state, not decrease.

    Regression for a reported 'no matter how often I log it still decreases':
    the curve is correct — it's sparse / no-schedule dosing that decays after the
    last logged dose.
    """
    u = User.objects.create_user(email="rel@example.com", password="x")
    c = Compound.objects.create(
        name="Test E", compound_class="anabolic", default_unit="mg", default_route="im",
        half_life_hours="168", ester="enanthate", active_fraction="0.700",
    )
    start = timezone.now().date() - timedelta(days=20)
    p = Protocol.objects.create(owner=u, name="Cyc", started_on=start, is_active=True)
    ProtocolItem.objects.create(
        protocol=p, compound=c, dose_amount=50, dose_unit="mg", route="im", frequency="daily"
    )
    for d in range(20, -1, -1):
        DoseLog.objects.create(
            owner=u, compound=c, taken_at=timezone.now() - timedelta(days=d),
            amount=50, unit="mg", route="im",
        )
    data = protocol_release_curves(u, p, horizon_days=14)
    assert data["unit"] == "relative"
    logged = [pt["rate"] for pt in data["compounds"][0]["points"] if not pt["projected"]]
    # Climbs over the dosing period toward a steady-state level (still approaching
    # it at day 20). The point: more doses → higher, not lower.
    assert logged[1] < logged[len(logged) // 2] < logged[-1]
    assert logged[-1] > 2 * logged[2]


def test_phase_compound_levels_from_actual_doses(db):
    """Phase levels are built from logged doses within [start, end]; doses outside
    the window don't add new compounds, and the curve spans the phase."""

    from apps.protocols.services import phase_compound_levels

    u = User.objects.create_user(email="ph@example.com", password="x")
    test_e = Compound.objects.create(
        name="Test E", compound_class="anabolic", default_unit="mg", default_route="im",
        half_life_hours="168", active_fraction="0.700",
    )
    deca = Compound.objects.create(
        name="Deca", compound_class="anabolic", default_unit="mg", default_route="im",
        half_life_hours="144", active_fraction="0.640",
    )
    start = timezone.now().date() - timedelta(days=40)
    end = timezone.now().date() - timedelta(days=5)
    # Test E dosed weekly across the window; Deca only once, before the window.
    for d in range(40, 4, -7):
        DoseLog.objects.create(
            owner=u, compound=test_e, taken_at=timezone.now() - timedelta(days=d),
            amount=250, unit="mg", route="im",
        )
    DoseLog.objects.create(
        owner=u, compound=deca, taken_at=timezone.now() - timedelta(days=60),
        amount=200, unit="mg", route="im",
    )

    data = phase_compound_levels(u, start, end)
    assert len(data["compounds"]) == 1  # one row per compound (no duplicates)
    names = {c["name"] for c in data["compounds"]}
    assert names == {"Test E"}  # Deca's only dose is outside the window → not shown
    pts = data["compounds"][0]["points"]
    assert pts[0]["date"] == start.isoformat()
    assert all(p["projected"] is False for p in pts)  # observed, not projected
    assert max(p["rate"] for p in pts) > 0
