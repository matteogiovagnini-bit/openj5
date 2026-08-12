"""
OpenJ5 Robot Core - Logging Service

Structured JSON logging with correlation IDs, log levels, and multiple outputs.
"""

import sys
import structlog
from structlog.stdlib import LoggerFactory
from structlog.processors import JSONRenderer, TimeStamper, add_log_level
from structlog.contextvars import merge_contextvars
import logging
import logging.handlers
from typing import Any


def setup_logging(config: dict | None = None) -> None:
    """Configure structured logging."""
    
    config = config or {}
    
    # Processors for structlog
    processors = [
        merge_contextvars,
        add_log_level,
        TimeStamper(fmt="iso", utc=True),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        JSONRenderer(),
    ]
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure stdlib logging
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger.addHandler(console_handler)
    
    # File handler with rotation
    if config.get("file_enabled", True):
        file_handler = logging.handlers.RotatingFileHandler(
            filename=config.get("file_path", "/var/log/openj5/robot_core.jsonl"),
            maxBytes=config.get("max_bytes", 10_000_000),
            backupCount=config.get("backup_count", 5),
        )
        file_handler.setFormatter(logging.Formatter("%(message)s"))
        root_logger.addHandler(file_handler)
    
    # Loki handler (optional)
    if config.get("loki_enabled", False):
        try:
            import logging_loki
            loki_handler = logging_loki.LokiHandler(
                url=config.get("loki_url", "http://loki:3100/loki/api/v1/push"),
                tags={"application": "openj5-robot-core"},
                version="1",
            )
            root_logger.addHandler(loki_handler)
        except ImportError:
            pass
    
    # Set log level
    level = config.get("level", "INFO").upper()
    root_logger.setLevel(getattr(logging, level, logging.INFO))
    
    # Silence noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("watchdog").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get structured logger instance."""
    return structlog.get_logger(name)


class CorrelationIDMiddleware:
    """Middleware to add correlation ID to log context."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        import uuid
        correlation_id = scope.get("headers", {}).get(b"x-correlation-id", uuid.uuid4().hex)
        
        with structlog.contextvars.bound_contextvars(correlation_id=correlation_id):
            await self.app(scope, receive, send)


# Convenience functions
def log_info(logger: structlog.stdlib.BoundLogger, event: str, **kwargs: Any) -> None:
    logger.info(event, **kwargs)


def log_error(logger: structlog.stdlib.BoundLogger, event: str, error: Exception = None, **kwargs: Any) -> None:
    if error:
        kwargs["error_type"] = type(error).__name__
        kwargs["error_message"] = str(error)
    logger.error(event, **kwargs)


def log_warning(logger: structlog.stdlib.BoundLogger, event: str, **kwargs: Any) -> None:
    logger.warning(event, **kwargs)


def log_debug(logger: structlog.stdlib.BoundLogger, event: str, **kwargs: Any) -> None:
    logger.debug(event, **kwargs)