from __future__ import annotations

from contextvars import ContextVar, Token

_context: ContextVar[dict[str, str]] = ContextVar("datatrust_log_context", default={})


def bind_context(**values: str | None) -> Token[dict[str, str]]:
    current = dict(_context.get())
    current.update({key: value for key, value in values.items() if value})
    return _context.set(current)


def reset_context(token: Token[dict[str, str]]) -> None:
    _context.reset(token)


def get_context() -> dict[str, str]:
    return dict(_context.get())
