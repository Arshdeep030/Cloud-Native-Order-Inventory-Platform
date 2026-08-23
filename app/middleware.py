import logging
import time
import uuid

from fastapi import Request

from app.metrics import HTTP_REQUESTS_TOTAL, HTTP_REQUEST_DURATION_SECONDS


logger = logging.getLogger("cloud-order-platform.http")


async def request_logging_middleware(
    request: Request,
    call_next
):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    correlation_id = request.headers.get("X-Correlation-ID") or request_id

    request.state.request_id = request_id
    request.state.correlation_id = correlation_id

    start_time = time.perf_counter()

    response = await call_next(request)

    duration_s = time.perf_counter() - start_time
    duration_ms = round(duration_s * 1000, 2)

    # Record Prometheus Metrics
    endpoint = request.url.path
    HTTP_REQUESTS_TOTAL.labels(
        method=request.method,
        endpoint=endpoint,
        status=str(response.status_code)
    ).inc()

    HTTP_REQUEST_DURATION_SECONDS.labels(
        method=request.method,
        endpoint=endpoint
    ).observe(duration_s)

    logger.info(
        f"{request.method} {request.url.path} responded {response.status_code} in {duration_ms}ms",
        extra={
            "request_id": request_id,
            "correlation_id": correlation_id,
            "event": "http_request",
            "extra_data": {
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms
            }
        }
    )

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Correlation-ID"] = correlation_id

    return response