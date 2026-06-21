"""Auto-activation: a phase adjustment flips the active protocol on its effective date."""
from datetime import date, timedelta

import pytest

from apps.accounts.models import User
from apps.core.models import Phase, PhaseAdjustment
from apps.protocols.models import Protocol
from apps.protocols.services import sync_active_protocol

pytestmark = pytest.mark.django_db

TODAY = date(2026, 2, 1)


@pytest.fixture
def user():
    return User.objects.create_user(email="act@example.com", password="x")


def _phase(user):
    return Phase.objects.create(
        owner=user, name="Block", phase_type="bulk", start_date=TODAY - timedelta(days=30)
    )


def test_adjustment_activates_on_effective_date(user):
    a = Protocol.objects.create(owner=user, name="A", is_active=True)
    b = Protocol.objects.create(owner=user, name="B", is_active=False)
    PhaseAdjustment.objects.create(phase=_phase(user), effective_date=TODAY, protocol=b)

    changed = sync_active_protocol(user, TODAY)

    a.refresh_from_db()
    b.refresh_from_db()
    assert changed == b
    assert b.is_active and not a.is_active
    # idempotent: a second pass changes nothing
    assert sync_active_protocol(user, TODAY) is None


def test_future_adjustment_waits_for_its_date(user):
    a = Protocol.objects.create(owner=user, name="A", is_active=True)
    b = Protocol.objects.create(owner=user, name="B", is_active=False)
    PhaseAdjustment.objects.create(
        phase=_phase(user), effective_date=TODAY + timedelta(days=1), protocol=b
    )

    # Today: the adjustment is still in the future → A stays active.
    assert sync_active_protocol(user, TODAY) is None
    a.refresh_from_db()
    b.refresh_from_db()
    assert a.is_active and not b.is_active

    # Tomorrow: B becomes active automatically.
    assert sync_active_protocol(user, TODAY + timedelta(days=1)) == b
    a.refresh_from_db()
    b.refresh_from_db()
    assert b.is_active and not a.is_active


def test_no_adjustments_leaves_manual_choice(user):
    a = Protocol.objects.create(owner=user, name="A", is_active=True)
    assert sync_active_protocol(user, TODAY) is None
    a.refresh_from_db()
    assert a.is_active
