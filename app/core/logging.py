"""
Structured logging configuration
──────────────────────────────────
Produces JSON log lines in production (APP_ENV=production) for easy
ingestion by log aggregators. Reverts to human-readable format in development.

Each log record contains:
  timestamp, level, logger, message
  + any extra fields added via logger.info("msg", extra={...})
"""

import json
import logging
import sys
import uuid


class _JsonFormatter(logging.Formatter):
    """Render log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # Include any extra fields attached by the caller
        skip = {
            "name", "msg", "args", "levelname", "levelno", "pathname",
            "filename", "module", "exc_info", "exc_text", "stack_info",
            "lineno", "funcName", "created", "msecs", "relativeCreated",
            "thread", "threadName", "processName", "process", "message",
            "taskName",
        }
        for key, val in record.__dict__.items():
            if key not in skip:
                payload[key] = val
        return json.dumps(payload, default=str)


def configure_logging(app_env: str = "development") -> None:
    """
    Configure root logger.
    JSON output in production; plain text in development.
    """
    handler = logging.StreamHandler(sys.stdout)

    if app_env == "production":
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    # Quiet noisy third-party loggers
    for noisy in ("httpx", "httpcore", "urllib3", "pinecone"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
