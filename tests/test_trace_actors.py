"""Right-rail AgentTracesTab actor chip from tool_name (then action, then actor_kind).

Four demo agents only: Profiler / Proposer / Repair / Benchmark.
clean_database is not Repair. Quarantine is a zone, not a chip unless nothing else to name.
Traces stay on the right rail. Beat click → chat (data-msgid / data-tool) still works.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABELS = ROOT / "frontend/src/demo/stewardLabels.ts"
TRACES = ROOT / "frontend/src/components/workspace/AgentTracesTab.tsx"
WS = ROOT / "frontend/src/pages/AgentChatWorkspace.tsx"

DEMO_AGENTS = {"Profiler", "Proposer", "Repair", "Benchmark"}

EXPECTED = {
    "profile_dataset": "Profiler",
    "data_profiler": "Profiler",
    "list_tables": "Profiler",
    "propose_quality_rules": "Proposer",
    "quality_rule_proposer": "Proposer",
    "propose_patches": "Repair",
    "apply_patches": "Repair",
    "benchmark_dataset": "Benchmark",
}


def _labels() -> str:
    return LABELS.read_text()


def _traces() -> str:
    return TRACES.read_text()


def _ws() -> str:
    return WS.read_text()


def _right_panel(ws: str) -> str:
    start = ws.find("RIGHT PANEL")
    end = ws.find("RULE EDIT MODAL")
    assert start != -1 and end != -1 and end > start, "right panel block missing"
    return ws[start:end]


def _parse_trace_actor_map() -> dict[str, str]:
    src = _labels()
    assert "export const TRACE_ACTOR_BY_TOOL" in src
    block = src.split("export const TRACE_ACTOR_BY_TOOL", 1)[1].split("};", 1)[0]
    mapped = dict(re.findall(r"([A-Za-z0-9_]+):\s*'([A-Za-z]+)'", block))
    return mapped


def last_tool_segment(name: str | None) -> str:
    if not name:
        return ""
    parts = [p for p in re.split(r"[/\\.]", str(name).strip()) if p]
    return (parts[-1] if parts else str(name)).lower()


def chip_for(tool_name: str | None = None, action: str | None = None, actor_kind: str | None = None) -> str | None:
    """Mirror actorChipFromTrace tool/action priority (not actorLabel fallback)."""
    mapped = _parse_trace_actor_map()

    def one(name: str | None) -> str | None:
        seg = last_tool_segment(name)
        if not seg or seg == "clean_database" or seg == "quarantine":
            return None
        return mapped.get(seg)

    return one(tool_name) or one(action)


def test_trace_actor_map_exists_and_is_four_demo_agents_only():
    mapped = _parse_trace_actor_map()
    assert mapped == EXPECTED, mapped
    assert set(mapped.values()) == DEMO_AGENTS
    assert "clean_database" not in mapped
    assert "quarantine" not in mapped
    assert "Quarantine" not in mapped.values()
    src = _labels()
    assert "actorChipFromTrace" in src
    assert "lastToolSegment" in src
    assert "clean_database" in src.split("function chipForToolSegment", 1)[1].split("return TRACE_ACTOR_BY_TOOL", 1)[0]
    zone = src.split("ZONE_NOT_CHIP", 1)[1].split(";", 1)[0]
    assert "quarantine" in zone.lower()


def test_tool_name_last_segment_maps_case_insensitive_before_action_and_actor():
    assert chip_for(tool_name="profile_dataset", actor_kind="DATA_STEWARD") == "Profiler"
    assert chip_for(tool_name="list_tables") == "Profiler"
    assert chip_for(tool_name="list_tables") != "Repair"
    assert chip_for(tool_name="src.tools.chat_tools.profile_dataset") == "Profiler"
    assert chip_for(tool_name="tools/data_profiler") == "Profiler"
    assert chip_for(tool_name="PROFILE_DATASET", action="propose_quality_rules") == "Profiler"
    assert chip_for(tool_name="unknown_tool", action="propose_quality_rules") == "Proposer"
    assert chip_for(tool_name="quality_rule_proposer") == "Proposer"
    assert chip_for(tool_name="propose_patches") == "Repair"
    assert chip_for(tool_name="apply_patches", actor_kind="EXECUTOR") == "Repair"
    assert chip_for(tool_name="benchmark_dataset") == "Benchmark"
    # tool_name wins over action
    assert chip_for(tool_name="profile_dataset", action="apply_patches") == "Profiler"


def test_clean_database_is_not_repair_and_unknown_keeps_existing_label():
    src = _labels()
    traces = _traces()
    assert chip_for(tool_name="clean_database") is None
    assert chip_for(tool_name="clean_database", action="apply_patches") == "Repair"
    assert chip_for(tool_name="clean_database", action="clean_database") is None
    assert "clean_database" in src  # catalog / exclusion, not a sixth agent
    assert "actorChipFromTrace(trace, isVi) || actorLabel(trace.actor_kind, isVi)" in traces
    # Unknown tools keep actorLabel fallback — no invented sixth demo agent
    for banned in ("Cleanser", "Anomaly", "Detector", "Quarantine Agent", "Executor Agent"):
        assert banned not in _parse_trace_actor_map().values()


def test_quarantine_is_zone_not_chip_unless_nothing_else_to_name():
    src = _labels()
    assert chip_for(tool_name="quarantine", action="profile_dataset") == "Profiler"
    assert chip_for(tool_name="quarantine") is None
    fn = src.split("export function actorChipFromTrace", 1)[1].split("export function preferActorKind", 1)[0]
    assert "ZONE_NOT_CHIP" in fn
    assert "Quarantine" in fn
    assert "actorLabel" in fn


def test_traces_stay_on_right_rail_and_beat_click_jumps_to_chat():
    traces = _traces()
    ws = _ws()
    panel = _right_panel(ws)
    assert "<AgentTracesTab" in panel
    assert "tab-traces" in panel
    assert ws.count("<AgentTracesTab") == 1
    assert ws.find("RIGHT PANEL") < ws.find("<AgentTracesTab") < ws.find("RULE EDIT MODAL")
    # Traces SoT stays the rail tab, not main chat
    assert "jumpToChat" in traces
    assert "[data-msgid=" in traces
    assert "[data-tool=" in traces
    assert "actorChipFromTrace" in traces
    assert "selectedTool" in traces
    assert "data-msgid={msg.id}" in ws
    assert "data-tool=" in ws


def test_actor_chip_does_not_regress_keep_mount_steps_critical_or_hitl():
    ws = _ws()
    panel = _right_panel(ws)
    traces = _traces()
    profiler = (ROOT / "frontend/src/components/workspace/DataProfilerTab.tsx").read_text()
    for tab_id, component in (
        ("tab-traces", "AgentTracesTab"),
        ("tab-profiler", "DataProfilerTab"),
        ("tab-rules", "QualityRulesTab"),
        ("tab-split", "SplitDbQuarantineTab"),
    ):
        assert f"<{component}" in panel
        assert f"rightTab === '{tab_id}' &&" not in panel
        assert f"hidden={{rightTab !== '{tab_id}'}}" in panel
    assert "Measured steps" in traces
    assert "Never clobber existing steps with empty" in traces
    assert "Critical" in profiler
    assert "Stop for HITL" in ws or "stop at HITL" in ws or "dừng HITL" in ws
