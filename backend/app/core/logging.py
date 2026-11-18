"""Structured JSON logging.

Rule: log events and IDs only. Never log request bodies, passwords, tokens,
email addresses or health content. Exceptions are logged by type name only,
because driver messages can embed user data (e.g. duplicate-key errors).
"""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

_logger = logging.getLogger("healthai")
if not _logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False


def _write(level: int, event: str, **fields: Any) -> None:
    payload = {"level": logging.getLevelName(level).lower(), "event": event, "time": datetime.now(UTC).isoformat()}
    payload.update({k: v for k, v in fields.items() if v is not None})
    _logger.log(level, json.dumps(payload, default=str))


def log_info(event: str, **fields: Any) -> None:
    _write(logging.INFO, event, **fields)


def log_warning(event: str, **fields: Any) -> None:
    _write(logging.WARNING, event, **fields)


def log_error(event: str, exc: BaseException | None = None, **fields: Any) -> None:
    if exc is not None:
        fields["error_type"] = type(exc).__name__
        code = getattr(exc, "code", None)
        if isinstance(code, (int, str)):
            fields["error_code"] = code
    _write(logging.ERROR, event, **fields)
