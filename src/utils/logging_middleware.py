"""
Logging Middleware
------------------
FastAPI middleware for structured request/response logging.

Features:
- Logs every incoming request and its corresponding response.
- Measures latency for performance insights.
- Outputs JSON-style logs for CloudWatch / ELK compatibility.
- Integrates with the global logger (`src.utils.logger`).

Usage:
    from src.utils.logging_middleware import LoggingMiddleware
    app.add_middleware(LoggingMiddleware)
"""

import json
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp
from typing import Optional
from src.utils.logger import logger


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for centralized structured API logging.
    """

    def __init__(self, app: ASGIApp, skip_paths: Optional[list[str]] = None):
        super().__init__(app)
        self.skip_paths = skip_paths or ["/health", "/metrics"]

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Log request start, completion, and response metadata.
        """
        if any(request.url.path.startswith(p) for p in self.skip_paths):
            # Skip health checks to avoid log noise
            return await call_next(request)

        start_time = time.perf_counter()
        request_id = request.headers.get("X-Request-ID", str(int(time.time() * 1000)))

        log_entry = {
            "event": "request_start",
            "method": request.method,
            "path": request.url.path,
            "query_params": str(request.query_params),
            "client_host": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("User-Agent", "unknown"),
            "request_id": request_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        logger.info(json.dumps(log_entry))

        try:
            response: Response = await call_next(request)
            latency = round((time.perf_counter() - start_time) * 1000, 2)

            response_log = {
                "event": "request_end",
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "latency_ms": latency,
                "content_length": response.headers.get("content-length", "unknown"),
                "request_id": request_id,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }

            logger.info(json.dumps(response_log))
            return response

        except Exception as e:
            # Catch and log any unhandled exceptions
            latency = round((time.perf_counter() - start_time) * 1000, 2)
            error_log = {
                "event": "request_error",
                "method": request.method,
                "path": request.url.path,
                "error": str(e),
                "latency_ms": latency,
                "request_id": request_id,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            logger.error(json.dumps(error_log))
            raise e


# =========================================================
# Example Integration (in src/main.py)
# =========================================================
# from fastapi import FastAPI
# from src.utils.logging_middleware import LoggingMiddleware
#
# app = FastAPI()
# app.add_middleware(LoggingMiddleware)
#
# @app.get("/ping")
# async def ping():
#     return {"status": "ok"}
