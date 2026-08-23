import logging
import time
import uuid

from fastapi import Request


logger = logging.getLogger("cloud-order-platform")


async def request_logging_middleware(
    request: Request,
    call_next
):

    request_id = request.headers.get(
        "X-Request-ID"
    )

    if not request_id:
        request_id = str(uuid.uuid4())

    request.state.request_id = request_id

    start_time = time.perf_counter()

    response = await call_next(request)

    duration = (
        time.perf_counter() - start_time
    )

    logger.info(
        "request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration * 1000
    )

    response.headers["X-Request-ID"] = request_id

    return response