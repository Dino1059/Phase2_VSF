from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

REDACTED = "[REDACTED]"
MAX_VALUE_LENGTH = 2000
SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "password",
    "refresh_token",
    "secret",
    "token",
}
_URL_SECRET_RE = re.compile(r"([?&](?:key|api_key|token|password)=)[^&\s]+", re.IGNORECASE)


def redact_text(value: str) -> str:
    value = _URL_SECRET_RE.sub(r"\1" + REDACTED, value)
    if len(value) > MAX_VALUE_LENGTH:
        return value[:MAX_VALUE_LENGTH] + "…"
    return value


def redact(value: Any, *, key: str | None = None) -> Any:
    if key and key.lower() in SENSITIVE_KEYS:
        return REDACTED
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Mapping):
        return {str(k): redact(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    return value
