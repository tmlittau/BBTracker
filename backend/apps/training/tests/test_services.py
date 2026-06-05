from decimal import Decimal

import pytest

from apps.training.enums import SetType
from apps.training.services import (
    brzycki_1rm,
    epley_1rm,
    estimated_1rm,
    set_volume,
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
