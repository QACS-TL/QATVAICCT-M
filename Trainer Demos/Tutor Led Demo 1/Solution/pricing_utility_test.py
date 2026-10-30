from decimal import Decimal
from pricing_utilities import calculate_discount
import pytest


def test_premium_customer_gets_15_percent_discount():
    assert calculate_discount(Decimal("100"), True) == Decimal("15")


def test_standard_customer_gets_10_percent_discount():
    assert calculate_discount(Decimal("100"), False) == Decimal("10")


@pytest.mark.parametrize("is_premium", [True, False])
def test_orders_below_20_get_no_discount(is_premium):
    assert calculate_discount(Decimal("19.99"), is_premium) == Decimal("0")


@pytest.mark.parametrize(
    ("is_premium", "expected_discount"),
    [(True, Decimal("3")), (False, Decimal("2"))],
)
def test_order_of_20_gets_customer_discount(is_premium, expected_discount):
    assert calculate_discount(Decimal("20"), is_premium) == expected_discount


@pytest.mark.parametrize(
    ("order_total", "is_premium"),
    [(Decimal("1000"), True), (Decimal("2000"), False)],
)
def test_discount_is_capped_at_100(order_total, is_premium):
    assert calculate_discount(order_total, is_premium) == Decimal("100")


@pytest.mark.parametrize("is_premium", [True, False])
def test_negative_order_total_is_invalid(is_premium):
    with pytest.raises(ValueError):
        calculate_discount(Decimal("-0.01"), is_premium)
