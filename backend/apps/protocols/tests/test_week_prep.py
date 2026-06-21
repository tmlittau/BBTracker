from datetime import date

import pytest

from apps.accounts.models import User
from apps.core.models import Phase, PhaseAdjustment
from apps.protocols.models import Compound, Protocol, ProtocolItem, Supplement
from apps.protocols.services import week_prep_plan

pytestmark = pytest.mark.django_db

MON = date(2026, 1, 5)  # a Monday (anchor for interval cadences)


@pytest.fixture
def user():
    return User.objects.create_user(email="wp@example.com", password="x")


def _oral(owner, name):
    return Compound.objects.create(
        owner=owner, name=name, compound_class="other",
        default_unit="mg", default_route="oral",
    )


def _item(proto, *, compound=None, supplement=None, dose="1", unit="mg",
          freq="daily", days=None, times=None):
    return ProtocolItem.objects.create(
        protocol=proto, compound=compound, supplement=supplement,
        dose_amount=dose, dose_unit=unit, route="" if supplement else "oral",
        frequency=freq, days_of_week=days or [], times_of_day=times or ["am"],
    )


def _names(slots, slot_key):
    for s in slots:
        if s["slot"] == slot_key:
            return {e["name"] for e in s["entries"]}
    return set()


def test_baseline_additions_and_removals(user):
    p = Protocol.objects.create(owner=user, name="Stack", is_active=True, started_on=MON)
    _item(p, compound=_oral(user, "Cardarine"), dose="10", times=["am"])             # daily
    _item(p, supplement=Supplement.objects.create(owner=user, name="Vitamin D"),
          dose="1", unit="capsule", times=["am"])                                    # daily
    _item(p, supplement=Supplement.objects.create(owner=user, name="Magnesium"),
          dose="2", unit="capsule", times=["night"])                                 # daily, night
    _item(p, compound=_oral(user, "Proviron"), dose="25", freq="specific_days",
          days=[0, 1, 2, 3, 4, 5], times=["am"])                                     # Mon–Sat
    _item(p, compound=_oral(user, "Anastrozole"), dose="0.5", freq="eod", times=["am"])  # EOD

    plan = week_prep_plan(user, MON)

    am_base = _names(plan["everyday"], "am")
    assert {"Cardarine", "Vitamin D", "Proviron"} <= am_base   # ≥5/7 days → baseline
    assert "Anastrozole" not in am_base                        # EOD (4/7) → not baseline
    assert _names(plan["everyday"], "night") == {"Magnesium"}

    days = {d["label"]: d for d in plan["days"]}
    # Mon–Sat item skipped on Sunday → one "removed" note, not six daily rows
    assert "Proviron" in _names(days["Sun"]["removed"], "am")
    assert all(
        "Proviron" not in _names(days[wd]["removed"], "am")
        for wd in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    )
    # EOD item → added on its days only
    assert "Anastrozole" in _names(days["Mon"]["added"], "am")
    assert "Anastrozole" in _names(days["Wed"]["added"], "am")
    assert _names(days["Tue"]["added"], "am") == set()
    assert plan["protocols"] == ["Stack"]


def test_interval_cadence_without_start_date(user):
    """Regression: an 'every 3 days' item on a protocol with no start date must keep
    its 1-in-N cadence (phased to a fixed epoch), not collapse to 'every day'."""
    p = Protocol.objects.create(owner=user, name="No-start", is_active=True)  # started_on=None
    _item(p, compound=_oral(user, "Cardarine"), dose="10", freq="every_3_days", times=["am"])

    plan = week_prep_plan(user, MON)

    assert "Cardarine" not in _names(plan["everyday"], "am")  # not an everyday baseline
    week = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    days = {d["label"]: d for d in plan["days"]}
    hits = [wd for wd in week if "Cardarine" in _names(days[wd]["added"], "am")]
    assert 2 <= len(hits) <= 3  # 1-in-3 over 7 days → never all 7
    idx = [week.index(w) for w in hits]
    assert all(idx[i + 1] - idx[i] == 3 for i in range(len(idx) - 1))  # exactly every 3rd day


def test_injectables_and_prn_excluded(user):
    p = Protocol.objects.create(owner=user, name="Inj", is_active=True, started_on=MON)
    ProtocolItem.objects.create(
        protocol=p,
        compound=Compound.objects.create(
            owner=user, name="Test E", compound_class="anabolic",
            default_unit="mg", default_route="im",
        ),
        dose_amount="250", dose_unit="mg", route="im",
        frequency="specific_days", days_of_week=[0, 3], times_of_day=["am"],
    )
    _item(p, compound=_oral(user, "Aspirin"), dose="100", freq="prn", times=["am"])
    _item(p, compound=_oral(user, "Cardarine"), dose="10", times=["am"])

    plan = week_prep_plan(user, MON)
    assert _names(plan["everyday"], "am") == {"Cardarine"}  # injectable + PRN excluded


def test_phase_adjustment_switches_protocol(user):
    a = Protocol.objects.create(owner=user, name="A", is_active=True, started_on=MON)
    b = Protocol.objects.create(owner=user, name="B", is_active=False, started_on=MON)
    _item(a, compound=_oral(user, "AlphaPill"), times=["am"])
    _item(b, compound=_oral(user, "BetaPill"), times=["am"])
    phase = Phase.objects.create(
        owner=user, name="Block", phase_type="bulk", start_date=MON, end_date=None
    )
    PhaseAdjustment.objects.create(
        phase=phase, effective_date=date(2026, 1, 8), protocol=b  # Thursday
    )

    plan = week_prep_plan(user, MON)
    days = {d["label"]: d for d in plan["days"]}
    assert days["Mon"]["protocol"] == "A"  # before the adjustment → active fallback
    assert days["Thu"]["protocol"] == "B"  # adjustment carried forward
    assert plan["protocols"] == ["A", "B"]
    assert "AlphaPill" in _names(days["Mon"]["added"], "am")
    assert "BetaPill" in _names(days["Thu"]["added"], "am")


def test_custom_slot_labels(user):
    from apps.notifications.models import ReminderSettings

    p = Protocol.objects.create(owner=user, name="Stack", is_active=True, started_on=MON)
    _item(p, compound=_oral(user, "Cardarine"), dose="10", times=["am"])
    _item(p, compound=_oral(user, "Melatonin"), dose="3", times=["night"])
    ReminderSettings.objects.create(owner=user, am_label="Pre-workout")  # night left default

    plan = week_prep_plan(user, MON)
    by_slot = {s["slot"]: s["slot_label"] for s in plan["everyday"]}
    assert by_slot["am"] == "Pre-workout"   # custom label honoured
    assert by_slot["night"] == "Night"      # blank → default
