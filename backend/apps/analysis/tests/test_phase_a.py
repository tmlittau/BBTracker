"""Phase A: robust stats module, time-series/overlay layer, and TDEE/partitioning."""
from datetime import date, timedelta

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.analysis import services, stats
from apps.analysis.timeseries import metric_catalog, overlay, series_for

D0 = date(2026, 1, 1)


class TestStats:
    def test_ewma_smooths_constant_and_damps_spike(self):
        flat = [(D0 + timedelta(days=i), 100.0) for i in range(5)]
        assert stats.ewma(flat)[-1][1] == pytest.approx(100.0)
        spike = [(D0, 100.0), (D0 + timedelta(days=1), 120.0)]
        assert 100.0 < stats.ewma(spike, halflife_days=10)[-1][1] < 120.0

    def test_theil_sen_exact_on_linear(self):
        pts = [(D0 + timedelta(days=i), 100 - 0.1 * i) for i in range(20)]
        assert stats.theil_sen_slope(pts) == pytest.approx(-0.1)

    def test_theil_sen_is_robust_to_end_outlier(self):
        pts = [(D0 + timedelta(days=i), 100 - 0.1 * i) for i in range(20)]
        pts[-1] = (pts[-1][0], 130.0)  # a big spike at the end
        ts, ls = stats.theil_sen_slope(pts), stats.linear_slope(pts)
        assert ts == pytest.approx(-0.1, abs=0.05)  # median slope barely moves
        assert ls > ts  # least-squares gets dragged up by the outlier

    def test_change_point_finds_the_break(self):
        flat = [(D0 + timedelta(days=i), 100.0) for i in range(20)]
        rising = [(D0 + timedelta(days=20 + i), 100.0 + i) for i in range(20)]
        cps = stats.detect_change_points(flat + rising, min_size=8)
        assert cps and any(abs((cp - (D0 + timedelta(days=20))).days) <= 3 for cp in cps)

    def test_empty_inputs(self):
        assert stats.ewma([]) == []
        assert stats.theil_sen_slope([]) is None
        assert stats.linear_slope([]) is None
        assert stats.detect_change_points([]) == []


def test_partitioning_splits_lean_and_fat():
    trend = [
        {"date": "2026-01-01", "weight_kg": 90, "lean_mass_kg": 72, "fat_mass_kg": 18},
        {"date": "2026-02-01", "weight_kg": 94, "lean_mass_kg": 75, "fat_mass_kg": 19},
    ]
    p = services.partitioning(trend)
    assert p["weight_change_kg"] == 4 and p["lean_change_kg"] == 3 and p["fat_change_kg"] == 1
    assert p["p_ratio"] == 0.75 and p["days"] == 31
    assert services.partitioning([]) is None


def test_adaptive_tdee_reports_trend_and_rate():
    weight = {D0 + timedelta(days=i): 90 - (0.5 / 7) * i for i in range(21)}
    intake = {D0 + timedelta(days=i): 2500 for i in range(21)}
    res = services.adaptive_tdee(intake, weight)
    assert res is not None
    assert res["trend_weight"] is not None
    assert res["weight_rate_pct_wk"] < 0  # cutting
    assert "weight_slope_kg_wk" in res  # backward-compatible key kept


@pytest.fixture
def user(db):
    return User.objects.create_user(email="ts@example.com", password="x")


@pytest.mark.django_db
def test_series_for_and_overlay(user):
    from apps.diary.models import CheckIn

    for i in range(5):
        CheckIn.objects.create(
            owner=user, date=D0 + timedelta(days=i), bodyweight=90 - 0.1 * i, energy=4
        )
    pts = series_for(user, "bodyweight", D0, D0 + timedelta(days=10))
    assert len(pts) == 5 and pts[0][1] == pytest.approx(90.0)

    ov = overlay(user, ["bodyweight", "energy"], D0, D0 + timedelta(days=10))
    assert {m["key"] for m in ov["metrics"]} == {"bodyweight", "energy"}
    bw = next(m for m in ov["metrics"] if m["key"] == "bodyweight")
    assert bw["unit"] == "kg" and len(bw["points"]) == 5


@pytest.mark.django_db
def test_metric_catalog_lists_core_metrics(user):
    keys = {c["key"] for c in metric_catalog(user)}
    assert {"bodyweight", "calories", "soreness", "training_tonnage"} <= keys


@pytest.mark.django_db
def test_catalog_dedupes_doses_and_bloodwork(user):
    """One entry per compound / marker, not one per dose log / result (guards the
    .order_by().distinct() fix — models order by date, which defeats a bare distinct)."""
    from django.utils import timezone

    from apps.protocols.models import BloodMarker, BloodResult, Compound, DoseLog

    c = Compound.objects.create(
        owner=user, name="Test E", slug="test-e", compound_class="anabolic", default_unit="mg"
    )
    for i in range(5):
        DoseLog.objects.create(
            owner=user, compound=c, taken_at=timezone.now() - timedelta(days=i),
            amount="250", unit="mg", status="taken",
        )
    marker = BloodMarker.objects.create(name="Hematocrit", slug="hematocrit", unit="%")
    for i in range(4):
        BloodResult.objects.create(
            owner=user, marker=marker, value=48 + i, measured_on=D0 + timedelta(days=10 * i)
        )

    cat = metric_catalog(user)
    assert [x["key"] for x in cat if x["key"].startswith("dose:")] == ["dose:test-e"]
    assert [x["key"] for x in cat if x["key"].startswith("blood:")] == ["blood:hematocrit"]


@pytest.mark.django_db
def test_series_and_metrics_endpoints(user):
    from apps.diary.models import CheckIn

    CheckIn.objects.create(owner=user, date=D0, bodyweight=90)
    c = APIClient()
    c.force_authenticate(user)
    end = D0 + timedelta(days=5)
    resp = c.get(f"/api/v1/analysis/series/?metrics=bodyweight&start={D0}&end={end}")
    assert resp.status_code == 200
    assert resp.json()["metrics"][0]["key"] == "bodyweight"
    assert c.get("/api/v1/analysis/metrics/").status_code == 200
