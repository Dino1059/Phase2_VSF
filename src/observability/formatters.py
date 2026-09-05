from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from .context import get_context
from .redaction import redact, redact_text


class DataTrustJsonFormatter(logging.Formatter):
    """Emit one searchable, redacted JSON object per runtime log record."""

    _standard_fields = set(logging.LogRecord(None, 0, "", 0, "", (), None).__dict__)

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_text(record.getMessage()),
            **get_context(),
        }
        for key, value in record.__dict__.items():
            if key not in self._standard_fields and key not in {"message", "asctime"}:
                payload[key] = redact(value, key=key)
        if record.exc_info:
            payload["exception"] = redact_text(self.formatException(record.exc_info))
        return json.dumps(redact(payload), ensure_ascii=False, default=str)
