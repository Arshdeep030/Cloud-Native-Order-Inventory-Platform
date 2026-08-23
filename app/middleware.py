import logging
import time
import uuid

from fastapi import Request


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

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

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