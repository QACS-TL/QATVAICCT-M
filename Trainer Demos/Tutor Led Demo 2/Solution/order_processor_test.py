import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from order_processor import OrderProcessor


def make_order(lines, **overrides):
    values = {
        "id": "order-1",
        "customer_id": "customer-1",
        "currency": "USD",
        "lines": lines,
        "tax_amount": Decimal("0"),
        "discount_amount": Decimal("0"),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class IdempotentPaymentService:
    def __init__(self, timeout_after_first_charge=False):
        self.requests = {}
        self.attempted_keys = []
        self.charge_count = 0
        self.timeout_after_first_charge = timeout_after_first_charge

    async def charge(self, customer, amount, *, currency, idempotency_key):
        self.attempted_keys.append(idempotency_key)
        await asyncio.sleep(0)

        request = (customer, amount, currency)
        if idempotency_key in self.requests:
            if self.requests[idempotency_key][0] != request:
                raise ValueError("Idempotency key reused for a different charge")
            return self.requests[idempotency_key][1]

        self.charge_count += 1
        result = {"success": True}
        self.requests[idempotency_key] = (request, result)
        if self.timeout_after_first_charge:
            self.timeout_after_first_charge = False
            raise TimeoutError("Payment completed but response was lost")
        return result


@pytest.mark.asyncio
async def test_successful_order_processing():
    customer = object()
    repository = SimpleNamespace(
        get_customer=AsyncMock(return_value=customer)
    )
    payment_service = SimpleNamespace(
        charge=AsyncMock(return_value={"success": True})
    )
    processor = OrderProcessor(repository, payment_service)
    order = make_order(
        [
            SimpleNamespace(price=10),
            SimpleNamespace(price=15),
        ]
    )

    result = await processor.process_order(order)

    assert result["success"] is True
    repository.get_customer.assert_awaited_once_with("customer-1")
    payment_service.charge.assert_awaited_once_with(
        customer,
        Decimal("25"),
        currency="USD",
        idempotency_key="order-1",
    )


@pytest.mark.parametrize(
    "payment_result",
    [
        False,
        {"success": False},
        {"status": "declined"},
        SimpleNamespace(success=False),
        None,
        {"unexpected": "response"},
    ],
)
@pytest.mark.asyncio
async def test_non_success_payment_results_are_not_reported_as_successful(
    payment_result,
):
    customer = object()
    repository = SimpleNamespace(
        get_customer=AsyncMock(return_value=customer)
    )
    payment_service = SimpleNamespace(
        charge=AsyncMock(return_value=payment_result)
    )
    processor = OrderProcessor(repository, payment_service)
    order = make_order([SimpleNamespace(price=10)])

    result = await processor.process_order(order)

    assert result["success"] is False


@pytest.mark.asyncio
async def test_retries_across_processors_share_provider_idempotency_key():
    customer = object()
    repository = SimpleNamespace(
        get_customer=AsyncMock(return_value=customer)
    )
    payment_service = IdempotentPaymentService()
    first_processor = OrderProcessor(repository, payment_service)
    restarted_processor = OrderProcessor(repository, payment_service)
    order = make_order([SimpleNamespace(price=10)])

    await first_processor.process_order(order)
    await restarted_processor.process_order(order)

    assert payment_service.charge_count == 1
    assert payment_service.attempted_keys == ["order-1", "order-1"]


@pytest.mark.asyncio
async def test_concurrent_processing_uses_provider_idempotency():
    customer = object()
    repository = SimpleNamespace(
        get_customer=AsyncMock(return_value=customer)
    )
    payment_service = IdempotentPaymentService()
    processors = [
        OrderProcessor(repository, payment_service),
        OrderProcessor(repository, payment_service),
    ]
    order = make_order([SimpleNamespace(price=10)])

    await asyncio.gather(
        *(processor.process_order(order) for processor in processors)
    )

    assert payment_service.charge_count == 1
    assert payment_service.attempted_keys == ["order-1", "order-1"]


@pytest.mark.asyncio
async def test_retry_after_ambiguous_timeout_reuses_idempotency_key():
    customer = object()
    repository = SimpleNamespace(
        get_customer=AsyncMock(return_value=customer)
    )
    payment_service = IdempotentPaymentService(timeout_after_first_charge=True)
    processor = OrderProcessor(repository, payment_service)
    order = make_order([SimpleNamespace(price=10)])

    with pytest.raises(TimeoutError):
        await processor.process_order(order)

    result = await processor.process_order(order)

    assert result["success"] is True
    assert payment_service.charge_count == 1
    assert payment_service.attempted_keys == ["order-1", "order-1"]


@pytest.mark.parametrize(
    "price",
    [-1, float("nan"), float("inf"), "not-a-price", True],
)
@pytest.mark.asyncio
async def test_invalid_line_amount_is_rejected_without_charging(price):
    customer = object()
    repository = SimpleNamespace(
        get_customer=AsyncMock(return_value=customer)
    )
    payment_service = SimpleNamespace(charge=AsyncMock())
    processor = OrderProcessor(repository, payment_service)
    order = make_order([SimpleNamespace(price=price)])

    result = await processor.process_order(order)

    assert result["success"] is False
    payment_service.charge.assert_not_awaited()


@pytest.mark.parametrize("quantity", [0, 1.5, True])
@pytest.mark.asyncio
async def test_invalid_line_quantity_is_rejected_without_charging(quantity):
    repository = SimpleNamespace(get_customer=AsyncMock())
    payment_service = SimpleNamespace(charge=AsyncMock())
    processor = OrderProcessor(repository, payment_service)
    order = make_order([SimpleNamespace(price=10, quantity=quantity)])

    result = await processor.process_order(order)

    assert result["success"] is False
    repository.get_customer.assert_not_awaited()
    payment_service.charge.assert_not_awaited()


@pytest.mark.parametrize(
    ("tax_amount", "discount_amount"),
    [(-1, 0), (0, -1)],
)
@pytest.mark.asyncio
async def test_negative_tax_or_discount_is_rejected(tax_amount, discount_amount):
    repository = SimpleNamespace(get_customer=AsyncMock())
    payment_service = SimpleNamespace(charge=AsyncMock())
    processor = OrderProcessor(repository, payment_service)
    order = make_order(
        [SimpleNamespace(price=10)],
        tax_amount=tax_amount,
        discount_amount=discount_amount,
    )

    result = await processor.process_order(order)

    assert result["success"] is False
    repository.get_customer.assert_not_awaited()
    payment_service.charge.assert_not_awaited()


@pytest.mark.asyncio
async def test_total_below_zero_is_rejected_without_fetching_customer():
    repository = SimpleNamespace(get_customer=AsyncMock())
    payment_service = SimpleNamespace(charge=AsyncMock())
    processor = OrderProcessor(repository, payment_service)
    order = make_order(
        [SimpleNamespace(price=10)],
        discount_amount=Decimal("11"),
    )

    result = await processor.process_order(order)

    assert result["success"] is False
    repository.get_customer.assert_not_awaited()
    payment_service.charge.assert_not_awaited()


@pytest.mark.asyncio
async def test_line_quantity_tax_and_discount_are_included_with_decimal_precision():
    customer = object()
    repository = SimpleNamespace(
        get_customer=AsyncMock(return_value=customer)
    )
    payment_service = SimpleNamespace(
        charge=AsyncMock(return_value=True)
    )
    processor = OrderProcessor(repository, payment_service)
    order = make_order(
        [SimpleNamespace(price=0.1, quantity=3),
         SimpleNamespace(price=Decimal("0.10"), quantity=2)],
        tax_amount=Decimal("0.05"),
        discount_amount=Decimal("0.10"),
    )

    result = await processor.process_order(order)

    assert result["success"] is True
    payment_service.charge.assert_awaited_once_with(
        customer,
        Decimal("0.45"),
        currency="USD",
        idempotency_key="order-1",
    )


@pytest.mark.asyncio
async def test_missing_customer_is_not_charged():
    repository = SimpleNamespace(get_customer=AsyncMock(return_value=None))
    payment_service = SimpleNamespace(charge=AsyncMock(return_value=True))
    processor = OrderProcessor(repository, payment_service)
    order = make_order([SimpleNamespace(price=10)])

    result = await processor.process_order(order)

    assert result["success"] is False
    payment_service.charge.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_order_succeeds_without_zero_value_charge():
    customer = object()
    repository = SimpleNamespace(
        get_customer=AsyncMock(return_value=customer)
    )
    payment_service = SimpleNamespace(charge=AsyncMock(return_value=True))
    processor = OrderProcessor(repository, payment_service)
    order = make_order([])

    result = await processor.process_order(order)

    assert result["success"] is True
    payment_service.charge.assert_not_awaited()


@pytest.mark.asyncio
async def test_order_requires_an_id_for_payment_idempotency():
    customer = object()
    repository = SimpleNamespace(
        get_customer=AsyncMock(return_value=customer)
    )
    payment_service = SimpleNamespace(charge=AsyncMock(return_value=True))
    processor = OrderProcessor(repository, payment_service)
    order = make_order([SimpleNamespace(price=10)], id=None)

    result = await processor.process_order(order)

    assert result["success"] is False
    payment_service.charge.assert_not_awaited()
