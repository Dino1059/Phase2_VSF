import pytest
from src.tools.rule_executor import RuleExecutorTool, RuleSpec
from src.services.security import validate_webhook_url
from src.agents.baselines import BaselineA1, BaselineA2, BenchmarkCase


def test_red_team_prompt_injection_in_rule_spec():
    executor = RuleExecutorTool()
    malicious_spec = RuleSpec(
        table="vgreen_telemetry",
        column="temperature; DROP TABLE vgreen_telemetry; --",
        operator="gt",
        arguments=[100],
    )
    # Compiler must reject multiple statements / SQL injection
    with pytest.raises(Exception):
        executor.compile_rule(malicious_spec)


def test_red_team_ssrf_webhook_blocked():
    assert validate_webhook_url("http://127.0.0.1:8000/internal") is False
    assert validate_webhook_url("http://169.254.169.254/latest/meta-data") is False
    assert validate_webhook_url("http://10.0.0.1/admin") is False
    assert validate_webhook_url("https://8.8.8.8/webhook") is True


@pytest.mark.asyncio
async def test_red_team_missing_data_context():
    a1 = BaselineA1()
    # Non-existent table and missing context
    case = BenchmarkCase(case_id="case_missing", dataset_key="non_existent_table_123")
    result = await a1.run(case)

    assert result.tier == "A1"
    # Agent must handle non-existent table gracefully without crashing
    assert isinstance(result.predictions, set)
    assert isinstance(result.evidence_refs, list)


@pytest.mark.asyncio
async def test_red_team_a2_verifier_filters_unsupported():
    a2 = BaselineA2()
    case = BenchmarkCase(case_id="case_redteam", dataset_key="vgreen_telemetry")
    result = await a2.run(case)

    assert result.tier == "A2"
    assert any(t.get("step") == "a2_verifier_audit" for t in result.tool_trace)
    assert result.cost_tokens > 0
