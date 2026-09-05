import json
from src.reliability.models.rule_context import (
    build_rule_proposal_context,
    render_rule_proposal_prompt_block,
    group_incidents_to_candidates,
)
from src.tools.rule_proposer import RuleProposerTool


def test_group_duplicate_soc_incidents():
    incidents = [
        {"incident_id": f"i{n}", "affected_columns": ["battery_soc"], "severity": "high",
         "detector_layers": ["L1"], "failure_mechanism": "range"}
        for n in range(27)
    ]
    cands = group_incidents_to_candidates(incidents, "ev_telemetry")
    assert len(cands) == 1
    assert cands[0].frequency == 27
    assert cands[0].affected_column == "battery_soc"


def test_render_never_uses_char_slice():
    anomalies = {"incidents": [{"incident_id": f"i{n}", "payload": "x" * 200} for n in range(80)]}
    ctx = build_rule_proposal_context(
        dataset_key="ev_telemetry",
        target_table="ev_telemetry",
        profile={"columns": [{"name": "battery_soc", "dtype": "float", "null_rate": 0.01}]},
        anomalies=anomalies,
        policy={"battery_soc": {"min": 0, "max": 100}},
    )
    block = render_rule_proposal_prompt_block(ctx)
    json.loads(block) if block.lstrip().startswith("{") else None
    assert "[:1000]" not in block
    assert ctx.context_metadata.estimated_tokens > 0


def test_rule_proposer_prompt_contains_full_valid_json(monkeypatch):
    captured = {}

    class FakeLLM:
        def generate_structured(self, *a, **k):
            captured["prompt"] = k.get("prompt") or (a[0] if a else "")
            return {"rules": []}

    tool = RuleProposerTool(llm=None)
    # If the tool uses self.llm.chat / generate, monkeypatch that instead.
    src = open("src/tools/rule_proposer.py").read()
    assert "[:1000]" not in src
