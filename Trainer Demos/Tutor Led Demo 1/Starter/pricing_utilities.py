from decimal import Decimal

def calculate_discount(order_total: Decimal, is_premium: bool)->Decimal:
    if is_premium:
        return order_total * Decimal("0.15")
    return order_total * Decimal("0.10")


