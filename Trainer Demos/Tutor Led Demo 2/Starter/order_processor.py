class OrderProcessor:

    def __init__(
        self,
        repository,
        payment_service
    ):
        self.repository = repository
        self.payment_service = payment_service

    async def process_order(self, order):

        customer = (
            await self.repository
                .get_customer(
                    order.customer_id
                )
        )

        total = sum(
            line.price
            for line in order.lines
        )

        await self.payment_service.charge(
            customer,
            total
        )

        return {
            "success": True
        }