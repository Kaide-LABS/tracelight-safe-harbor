import logging
import uuid
import time
import json
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        trace_id = str(uuid.uuid4())[:8]
        request.state.trace_id = trace_id
        start = time.time()

        logger = logging.getLogger("tracelight")
        logger.info(json.dumps({
            "event": "request_start",
            "trace_id": trace_id,
            "method": request.method,
            "path": request.url.path,
        }))

        response = await call_next(request)
        duration_ms = int((time.time() - start) * 1000)

        logger.info(json.dumps({
            "event": "request_end",
            "trace_id": trace_id,
            "status": response.status_code,
            "duration_ms": duration_ms,
        }))

        response.headers["X-Trace-ID"] = trace_id
        return response
