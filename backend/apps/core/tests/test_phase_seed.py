"""A phase's initial adjustment is seeded on creation, and the backfill command
brings existing phases into the same shape."""
from datetime import date, timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.models import Phase, PhaseAdjustment
from apps.core.services import seed_initial_adjustment
from apps.protocols.models import Protocol

pytestmark = pytest.mark.django_db

TODAY = date(2026, 6, 22)


@pytest.fixture
def user():
    return User.objects.create_user(email="seed@example.com", password="x")


def _phase(user, name="Prep", start=TODAY):
    return Phase.objects.create(owner=user, name=name, phase_type="prep", start_date=start)


def test_seed_captures_active_plan(user):
    p = Protocol.objects.create(owner=user, name="A", is_active=True)
    phase = _phase(user)
    adj = seed_initial_adjustment(phase)
    assert adj is not None
    assert adj.protocol_id == p.id and adj.effective_date == TODAY
    assert seed_initial_adjustment(phase) is None  # idempotent
    assert phase.adjustments.count() == 1


def test_seed_skips_when_covered_or_nothing_active(user):
    bare = _phase(user, "Bare")
    assert seed_initial_adjustment(bare) is None  # nothing active

    Protocol.objects.create(owner=user, name="A", is_active=True)
    covered = _phase(user, "Covered")
    PhaseAdjustment.objects.create(phase=covered, effective_date=TODAY, reason="manual")
    assert seed_initial_adjustment(covered) is None  # already covered


def test_phase_create_seeds_initial_adjustment(user):
    Protocol.objects.create(owner=user, name="A", is_active=True)
    c = APIClient()
    c.force_authenticate(user)
    res = c.post(
        "/api/v1/phases/",
        {"name": "Prep", "phase_type": "prep", "start_date": TODAY.isoformat()},
        format="json",
    )
    assert res.status_code == 201
    adj = Phase.objects.get(id=res.json()["id"]).adjustments.get()
    assert adj.protocol.name == "A" and adj.effective_date == TODAY


def test_backfill_command(user):
    prot = Protocol.objects.create(owner=user, name="A", is_active=True)
    no_adj = _phase(user, "NoAdj", TODAY - timedelta(days=30))
    gap = _phase(user, "Gap", TODAY - timedelta(days=30))
    PhaseAdjustment.objects.create(phase=gap, effective_date=TODAY, protocol=prot)
    covered = _phase(user, "Covered", TODAY - timedelta(days=30))
    PhaseAdjustment.objects.create(phase=covered, effective_date=covered.start_date, protocol=prot)

    out = StringIO()
    call_command("backfill_initial_adjustments", email=user.email, stdout=out)
    text = out.getvalue()

    assert no_adj.adjustments.filter(effective_date=no_adj.start_date).exists()  # seeded
    assert not gap.adjustments.filter(effective_date=gap.start_date).exists()  # flagged, not seeded
    assert gap.adjustments.count() == 1  # untouched
    assert "needs manual" in text
    assert "seeded=1" in text and "flagged=1" in text and "skipped=1" in text
