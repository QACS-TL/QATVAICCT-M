from decimal import Decimal


def calculate_discount(order_total: Decimal, is_premium: bool)->Decimal:
    if order_total < 0:
        raise ValueError("order_total cannot be negative")

    if order_total < Decimal("20"):
        return Decimal("0")

    if is_premium:
        discount = order_total * Decimal("0.15")
    else:
        discount = order_total * Decimal("0.10")

    return min(round(discount, 2), Decimal("100"))
