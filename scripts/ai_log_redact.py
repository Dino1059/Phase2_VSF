"""Redact secrets and emails from course AI-usage log payloads.

Shared by scripts/log_*.py writers and scripts/submit_log.py (defense in depth).
Matches are replaced with stable tokens. Raw secrets are never printed or logged.
"""
from __future__ import annotations

import re
from typing import Any

# Routing / identity fields keep emails (student attribution on the ingest
# server) but still lose key-like material if it ever lands here.
_IDENTITY_KEYS = frozenset(
    {
        "ts",
        "tool",
        "event",
        "entry_id",
        "session_id",
        "model",
        "repo",
        "branch",
        "commit",
        "project_id",
        "turn_id",
        "transcript_path",
        "student",
    }
)

_PEM_RE = re.compile(
    r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----"
    r".*?"
    r"-----END (?:[A-Z]+ )?PRIVATE KEY-----",
    re.DOTALL,
)

_BEARER_RE = re.compile(
    r"\bBearer\s+[A-Za-z0-9._\-+/=]{8,}",
    re.IGNORECASE,
)

# Require enough body that "sk-learn" / short words do not match.
_SK_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{20,}")

_GITHUB_RE = re.compile(
    r"\b(?:ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"
)

_AWS_RE = re.compile(r"\bAKIA[0-9A-Z]{16}\b")

_SLACK_RE = re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")

# Cloudflare tunnel tokens are JWTs that typically start eyJhIjoi
_CF_TUNNEL_RE = re.compile(r"\beyJhIjoi[A-Za-z0-9+/=_-]{20,}")

_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")

_ENV_ASSIGN_RE = re.compile(
    r"(?i)(\b(?:export\s+)?[A-Za-z_][A-Za-z0-9_]*"
    r"(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*)"
    r"(\s*[=:]\s*)"
    r"([\"']?)"
    r"([^\s\"'#]+)"
    r"(\3)"
)

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")


def _env_sub(match: re.Match[str]) -> str:
    return (
        f"{match.group(1)}{match.group(2)}{match.group(3)}"
        f"[REDACTED:secret]{match.group(5)}"
    )


def _email_sub(match: re.Match[str]) -> str:
    text = match.group(0)
    end = match.end()
    src = match.string
    # git@github.com:org/repo — SSH remote, not an email.
    if end < len(src) and src[end] == ":":
        return text
    return "[REDACTED:email]"


def redact_text(text: str, *, emails: bool = True) -> str:
    """Return text with secrets/emails replaced by stable tokens."""
    if not text:
        return text
    out = _PEM_RE.sub("[REDACTED:pem]", text)
    out = _BEARER_RE.sub("[REDACTED:token]", out)
    out = _SK_RE.sub("[REDACTED:api_key]", out)
    out = _GITHUB_RE.sub("[REDACTED:token]", out)
    out = _AWS_RE.sub("[REDACTED:api_key]", out)
    out = _SLACK_RE.sub("[REDACTED:token]", out)
    out = _CF_TUNNEL_RE.sub("[REDACTED:token]", out)
    out = _JWT_RE.sub("[REDACTED:jwt]", out)
    out = _ENV_ASSIGN_RE.sub(_env_sub, out)
    if emails:
        out = _EMAIL_RE.sub(_email_sub, out)
    return out


def redact_obj(obj: Any, *, _key: str | None = None) -> Any:
    """Recursively redact strings in JSON-compatible structures.

    Dict keys and non-string scalars are unchanged so the ingest shape stays
    compatible. Identity fields skip email redaction only.
    """
    if isinstance(obj, str):
        return redact_text(obj, emails=_key not in _IDENTITY_KEYS)
    if isinstance(obj, dict):
        return {k: redact_obj(v, _key=k) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_obj(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(redact_obj(v) for v in obj)
    return obj
