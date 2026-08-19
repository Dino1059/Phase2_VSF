"""Unit tests for course AI-log redaction (not product audit_log)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_REDACT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "ai_log_redact.py"
_SPEC = importlib.util.spec_from_file_location("ai_log_redact", _REDACT_PATH)
_MOD = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_MOD)
redact_text = _MOD.redact_text
redact_obj = _MOD.redact_obj

# Synthetic fixtures assembled so tests never depend on a live credential.
_FAKE_SK = "sk-" + "proj-" + "EXAMPLETESTKEY" + "1234567890abcd"
_FAKE_GHP = "ghp_" + ("x" * 36)
_FAKE_GHO = "gho_" + ("y" * 36)
_FAKE_PAT = "github_pat_" + ("z" * 22)
_FAKE_AKIA = "AKIA" + ("A" * 16)
_FAKE_SLACK = "xoxb-" + "1234567890" + "-abcdefghij"
_FAKE_JWT = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiIxMjM0NTY3ODkwIn0."
    "testsigTESTSIG"
)
_FAKE_CF = "eyJhIjoi" + ("B" * 40)
_FAKE_PEM = (
    "-----BEGIN PRIVATE KEY-----\n"
    "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC0FAKEPEM\n"
    "-----END PRIVATE KEY-----"
)
_FAKE_BEARER = "Bearer " + "n3xampl3t0kenvalue99"
_FAKE_EMAIL = "alice.student@example.com"
_CLEAN = "Please add a timeout to the backend lint job and keep the JSON shape."
_REPO_HTTPS = "https://github.com/AI20K-Build-Phase-Cohort-3/P-086.git"
_REPO_SSH = "git@github.com:AI20K-Build-Phase-Cohort-3/P-086.git"


def test_openai_like_key_is_blurred():
    out = redact_text(f"use key {_FAKE_SK} please")
    assert _FAKE_SK not in out
    assert "[REDACTED:api_key]" in out


def test_github_tokens_are_blurred():
    blob = f"{_FAKE_GHP} {_FAKE_GHO} {_FAKE_PAT}"
    out = redact_text(blob)
    assert _FAKE_GHP not in out
    assert _FAKE_GHO not in out
    assert _FAKE_PAT not in out
    assert out.count("[REDACTED:token]") == 3


def test_aws_and_slack_are_blurred():
    out = redact_text(f"{_FAKE_AKIA} {_FAKE_SLACK}")
    assert _FAKE_AKIA not in out
    assert _FAKE_SLACK not in out
    assert "[REDACTED:api_key]" in out
    assert "[REDACTED:token]" in out


def test_jwt_and_cf_tunnel_are_blurred():
    out = redact_text(f"jwt={_FAKE_JWT} cf={_FAKE_CF}")
    assert _FAKE_JWT not in out
    assert _FAKE_CF not in out
    assert "[REDACTED:jwt]" in out or "[REDACTED:token]" in out


def test_pem_and_bearer_are_blurred():
    out = redact_text(f"{_FAKE_PEM}\nAuthorization: {_FAKE_BEARER}")
    assert "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC0FAKEPEM" not in out
    assert "n3xampl3t0kenvalue99" not in out
    assert "[REDACTED:pem]" in out
    assert "[REDACTED:token]" in out


def test_env_assignment_value_is_blurred():
    line = "export OPENAI_API_KEY=not-a-real-secret-value-12345"
    out = redact_text(line)
    assert "not-a-real-secret-value-12345" not in out
    assert "OPENAI_API_KEY" in out
    assert "[REDACTED:secret]" in out


def test_email_is_blurred():
    out = redact_text(f"ping {_FAKE_EMAIL} about the PR")
    assert _FAKE_EMAIL not in out
    assert "[REDACTED:email]" in out


def test_clean_prompt_is_unchanged():
    assert redact_text(_CLEAN) == _CLEAN


def test_repo_urls_are_not_redacted():
    text = f"clone {_REPO_HTTPS} or {_REPO_SSH}"
    assert redact_text(text) == text


def test_redact_obj_keeps_ingest_shape():
    entry = {
        "ts": "2026-08-20T01:00:00+07:00",
        "tool": "cursor",
        "event": "UserPrompt",
        "student": "shayneeo@ai20k.build",
        "repo": "P-086",
        "prompt": f"key {_FAKE_SK} mail {_FAKE_EMAIL}",
        "tool_input": {"command": f"echo {_FAKE_GHP}"},
        "nested": ["ok", {"x": _FAKE_EMAIL}],
    }
    out = redact_obj(entry)
    assert set(out) == set(entry)
    assert out["ts"] == entry["ts"]
    assert out["tool"] == "cursor"
    assert out["student"] == "shayneeo@ai20k.build"
    assert out["repo"] == "P-086"
    assert _FAKE_SK not in out["prompt"]
    assert _FAKE_EMAIL not in out["prompt"]
    assert "[REDACTED:api_key]" in out["prompt"]
    assert "[REDACTED:email]" in out["prompt"]
    assert _FAKE_GHP not in out["tool_input"]["command"]
    assert out["nested"][0] == "ok"
    assert out["nested"][1]["x"] == "[REDACTED:email]"
