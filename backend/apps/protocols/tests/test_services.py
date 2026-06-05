from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from apps.protocols.services import (
    active_amount,
    adherence_pct,
    concentration_series,
    expected_doses,
    marker_in_range,
    remaining_fraction,
    site_status,
)


class TestRemainingFraction:
    def test_zero_elapsed_is_full(self):
        assert remaining_fraction(0, 24) == 1.0

    def test_one_half_life_is_half(self):
        assert remaining_fraction(24, 24) == 0.5

    def test_two_half_lives_is_quarter(self):
        assert remaining_fraction(48, 24) == 0.25

    def test_no_half_life_is_zero(self):
        assert remaining_fraction(10, 0) == 0.0
        assert remaining_fraction(10, None) == 0.0


class TestActiveAmount:
    def test_applies_ester_fraction(self):
        # 100 mg testosterone enanthate (~0.70 active) at t=0 → 70 mg active
        assert active_amount(100, 0.70, 0, 24) == 70.0

    def test_decays(self):
        # 100 mg, fraction 1, after one half-life → 50
        assert active_amount(100, 1, 24, 24) == 50.0

    def test_none_amount(self):
        assert active_amount(None, 1, 0, 24) == 0.0


class TestConcentrationSeries:
    def test_builds_points_and_accumulates(self):
        base = datetime(2026, 1, 1, tzinfo=UTC)
        doses = [(base, 100), (base + timedelta(days=3), 100)]
        end = base + timedelta(days=6)
        pts = concentration_series(doses, half_life_hours=72, active_fraction=1,
                                   start=base, end=end, step_hours=24)
        assert len(pts) == 7  # day 0..6 inclusive
        assert pts[0]["value"] == 100.0
        assert 149 <= pts[3]["value"] <= 151

    def test_no_half_life_empty(self):
        base = datetime(2026, 1, 1, tzinfo=UTC)
        assert concentration_series([(base, 100)], 0, 1, base, base) == []


class TestSiteStatus:
    def test_buckets(self):
        assert site_status(None) == "rested"
        assert site_status(10) == "rested"
        assert site_status(7) == "rested"
        assert site_status(5) == "recovering"
        assert site_status(3) == "recovering"
        assert site_status(1) == "fresh"
        assert site_status(0) == "fresh"


class TestAdherence:
    def test_expected_doses(self):
        assert expected_doses(3.5, 28) == 14.0
        assert expected_doses(1, 7) == 1.0

    def test_pct(self):
        assert adherence_pct(14, 14) == 100
        assert adherence_pct(7, 14) == 50
        assert adherence_pct(20, 14) == 100
        assert adherence_pct(5, 0) is None


class TestMarkerInRange:
    """`marker_in_range` is pure — feed it a lightweight stand-in for a BloodMarker."""

    def _marker(self, **kw):
        defaults = dict(
            ref_low=None, ref_high=None,
            ref_low_male=None, ref_high_male=None,
            ref_low_female=None, ref_high_female=None,
        )
        defaults.update(kw)
        return SimpleNamespace(**defaults)

    def test_generic_range(self):
        alt = self._marker(ref_low=7, ref_high=56)
        assert marker_in_range(5, alt) == "low"
        assert marker_in_range(30, alt) == "in_range"
        assert marker_in_range(80, alt) == "high"

    def test_sex_specific_male(self):
        tt = self._marker(ref_low_male=300, ref_high_male=1000)
        assert marker_in_range(250, tt, sex="male") == "low"
        assert marker_in_range(650, tt, sex="male") == "in_range"
        assert marker_in_range(1200, tt, sex="male") == "high"

    def test_sex_specific_female_differs(self):
        tt = self._marker(ref_low_male=300, ref_high_male=1000,
                          ref_low_female=15, ref_high_female=70)
        # 60 is "low" for a male range but "in_range" for a female range.
        assert marker_in_range(60, tt, sex="male") == "low"
        assert marker_in_range(60, tt, sex="female") == "in_range"

    def test_unknown_sex_without_generic_is_in_range(self):
        # Only sex-specific ranges + unknown sex → cannot judge → in_range.
        tt = self._marker(ref_low_male=300, ref_high_male=1000)
        assert marker_in_range(250, tt, sex=None) == "in_range"
