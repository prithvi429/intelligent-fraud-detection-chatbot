"""
Request/Response Logging Middleware
-----------------------------------
Logs every API request and response in structured JSON format.

Features:
- Captures method, path, user_id (from JWT), latency, and status code
- Masks sensitive fields (PII) automatically
- Async-safe and lightweight (for FastAPI / Starlette)
- Compatible with CloudWatch, ELK, or Datadog ingestion
- Skips health check & docs routes for noise reduction
"""

import time
import json
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from src.utils.logger import logger
from src.utils.security import verify_jwt_token
from src.config import config


class LoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, redact_pii: bool = True):
        super().__init__(app)
        self.redact_pii = redact_pii

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        path = request.url.path
        method = request.method
        trace_id = str(uuid.uuid4())  # Unique per request
        user_id = "anonymous"

        # Skip noisy or non-business-critical endpoints
        skip_paths = ["/health", "/docs", "/openapi.json", "/favicon.ico"]
        if any(path.startswith(skip) for skip in skip_paths):
            return await call_next(request)

        try:
            # Try to extract JWT user_id if available
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
                payload = verify_jwt_token(token)
                if payload:
                    user_id = payload.get("sub", "unknown")

            # Capture query parameters
            params = dict(request.query_params)
            if self.redact_pii:
                params = self._mask_sensitive(params)

            # Capture request body (non-blocking, async safe)
            body_bytes = await request.body()
            content_length = len(body_bytes) if body_bytes else 0

            # Log request start
            logger.info(
                json.dumps({
                    "trace_id": trace_id,
                    "event": "request_start",
                    "timestamp": time.time(),
                    "method": method,
                    "path": path,
                    "user_id": user_id,
                    "client_ip": request.client.host if request.client else "unknown",
                    "user_agent": request.headers.get("user-agent", "unknown"),
                    "params": params,
                    "content_length": content_length,
                }, default=str)
            )

            # Process request
            response: Response = await call_next(request)
            latency_ms = round((time.time() - start_time) * 1000, 2)

            # Log response completion
            logger.info(
                json.dumps({
                    "trace_id": trace_id,
                    "event": "request_end",
                    "timestamp": time.time(),
                    "method": method,
                    "path": path,
                    "status_code": response.status_code,
                    "user_id": user_id,
                    "latency_ms": latency_ms,
                    "response_size": int(response.headers.get("content-length", 0)),
                    **({"response_headers": dict(response.headers)} if config.DEBUG else {}),
                }, default=str)
            )

            return response

        except Exception as e:
            # Catch & log errors but re-raise to FastAPI
            latency_ms = round((time.time() - start_time) * 1000, 2)
            logger.error(
                json.dumps({
                    "trace_id": trace_id,
                    "event": "request_error",
                    "timestamp": time.time(),
                    "method": method,
                    "path": path,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "user_id": user_id,
                    "latency_ms": latency_ms,
                    "client_ip": request.client.host if request.client else "unknown",
                }, default=str)
            )
            raise e

    # --------------------------
    # Internal helpers
    # --------------------------
    def _mask_sensitive(self, params: dict) -> dict:
        """Mask sensitive query parameters."""
        masked = {}
        for key, val in params.items():
            if any(x in key.lower() for x in ("id", "token", "email", "ssn")):
                masked[key] = "[REDACTED]"
            else:
                masked[key] = val
        return masked
