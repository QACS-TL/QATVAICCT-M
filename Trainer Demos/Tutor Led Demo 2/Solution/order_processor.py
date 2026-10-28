from collections.abc import Mapping
from decimal import Decimal, InvalidOperation


class OrderProcessor:

    def __init__(
        self,
        repository,
        payment_service
    ):
        self.repository = repository
        self.payment_service = payment_service

    async def process_order(self, order):
        order_id = getattr(order, "id", None)
        currency = getattr(order, "currency", None)
        if order_id is None or order_id == "" or not self._valid_currency(currency):
            return {"success": False}

        try:
            total = self._calculate_total(order)
        except (AttributeError, InvalidOperation, TypeError, ValueError):
            return {"success": False}

        if total < 0:
            return {"success": False}
        if total == 0:
            return {"success": True}

        customer = (
            await self.repository
                .get_customer(
                    order.customer_id
                )
        )
        if customer is None:
            return {"success": False}

        payment_result = await self.payment_service.charge(
            customer,
            total,
            currency=currency,
            idempotency_key=str(order_id),
        )
        if not self._payment_succeeded(payment_result):
            return {"success": False}

        return {"success": True}

    @staticmethod
    def _calculate_total(order):
        total = Decimal("0")
        for line in order.lines:
            price = OrderProcessor._to_decimal(line.price)
            quantity = getattr(line, "quantity", 1)
            if type(quantity) is not int or quantity < 1:
                raise ValueError("quantity must be a positive integer")
            if price < 0:
                raise ValueError("line price cannot be negative")
            total += price * quantity

        tax = OrderProcessor._to_decimal(
            getattr(order, "tax_amount", 0)
        )
        discount = OrderProcessor._to_decimal(
            getattr(order, "discount_amount", 0)
        )
        if tax < 0 or discount < 0:
            raise ValueError("tax and discount amounts cannot be negative")
        return total + tax - discount

    @staticmethod
    def _to_decimal(value):
        if isinstance(value, bool):
            raise ValueError("money values must be numeric")
        amount = Decimal(str(value))
        if not amount.is_finite():
            raise ValueError("money values must be finite")
        return amount

    @staticmethod
    def _valid_currency(currency):
        return (
            isinstance(currency, str)
            and len(currency) == 3
            and currency.isascii()
            and currency.isalpha()
            and currency.isupper()
        )

    @staticmethod
    def _payment_succeeded(result):
        if result is True:
            return True
        if isinstance(result, Mapping):
            if "success" in result:
                return result["success"] is True
            status = result.get("status")
        else:
            success = getattr(result, "success", None)
            if success is not None:
                return success is True
            status = getattr(result, "status", None)

        return isinstance(status, str) and status.lower() in {
            "success",
            "succeeded",
            "paid",
            "completed",
        }