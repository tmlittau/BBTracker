from decimal import Decimal

from apps.nutrition.services import (
    percent_of_target,
    resolve_grams,
    scale_amount,
)


class TestScaleAmount:
    def test_scales_per_100g_to_grams(self):
        # 20 g protein per 100 g, 150 g eaten → 30 g
        assert scale_amount(20, 150) == Decimal("30.000")

    def test_half_portion(self):
        assert scale_amount(100, 50) == Decimal("50.000")

    def test_missing_returns_zero(self):
        assert scale_amount(None, 100) == Decimal("0")
        assert scale_amount(20, None) == Decimal("0")

    def test_accepts_decimal(self):
        assert scale_amount(Decimal("8.5"), Decimal("200")) == Decimal("17.000")


class TestResolveGrams:
    def test_quantity_times_serving(self):
        # 2 servings of 30 g = 60 g
        assert resolve_grams(2, 30) == Decimal("60.00")

    def test_no_serving_is_grams(self):
        assert resolve_grams(150, None) == Decimal("150.00")

    def test_fractional_quantity(self):
        assert resolve_grams(Decimal("1.5"), 40) == Decimal("60.00")

    def test_none_quantity(self):
        assert resolve_grams(None, 30) is None


class TestPercentOfTarget:
    def test_basic(self):
        assert percent_of_target(50, 100) == 50
        assert percent_of_target(150, 100) == 150

    def test_zero_or_missing_target(self):
        assert percent_of_target(50, 0) is None
        assert percent_of_target(50, None) is None
