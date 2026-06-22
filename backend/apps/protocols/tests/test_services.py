import math
from datetime import date
from types import SimpleNamespace

from apps.protocols.services import (
    absorption_constant_per_day,
    active_amount,
    adherence_pct,
    concentration_series,
    decay_constant_per_day,
    expected_doses,
    marker_in_range,
    release_rate_series,
    remaining_fraction,
    scheduled_dose_dates,
    site_status,
    times_per_day_count,
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


class TestReleaseRate:
    def test_single_dose_peaks_then_halves(self):
        # 100 mg, f=1, t½=24h (k = ln2 per day). Release rate at the dose = D·k; one
        # half-life (1 day) later it has halved.
        pts = release_rate_series([(0, 100)], half_life_hours=24, active_fraction=1,
                                  start_day=0, end_day=2, step_days=1)
        assert [d for d, _ in pts] == [0, 1, 2]
        k = decay_constant_per_day(24)
        assert pts[0][1] == round(100 * k, 5)
        assert pts[1][1] == round(pts[0][1] * 0.5, 5)

    def test_active_fraction_scales(self):
        full = release_rate_series([(0, 100)], 24, 1.0, 0, 0)[0][1]
        half = release_rate_series([(0, 100)], 24, 0.5, 0, 0)[0][1]
        assert round(half, 6) == round(full * 0.5, 6)

    def test_accumulates_across_doses(self):
        one = release_rate_series([(0, 100)], 72, 1, 5, 5)[0][1]
        two = release_rate_series([(0, 100), (3, 100)], 72, 1, 5, 5)[0][1]
        assert two > one

    def test_no_half_life_empty(self):
        assert release_rate_series([(0, 100)], 0, 1, 0, 5) == []
        assert release_rate_series([(0, 100)], None, 1, 0, 5) == []


class TestAbsorptionConstant:
    def test_reproduces_tmax(self):
        ke = decay_constant_per_day(168)  # t½ 7 days
        ka = absorption_constant_per_day(33.3, ke)  # tmax ≈ 1.39 days
        assert ka is not None and ka > ke
        tmax_days = math.log(ka / ke) / (ka - ke)
        assert abs(tmax_days - 33.3 / 24.0) < 0.01

    def test_missing_tmax_is_none(self):
        ke = decay_constant_per_day(168)
        assert absorption_constant_per_day(None, ke) is None
        assert absorption_constant_per_day(0, ke) is None


class TestConcentration:
    def test_single_dose_rises_to_peak_then_falls(self):
        pts = concentration_series([(0, 100)], half_life_hours=168, tmax_hours=48,
                                   bioavailability=1, active_fraction=1,
                                   start_day=0, end_day=20, step_days=1)
        levels = [v for _, v in pts]
        assert levels[0] < levels[2]  # absorption phase: starts low, rising
        peak_i = max(range(len(levels)), key=lambda i: levels[i])
        assert 1 <= peak_i <= 3  # peaks near tmax (~2 days)
        assert levels[-1] < levels[peak_i]  # decays after the peak

    def test_fallback_is_exponential_decay(self):
        # No tmax → instantaneous absorption: starts at max, halves each half-life.
        pts = concentration_series([(0, 100)], half_life_hours=24, tmax_hours=None,
                                   bioavailability=1, active_fraction=1,
                                   start_day=0, end_day=2, step_days=1)
        assert pts[0][1] == 100.0
        assert round(pts[1][1], 5) == 50.0
        assert round(pts[2][1], 5) == 25.0

    def test_bioavailability_and_fraction_scale(self):
        full = concentration_series([(0, 100)], 24, None, 1.0, 1.0, 0, 0)[0][1]
        half_bio = concentration_series([(0, 100)], 24, None, 0.5, 1.0, 0, 0)[0][1]
        half_f = concentration_series([(0, 100)], 24, None, 1.0, 0.5, 0, 0)[0][1]
        assert round(half_bio, 6) == round(full * 0.5, 6)
        assert round(half_f, 6) == round(full * 0.5, 6)

    def test_no_half_life_empty(self):
        assert concentration_series([(0, 100)], 0, None, 1, 1, 0, 5) == []


class TestScheduledDoses:
    anchor = date(2026, 1, 5)  # a Monday

    def test_daily_every_day(self):
        days = scheduled_dose_dates("daily", [], date(2026, 1, 5), date(2026, 1, 11), self.anchor)
        assert len(days) == 7

    def test_eod_phased_to_anchor(self):
        days = scheduled_dose_dates("eod", [], date(2026, 1, 5), date(2026, 1, 11), self.anchor)
        assert days == [date(2026, 1, 5), date(2026, 1, 7), date(2026, 1, 9), date(2026, 1, 11)]

    def test_weekly(self):
        days = scheduled_dose_dates("weekly", [], date(2026, 1, 5), date(2026, 1, 26), self.anchor)
        assert days == [date(2026, 1, 5), date(2026, 1, 12), date(2026, 1, 19), date(2026, 1, 26)]

    def test_specific_weekdays(self):
        # Mon (0) and Thu (3) within one week.
        days = scheduled_dose_dates("specific_days", [0, 3], date(2026, 1, 5),
                                    date(2026, 1, 11), self.anchor)
        assert days == [date(2026, 1, 5), date(2026, 1, 8)]

    def test_prn_not_projectable(self):
        assert scheduled_dose_dates("prn", [], date(2026, 1, 5), date(2026, 1, 30),
                                    self.anchor) == []


class TestTimesPerDay:
    def test_defaults_and_multi(self):
        assert times_per_day_count([], "daily") == 1
        assert times_per_day_count(["am", "pm"], "daily") == 2
        assert times_per_day_count([], "2x_day") == 2


class TestSiteStatus:
    def test_im_buckets(self):
        # IM recovers over ~a week: red days 0-2, amber 3-6, green from day 7.
        assert site_status(None, "im") == "rested"
        assert site_status(10, "im") == "rested"
        assert site_status(7, "im") == "rested"
        assert site_status(5, "im") == "recovering"
        assert site_status(3, "im") == "recovering"
        assert site_status(1, "im") == "fresh"
        assert site_status(0, "im") == "fresh"
        assert site_status(5) == "recovering"  # defaults to IM thresholds

    def test_subq_buckets(self):
        # subQ recovers over ~a day: red day 0, amber day 1, green from day 2.
        assert site_status(0, "subq") == "fresh"
        assert site_status(1, "subq") == "recovering"
        assert site_status(2, "subq") == "rested"
        assert site_status(5, "subq") == "rested"
        assert site_status(None, "subq") == "rested"


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


class TestResultRange:
    """Per-result reference ranges (e.g. captured from a PDF) drive flagging."""

    def _marker(self, **kw):
        defaults = dict(
            ref_low=None, ref_high=None, ref_low_male=None, ref_high_male=None,
            ref_low_female=None, ref_high_female=None,
        )
        defaults.update(kw)
        return SimpleNamespace(**defaults)

    def test_flag_value(self):
        from apps.protocols.services import flag_value

        assert flag_value(5, 10, 20) == "low"
        assert flag_value(15, 10, 20) == "in_range"
        assert flag_value(25, 10, 20) == "high"
        assert flag_value(25, None, None) == "in_range"

    def test_result_range_prefers_result_over_marker(self):
        from apps.protocols.services import result_range

        marker = self._marker(ref_low=1, ref_high=2)
        with_own = SimpleNamespace(ref_low=10, ref_high=20, marker=marker)
        without = SimpleNamespace(ref_low=None, ref_high=None, marker=marker)
        assert result_range(with_own) == (10, 20)
        assert result_range(without) == (1, 2)
