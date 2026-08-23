class PaymentService:

    def process_payment(
        self,
        db,
        order_id: int,
        amount: float
    ) -> str:
        # Simulated payment processing
        # Fails for negative amounts or sentinel failure amounts (e.g. 9999.0)
        if amount <= 0 or amount == 9999.0:
            return "FAILED"

        return "COMPLETED"


payment_service = PaymentService()
