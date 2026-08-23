from prometheus_client import Counter, Histogram


HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status"],
)


HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
)


ORDERS_CREATED_TOTAL = Counter(
    "orders_created_total",
    "Total number of orders created",
)


ORDERS_FAILED_TOTAL = Counter(
    "orders_failed_total",
    "Total number of failed orders",
)


PRODUCTS_CREATED_TOTAL = Counter(
    "products_created_total",
    "Total number of products created",
)
