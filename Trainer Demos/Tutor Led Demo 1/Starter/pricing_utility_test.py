from decimal import Decimal
from pricing_utilities import calculate_discount


def test_premium_customer_gets_15_percent_discount():
    assert calculate_discount(Decimal("100"), True) == Decimal("15")

def test_standard_customer_gets_10_percent_discount():
    assert calculate_discount(Decimal("100"), False) == Decimal("10")

