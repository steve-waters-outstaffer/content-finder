"""Centralized structured logging configuration for the backend."""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict

__all__ = ["configure_logging", "GCPJSONFormatter"]

_LOGGING_CONFIGURED = False


class GCPJSONFormatter(logging.Formatter):
    """Render log records as JSON for compatibility with GCP Cloud Logging."""

    _RESERVED_ATTRS = {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
    }

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401 - default docstring is sufficient
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        log_entry: Dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "function": record.funcName,
            "message": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key in self._RESERVED_ATTRS:
                continue
            if key == "exc_info" and value:
                continue
            log_entry[key] = value

        if record.exc_info:
            log_entry["error"] = self.formatException(record.exc_info)
        if record.stack_info:
            log_entry["stack"] = record.stack_info

        return json.dumps(log_entry, default=str, ensure_ascii=False)


def configure_logging() -> None:
    """Configure root logging handler for structured JSON output."""

    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = logging.getLevelName(log_level_name)
    if isinstance(log_level, str):  # getLevelName returns name for unknown inputs
        log_level = logging.INFO

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(GCPJSONFormatter())
    root_logger.addHandler(handler)

    logging.captureWarnings(True)

    _LOGGING_CONFIGURED = True
