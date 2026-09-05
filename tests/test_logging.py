import json
import logging

from src.observability.context import bind_context, reset_context
from src.observability.formatters import DataTrustJsonFormatter
from src.observability.redaction import redact, redact_text


def test_redaction_masks_sensitive_keys_and_url_secrets():
    assert redact({"api_key": "secret", "nested": {"token": "value"}}) == {
        "api_key": "[REDACTED]",
        "nested": {"token": "[REDACTED]"},
    }
    assert "key=[REDACTED]" in redact_text("https://api.test?key=secret")


def test_formatter_emits_context_and_redacted_json():
    token = bind_context(request_id="req-test-123", run_id="run-test-123")
    try:
        record = logging.LogRecord(
            "src.services.llm",
            logging.WARNING,
            __file__,
            1,
            "provider call failed: %s",
            ("https://api.test?key=secret",),
            None,
        )
        record.event = "llm_provider_failed"
        record.provider = "gemini"
        record.api_key = "secret"

        payload = json.loads(DataTrustJsonFormatter().format(record))

        assert payload["event"] == "llm_provider_failed"
        assert payload["request_id"] == "req-test-123"
        assert payload["run_id"] == "run-test-123"
        assert payload["api_key"] == "[REDACTED]"
        assert "key=[REDACTED]" in payload["message"]
    finally:
        reset_context(token)
