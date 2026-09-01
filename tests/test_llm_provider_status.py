"""LLM provider availability — backend status shape used by frontend provider-off UX."""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest


def _provider_available(status: dict) -> bool:
    """Mirror frontend isLlmProviderAvailable() for contract tests."""
    if not status:
        return False
    if status.get("status") in ("offline", "disabled"):
        return False
    if not status.get("has_api_key"):
        return False
    return status.get("provider") != "heuristic"


@pytest.mark.parametrize(
    "status,expected",
    [
        ({"status": "disabled", "provider": "heuristic", "has_api_key": False}, False),
        ({"status": "offline", "provider": "heuristic", "has_api_key": False}, False),
        ({"status": "online", "provider": "heuristic", "has_api_key": False}, False),
        ({"status": "online", "provider": "gemini", "has_api_key": True}, True),
        ({"status": "fallback_ready", "provider": "openrouter", "has_api_key": True}, True),
    ],
)
def test_llm_provider_available_contract(status, expected):
    assert _provider_available(status) is expected


def test_llm_service_get_status_disabled():
    from src.services.llm import LLMService

    with patch.dict(os.environ, {"USE_LLM": "false"}, clear=False):
        svc = LLMService()
        st = svc.get_status()
    assert st["status"] == "disabled"
    assert st["provider"] == "heuristic"
    assert _provider_available(st) is False
