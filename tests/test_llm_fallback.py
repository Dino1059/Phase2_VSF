"""Wave 2 Task 2.2 — LLM guardrails, fallback telemetry, circuit breaker."""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest
import urllib.error

from src.services.llm import (
    LLMResponse,
    UnifiedLLMAdapter,
    reset_provider_circuits,
    _circuit_is_open,
    _circuit_record_failure,
    _PROVIDER_CIRCUIT,
)
from src.services.llm_guardrails import GuardVerdict, post_llm_guard, pre_llm_guard


@pytest.fixture(autouse=True)
def _clear_circuits():
    reset_provider_circuits()
    yield
    reset_provider_circuits()


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="https://example.test",
        code=code,
        msg="err",
        hdrs=None,
        fp=None,
    )


def test_pre_llm_guard_rejects_absurd_chat_body():
    huge = "x" * 200_000
    v = pre_llm_guard(huge, task_type="chat")
    assert isinstance(v, GuardVerdict)
    assert v.allowed is False


def test_pre_llm_guard_trims_evidence_without_reject():
    huge = "e" * 200_000
    v = pre_llm_guard(huge, task_type="evidence")
    assert v.allowed is True
    assert v.trimmed is True


def test_post_llm_guard_requires_keys_and_confidence():
    bad = post_llm_guard({"foo": 1}, required_keys=["diagnosis"])
    assert bad.allowed is False
    ok = post_llm_guard(
        {"diagnosis": "ok", "confidence": 0.8, "evidence_ids": ["ev_1"]},
        required_keys=["diagnosis"],
    )
    assert ok.allowed is True


def test_503_first_provider_falls_back_to_second():
    called = []

    def boom(*_a, **_k):
        called.append("openrouter")
        raise _http_error(503)

    def ok(*_a, **_k):
        called.append("gemini")
        return LLMResponse(content="from-gemini", model_used="gemini-test", tokens_used=3)

    with patch.dict(
        os.environ,
        {
            "LLM_PROVIDER": "openrouter",
            "USE_LLM": "true",
            "OPENROUTER_API_KEY": "sk-or-test-key",
            "GOOGLE_AI_API_KEY": "gemini-test-key",
        },
        clear=False,
    ):
        svc = UnifiedLLMAdapter(use_llm=True)
        # Force keys regardless of placeholders
        svc.openrouter_key = "sk-or-real-test"
        svc._google_keys = type(svc._google_keys)(["gemini-real-key"])
        with patch.object(svc, "_call_openrouter", side_effect=boom), patch.object(
            svc, "_call_gemini", side_effect=ok
        ), patch.object(svc, "_check_ollama", return_value=False):
            # Preferred openrouter order: openrouter, gemini, ...
            svc.preferred_provider = "auto"
            resp = svc.chat([{"role": "user", "content": "hi"}])

    assert called == ["openrouter", "gemini"]
    assert resp.content == "from-gemini"
    assert resp.provider == "gemini"
    assert resp.fallback_depth >= 1
    assert any(a.get("provider") == "openrouter" and a.get("result") == "error" for a in resp.provider_attempts)


def test_open_provider_skipped_within_30s():
    _circuit_record_failure("openrouter", status_code=503)
    assert _circuit_is_open("openrouter") is True

    called = []

    def should_not(*_a, **_k):
        called.append("openrouter")
        return LLMResponse(content="should-not")

    def ok(*_a, **_k):
        called.append("gemini")
        return LLMResponse(content="ok", model_used="g")

    with patch.dict(os.environ, {"USE_LLM": "true"}, clear=False):
        svc = UnifiedLLMAdapter(use_llm=True)
        svc.openrouter_key = "sk-or-real-test"
        svc._google_keys = type(svc._google_keys)(["gemini-real-key"])
        svc.preferred_provider = "auto"
        with patch.object(svc, "_call_openrouter", side_effect=should_not), patch.object(
            svc, "_call_gemini", side_effect=ok
        ), patch.object(svc, "_check_ollama", return_value=False):
            resp = svc.chat([{"role": "user", "content": "hi"}])

    assert "openrouter" not in called
    assert called == ["gemini"]
    assert any(a.get("result") == "skipped_open" for a in resp.provider_attempts)
    assert _PROVIDER_CIRCUIT["openrouter"]["state"] == "OPEN"


def test_llm_provider_off_heuristic_without_raise():
    with patch.dict(os.environ, {"LLM_PROVIDER": "off", "USE_LLM": "true"}, clear=False):
        svc = UnifiedLLMAdapter(use_llm=True)
        assert svc.use_llm is False
        resp = svc.chat([{"role": "user", "content": "hello there"}])
    assert resp.reasoning_mode == "heuristic" or resp.model_used.startswith("heuristic")
    assert isinstance(resp.content, str)
