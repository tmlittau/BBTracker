"""Pure-helper tests for the self-coaching aggregators."""
from apps.core.services import mean, trend


class TestMean:
    def test_averages_present_values(self):
        assert mean([4, 3, 5]) == 4.0

    def test_skips_none(self):
        assert mean([4, None, 2]) == 3.0

    def test_all_none_is_none(self):
        assert mean([None, None]) is None

    def test_empty_is_none(self):
        assert mean([]) is None


class TestTrend:
    def test_first_last_delta(self):
        assert trend([80, 81, 79, 78]) == {"first": 80.0, "last": 78.0, "delta": -2.0}

    def test_skips_none_ends(self):
        assert trend([None, 90, 92, None]) == {"first": 90.0, "last": 92.0, "delta": 2.0}

    def test_single_value(self):
        assert trend([84.5]) == {"first": 84.5, "last": 84.5, "delta": 0.0}

    def test_empty_is_none(self):
        assert trend([None]) is None
