"""
Structured logging service for CICosts API.

Outputs JSON-formatted logs for CloudWatch with:
- Request IDs for correlation
- User/org context
- Timing information
- Error details with stack traces

Usage:
    from app.services.logging_service import get_logger, log_request

    logger = get_logger(__name__)
    logger.info("Processing webhook", extra={"org_id": org.id, "event": "workflow_run"})
"""
import json
import logging
import sys
import time
import traceback
import uuid
from contextvars import ContextVar
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Context variable for request ID
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar("user_id", default=None)
org_id_var: ContextVar[Optional[str]] = ContextVar("org_id", default=None)


class JSONFormatter(logging.Formatter):
    """
    JSON log formatter for CloudWatch.

    Outputs structured JSON with consistent fields for easy parsing.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
        }

        # Add user/org context if available
        user_id = user_id_var.get()
        org_id = org_id_var.get()
        if user_id:
            log_data["user_id"] = user_id
        if org_id:
            log_data["org_id"] = org_id

        # Add extra fields from the log record
        if hasattr(record, "__dict__"):
            for key, value in record.__dict__.items():
                if key not in (
                    "name", "msg", "args", "created", "filename", "funcName",
                    "levelname", "levelno", "lineno", "module", "msecs",
                    "pathname", "process", "processName", "relativeCreated",
                    "stack_info", "exc_info", "exc_text", "message", "thread",
                    "threadName", "taskName",
                ):
                    # Serialize non-primitive types
                    if isinstance(value, (dict, list, tuple)):
                        log_data[key] = value
                    elif hasattr(value, "__str__"):
                        log_data[key] = str(value)

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info),
            }

        return json.dumps(log_data, default=str)


def configure_logging(level: str = "INFO", json_format: bool = True) -> None:
    """
    Configure logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        json_format: Use JSON formatting (for CloudWatch)
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level.upper()))

    # Set formatter
    if json_format:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(levelname)s - %(name)s - %(message)s")
        )

    root_logger.addHandler(handler)

    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the given name.

    The logger will automatically include request context.
    """
    return logging.getLogger(name)


def set_request_context(
    request_id: Optional[str] = None,
    user_id: Optional[str] = None,
    org_id: Optional[str] = None,
) -> None:
    """Set context variables for logging."""
    if request_id:
        request_id_var.set(request_id)
    if user_id:
        user_id_var.set(user_id)
    if org_id:
        org_id_var.set(org_id)


def clear_request_context() -> None:
    """Clear context variables."""
    request_id_var.set(None)
    user_id_var.set(None)
    org_id_var.set(None)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log requests and set context.

    Logs:
    - Request start with method, path, client IP
    - Request end with status code and duration
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Set context for logging
        set_request_context(request_id=request_id)

        # Extract user/org from query params (if present)
        org_id = request.query_params.get("org_id")
        if org_id:
            org_id_var.set(org_id)

        # Log request start
        logger = get_logger("request")
        start_time = time.time()

        logger.info(
            "Request started",
            extra={
                "method": request.method,
                "path": str(request.url.path),
                "query": str(request.url.query) if request.url.query else None,
                "client_ip": request.client.host if request.client else None,
            },
        )

        try:
            response = await call_next(request)

            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Log request end
            logger.info(
                "Request completed",
                extra={
                    "method": request.method,
                    "path": str(request.url.path),
                    "status_code": response.status_code,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Log error
            logger.error(
                "Request failed",
                extra={
                    "method": request.method,
                    "path": str(request.url.path),
                    "duration_ms": round(duration_ms, 2),
                    "error": str(e),
                },
                exc_info=True,
            )
            raise

        finally:
            # Clear context
            clear_request_context()


def log_operation(operation: str):
    """
    Decorator to log function execution with timing.

    Usage:
        @log_operation("process_webhook")
        def process_webhook(payload):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            logger = get_logger(func.__module__)
            start_time = time.time()

            logger.info(f"{operation} started", extra={"operation": operation})

            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000

                logger.info(
                    f"{operation} completed",
                    extra={
                        "operation": operation,
                        "duration_ms": round(duration_ms, 2),
                    },
                )
                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.error(
                    f"{operation} failed",
                    extra={
                        "operation": operation,
                        "duration_ms": round(duration_ms, 2),
                        "error": str(e),
                    },
                    exc_info=True,
                )
                raise

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            logger = get_logger(func.__module__)
            start_time = time.time()

            logger.info(f"{operation} started", extra={"operation": operation})

            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000

                logger.info(
                    f"{operation} completed",
                    extra={
                        "operation": operation,
                        "duration_ms": round(duration_ms, 2),
                    },
                )
                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.error(
                    f"{operation} failed",
                    extra={
                        "operation": operation,
                        "duration_ms": round(duration_ms, 2),
                        "error": str(e),
                    },
                    exc_info=True,
                )
                raise

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
