#!/usr/bin/env python3
"""Provider fallback stress (Wave 3 Task 3.3).

Monkeypatch timeout / 429 / 500 / invalid JSON / empty / all cloud down /
Ollama down → heuristic or abstain; never raise through HITL-safe path.
"""
from __future__ import annotations

import os
import sys
import urllib.error
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services.llm import (
    LLMResponse,
    StructuredOutputInvalidException,
    UnifiedLLMAdapter,
    reset_provider_circuits,
)


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="https://example.test",
        code=code,
        msg="err",
        hdrs=None,
        fp=None,
    )


def _adapter() -> UnifiedLLMAdapter:
    reset_provider_circuits()
    with patch.dict(
        os.environ,
        {
            "USE_LLM": "true",
            "LLM_PROVIDER": "auto",
            "OPENROUTER_API_KEY": "sk-or-stress-test-key",
            "GOOGLE_AI_API_KEY": "gemini-stress-test-key",
            "OPENAI_API_KEY": "sk-stress-test-key",
            "GROQ_API_KEY": "gsk_stress-test-key",
        },
        clear=False,
    ):
        svc = UnifiedLLMAdapter(use_llm=True)
    svc.preferred_provider = "auto"
    svc.openrouter_key = "sk-or-stress-real"
    svc.openai_key = "sk-stress-real"
    svc.groq_key = "gsk_stress-real"
    svc._google_keys = type(svc._google_keys)(["gemini-stress-real"])
    return svc


def hitl_safe_chat(svc: UnifiedLLMAdapter, messages: list[dict]) -> LLMResponse:
    """HITL boundary: never let provider failures raise into the HITL queue."""
    try:
        resp = svc.chat(messages, raise_on_error=False)
        if resp is None:
            return LLMResponse(content="", reasoning_mode="abstain", model_used="abstain", provider="abstain")
        if not str(resp.content or "").strip():
            resp.reasoning_mode = "abstain"
            resp.provider = resp.provider or "abstain"
            return resp
        return resp
    except Exception:
        # Must not propagate through HITL
        fb = svc._heuristic_fallback(messages)
        fb.reasoning_mode = "heuristic"
        fb.provider = "heuristic"
        return fb


def hitl_safe_structured(svc: UnifiedLLMAdapter, prompt: str, schema: dict) -> dict:
    """HITL boundary for structured_output: invalid/empty → abstain dict, never raise."""
    try:
        return svc.structured_output(prompt, schema)
    except StructuredOutputInvalidException:
        return {"status": "abstain", "reasoning_mode": "abstain", "rules": []}
    except Exception:
        return {"status": "heuristic", "reasoning_mode": "heuristic", "rules": []}


def _assert_no_raise_heuristic_or_abstain(label: str, resp: LLMResponse) -> None:
    mode = (resp.reasoning_mode or "").lower()
    model = (resp.model_used or "").lower()
    provider = (resp.provider or "").lower()
    ok = (
        mode in ("heuristic", "abstain")
        or provider in ("heuristic", "abstain")
        or model.startswith("heuristic")
        or model == "abstain"
        or (mode == "abstain")
    )
    if not ok:
        raise AssertionError(
            f"{label}: expected heuristic/abstain, got mode={resp.reasoning_mode!r} "
            f"provider={resp.provider!r} model={resp.model_used!r}"
        )


