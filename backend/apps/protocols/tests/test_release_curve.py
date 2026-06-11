from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.protocols.models import Compound, DoseLog, Protocol, ProtocolItem
from apps.protocols.services import protocol_release_curves

pytestmark = pytest.mark.django_db


def test_release_rate_accumulates_with_steady_dosing(db):
    """Steady daily dosing makes the active-release rate RISE toward a plateau
    (≈ dose × active fraction), not decrease.

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
    logged = [pt["rate"] for pt in data["compounds"][0]["points"] if not pt["projected"]]
    # Climbs over the dosing period toward the 50 mg × 0.70 = 35 mg/day plateau
    # (still approaching it at day 20). The point: more doses → higher, not lower.
    assert logged[1] < logged[len(logged) // 2] < logged[-1]
    assert logged[-1] > 2 * logged[2]
    assert 25 < logged[-1] < 35
