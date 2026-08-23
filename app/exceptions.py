class AppException(Exception):
    """Base exception for errors caused by application business rules."""

    def __init__(self, code: str, message: str, status_code: int):
        self.code = code
        self.message = message
        self.status_code = status_code

        super().__init__(message)


class ProductNotFoundError(AppException):

    def __init__(self, product_id: int):
        super().__init__(
            code="PRODUCT_NOT_FOUND",
            message=f"Product {product_id} was not found",
            status_code=404
        )


class InsufficientInventoryError(AppException):

    def __init__(self, product_id: int):
        super().__init__(
            code="INSUFFICIENT_INVENTORY",
            message=f"Insufficient inventory for product {product_id}",
            status_code=409
        )


class OrderNotFoundError(AppException):

    def __init__(self, order_id: int):
        super().__init__(
            code="ORDER_NOT_FOUND",
            message=f"Order {order_id} was not found",
            status_code=404
        )
