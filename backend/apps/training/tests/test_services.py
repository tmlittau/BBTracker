from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.training.enums import SetType
from apps.training.models import Exercise, LoggedExercise, LoggedSet, Muscle, WorkoutSession
from apps.training.services import (
    average_weekly_muscle_volume,
    brzycki_1rm,
    counts_as_set,
    epley_1rm,
    estimated_1rm,
    rest_seconds_for,
    set_volume,
    weekly_muscle_volume,
)


class TestRestSecondsFor:
    def test_uses_configured_value_else_default(self):
        ex = Exercise(rest_by_set_type={"working": 180, "warmup": 45})
        assert rest_seconds_for(ex, "working") == 180
        assert rest_seconds_for(ex, "warmup") == 45
        assert rest_seconds_for(ex, "drop") == 120  # unset → default

    def test_empty_or_junk_falls_back_to_default(self):
        assert rest_seconds_for(Exercise(rest_by_set_type={}), "working") == 120
        assert rest_seconds_for(Exercise(rest_by_set_type={"working": 0}), "working") == 120


def _log_sets(user, muscle, started_at, n, set_type=SetType.WORKING, weight="50", reps=10):
    bench, _ = Exercise.objects.get_or_create(name="Bench Press")
    bench.primary_muscles.add(muscle)
    sess = WorkoutSession.objects.create(owner=user, started_at=started_at)
    le = LoggedExercise.objects.create(session=sess, exercise=bench, order=0)
    for i in range(n):
        LoggedSet.objects.create(
            logged_exercise=le, order=i, set_type=set_type,
            weight=weight, reps=reps, is_completed=True,
        )


class TestE1RM:
    def test_one_rep_returns_weight(self):
        assert epley_1rm(100, 1) == Decimal("100.00")
        assert brzycki_1rm(100, 1) == Decimal("100.00")

    def test_epley_formula(self):
        # 100 * (1 + 10/30) = 133.33
        assert epley_1rm(100, 10) == Decimal("133.33")

    def test_brzycki_formula(self):
        # 100 * 36 / (37 - 10) = 133.33
        assert brzycki_1rm(100, 10) == Decimal("133.33")

    def test_estimated_1rm_defaults_to_epley(self):
        assert estimated_1rm(100, 5) == epley_1rm(100, 5)

    def test_heavier_or_more_reps_increases_estimate(self):
        assert estimated_1rm(100, 5) > estimated_1rm(100, 4)
        assert estimated_1rm(110, 5) > estimated_1rm(100, 5)

    @pytest.mark.parametrize(
        "weight,reps",
        [(None, 5), (100, None), (0, 5), (100, 0), (-5, 5), (100, 999)],
    )
    def test_invalid_inputs_return_none(self, weight, reps):
        assert estimated_1rm(weight, reps) is None

    def test_accepts_decimal_weight(self):
        assert epley_1rm(Decimal("60.5"), 8) is not None


class TestSetVolume:
    def test_working_set_tonnage(self):
        assert set_volume(100, 5, SetType.WORKING) == Decimal("500.00")

    def test_warmup_excluded(self):
        assert set_volume(100, 5, SetType.WARMUP) == Decimal("0")

    def test_drop_set_counts(self):
        assert set_volume(60, 12, SetType.DROP) == Decimal("720.00")

    def test_missing_data_is_zero(self):
        assert set_volume(None, 5, SetType.WORKING) == Decimal("0")
        assert set_volume(100, None, SetType.WORKING) == Decimal("0")


class TestCountsAsSet:
    def test_working_and_top_set_count(self):
        assert counts_as_set(SetType.WORKING)
        assert counts_as_set(SetType.TOP_SET)

    def test_warmups_and_intensity_techniques_do_not(self):
        for t in (
            SetType.WARMUP, SetType.DROP, SetType.REST_PAUSE, SetType.MYO_REP,
            SetType.CLUSTER, SetType.AMRAP, SetType.BACKOFF, SetType.FAILURE,
        ):
            assert not counts_as_set(t)


@pytest.mark.django_db
def test_weekly_muscle_volume_counts_only_hard_sets():
    user = User.objects.create_user(email="vol@example.com", password="x")
    chest = Muscle.objects.create(name="Chest", slug="chest")
    bench = Exercise.objects.create(name="Bench Press")
    bench.primary_muscles.add(chest)
    session = WorkoutSession.objects.create(owner=user, started_at=timezone.now())
    le = LoggedExercise.objects.create(session=session, exercise=bench, order=0)
    for order, (st, w, r) in enumerate([
        (SetType.WORKING, "100", 5),   # counts; 500 tonnage
        (SetType.TOP_SET, "100", 3),   # counts; 300 tonnage
        (SetType.DROP, "60", 12),      # tonnage only (720), not a counted set
        (SetType.WARMUP, "40", 10),    # excluded entirely
    ]):
        LoggedSet.objects.create(
            logged_exercise=le, order=order, set_type=st, weight=w, reps=r, is_completed=True
        )

    vol = weekly_muscle_volume(user)
    assert vol["Chest"]["sets"] == 2  # working + top set only
    assert vol["Chest"]["tonnage"] == Decimal("1520.00")  # incl. the drop set's work


@pytest.mark.django_db
def test_average_weekly_muscle_volume_reports_per_week():
    now = timezone.now()
    user = User.objects.create_user(email="avg@example.com", password="x")
    chest = Muscle.objects.create(name="Chest", slug="chest")
    # 4 weekly sessions, 12 working sets each (48 total). First is 27d ago → span 28
    # days = 4.0 weeks → 48 / 4 = 12 sets/week, 24000 / 4 = 6000 kg/week.
    for wk in range(4):
        _log_sets(user, chest, now - timedelta(days=27 - wk * 7), 12)

    out = average_weekly_muscle_volume(user, window_days=30, now=now)
    assert out["Chest"]["sets"] == 12
    assert out["Chest"]["tonnage"] == Decimal("6000.00")


@pytest.mark.django_db
def test_average_weekly_muscle_volume_floors_short_history_at_one_week():
    now = timezone.now()
    user = User.objects.create_user(email="new@example.com", password="x")
    chest = Muscle.objects.create(name="Chest", slug="chest")
    # Only ~3 days of logging: 12 sets must read ~12/wk (÷ 1 week), not diluted by the
    # 30-day window (which would give 12 ÷ ~4.3 ≈ 3).
    _log_sets(user, chest, now - timedelta(days=2), 12)

    out = average_weekly_muscle_volume(user, window_days=30, now=now)
    assert out["Chest"]["sets"] == 12
