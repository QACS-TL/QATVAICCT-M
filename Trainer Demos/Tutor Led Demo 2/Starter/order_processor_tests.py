from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from order_processor import OrderProcessor


@pytest.mark.asyncio
async def test_successful_order_processing():
    customer = object()
    repository = SimpleNamespace(
        get_customer=AsyncMock(return_value=customer)
    )
    payment_service = SimpleNamespace(charge=AsyncMock())
    processor = OrderProcessor(repository, payment_service)
    order = SimpleNamespace(
        customer_id="customer-1",
        lines=[
            SimpleNamespace(price=10),
            SimpleNamespace(price=15),
        ],
    )

    result = await processor.process_order(order)

    assert result["success"] is True
    repository.get_customer.assert_awaited_once_with("customer-1")
    payment_service.charge.assert_awaited_once_with(customer, 25)