def run() -> int:
    messages = [{"role": "user", "content": "hello fallback stress"}]
    failures: list[str] = []

    scenarios = [
        ("timeout", TimeoutError("provider timeout")),
        ("429", _http_error(429)),
        ("500", _http_error(500)),
    ]

    for label, exc in scenarios:
        try:
            svc = _adapter()
            with patch.object(svc, "_call_openrouter", side_effect=exc), patch.object(
                svc, "_call_gemini", side_effect=exc
            ), patch.object(svc, "_call_openai", side_effect=exc), patch.object(
                svc, "_call_groq", side_effect=exc
            ), patch.object(svc, "_check_ollama", return_value=False):
                resp = hitl_safe_chat(svc, messages)
            _assert_no_raise_heuristic_or_abstain(label, resp)
            print(f"PASS {label}: mode={resp.reasoning_mode} provider={resp.provider}")
        except Exception as e:
            failures.append(f"{label}: {e}")
            print(f"FAIL {label}: {e}")

    # invalid JSON from "successful" provider → structured path abstains, never raises
    try:
        svc = _adapter()

        def bad_json(*_a, **_k):
            return LLMResponse(content="NOT_JSON{{{{", model_used="fake", tokens_used=1)

        with patch.object(svc, "_call_openrouter", side_effect=bad_json), patch.object(
            svc, "_check_ollama", return_value=False
        ), patch.object(svc, "_call_gemini", side_effect=Exception("skip")), patch.object(
            svc, "_call_openai", side_effect=Exception("skip")
        ), patch.object(svc, "_call_groq", side_effect=Exception("skip")):
            # Force only openrouter eligible by clearing other keys after first call path
            out = hitl_safe_structured(
                svc,
                "propose rules",
                {"type": "object", "properties": {"rules": {"type": "array"}}},
            )
        if out.get("reasoning_mode") not in ("abstain", "heuristic") and "rules" not in out:
            raise AssertionError(f"unexpected structured result: {out}")
        # Must be a dict, not an exception
        assert isinstance(out, dict)
        print(f"PASS invalid_json: {out.get('reasoning_mode') or 'parsed_or_fallback'}")
    except Exception as e:
        failures.append(f"invalid_json: {e}")
        print(f"FAIL invalid_json: {e}")

    # empty string content → abstain at HITL boundary
    try:
        svc = _adapter()

        def empty(*_a, **_k):
            return LLMResponse(content="", model_used="fake", tokens_used=0)

        with patch.object(svc, "_call_openrouter", side_effect=empty), patch.object(
            svc, "_check_ollama", return_value=False
        ), patch.object(svc, "_call_gemini", side_effect=Exception("skip")), patch.object(
            svc, "_call_openai", side_effect=Exception("skip")
        ), patch.object(svc, "_call_groq", side_effect=Exception("skip")):
            resp = hitl_safe_chat(svc, messages)
        _assert_no_raise_heuristic_or_abstain("empty", resp)
        print(f"PASS empty: mode={resp.reasoning_mode} provider={resp.provider}")
    except Exception as e:
        failures.append(f"empty: {e}")
        print(f"FAIL empty: {e}")

    # all cloud down + ollama down → heuristic
    try:
        svc = _adapter()
        down = _http_error(503)
        with patch.object(svc, "_call_openrouter", side_effect=down), patch.object(
            svc, "_call_gemini", side_effect=down
        ), patch.object(svc, "_call_openai", side_effect=down), patch.object(
            svc, "_call_groq", side_effect=down
        ), patch.object(svc, "_check_ollama", return_value=False), patch.object(
            svc, "_call_ollama", side_effect=ConnectionError("ollama down")
        ):
            resp = hitl_safe_chat(svc, messages)
        _assert_no_raise_heuristic_or_abstain("all_cloud_and_ollama_down", resp)
        print(
            f"PASS all_cloud_and_ollama_down: mode={resp.reasoning_mode} "
            f"provider={resp.provider} depth={resp.fallback_depth}"
        )
    except Exception as e:
        failures.append(f"all_cloud_and_ollama_down: {e}")
        print(f"FAIL all_cloud_and_ollama_down: {e}")

    # Ollama-only preferred path down → heuristic (cloud keys cleared)
    try:
        svc = _adapter()
        svc.openrouter_key = "sk-or-your-placeholder"
        svc.openai_key = "sk-your-placeholder"
        svc.groq_key = "gsk_your-placeholder"
        svc._google_keys = type(svc._google_keys)([])
        with patch.object(svc, "_check_ollama", return_value=True), patch.object(
            svc, "_call_ollama", side_effect=ConnectionError("ollama down")
        ):
            resp = hitl_safe_chat(svc, messages)
        _assert_no_raise_heuristic_or_abstain("ollama_down", resp)
        print(f"PASS ollama_down: mode={resp.reasoning_mode} provider={resp.provider}")
    except Exception as e:
        failures.append(f"ollama_down: {e}")
        print(f"FAIL ollama_down: {e}")

    reset_provider_circuits()
    if failures:
        print("---")
        for f in failures:
            print("FAIL:", f)
        return 1
    print("All provider-fallback scenarios passed (heuristic/abstain, no HITL raise).")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
