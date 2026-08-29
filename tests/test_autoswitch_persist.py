"""Auto-switch (not click) must not wipe traces STEPS or Split rows.

After Profile+Propose STEPS 2, AgentChatWorkspace auto-switches the right rail
to profiler/rules via setRightTab on chatMessages — not a tab click. That path
currently remounts/refetches and can wipe traces to STEPS 0 and clobber Split
rows on empty GET.

These assertions fail on today's auto-switch wipe and pass once Product keeps
state. Numbers are existing Unhappy warehouse facts — not invented KPIs.
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from src.api.traces import normalize_trace_step
from src.main import app
from src.orchestrator.engine import ReActEngine, ReActStep

ROOT = Path(__file__).resolve().parents[1]

_AND_UNMOUNT = re.compile(
    r"""rightTab\s*===\s*['"]tab-(?:traces|profiler|rules|split)['"]\s*&&"""
)


def _ws() -> str:
    return (ROOT / "frontend/src/pages/AgentChatWorkspace.tsx").read_text()


def _traces() -> str:
    return (ROOT / "frontend/src/components/workspace/AgentTracesTab.tsx").read_text()


def _split() -> str:
    return (ROOT / "frontend/src/components/workspace/SplitDbQuarantineTab.tsx").read_text()


def _labels() -> str:
    return (ROOT / "frontend/src/demo/stewardLabels.ts").read_text()


def _right_panel(ws: str) -> str:
    start = ws.find("RIGHT PANEL")
    end = ws.find("RULE EDIT MODAL")
    assert start != -1 and end != -1 and end > start, "right panel block missing"
    return ws[start:end]


def _autoswitch_block(ws: str) -> str:
    """The setRightTab-after-chat path — not panel-tab onClick."""
    start = ws.find("Context-Aware Auto-Switch")
    assert start != -1, "auto-switch effect missing"
    rest = ws[start:]
    end = rest.find("\n  }, [chatMessages")
    assert end != -1, "auto-switch must run on chatMessages, not a user click"
    return rest[: end + len("\n  }, [chatMessages]")]


def _load_traces() -> str:
    ui = _traces()
    return ui.split("const loadTraces", 1)[1].split("useEffect", 1)[0]


def _strip_comments(src: str) -> str:
    return re.sub(r"//.*?$", "", src, flags=re.M)


def _norm_row(
    *,
    step: int = 1,
    action: str = "profile_dataset",
    tool_name: str = "profile_dataset",
    thought: str | None = None,
    tool_input: str | None = '{"dataset_key": "vingroup_pilot"}',
    tool_output: str | None = '{"total_rows": 50000, "columns_count": 10, "status": "ok"}',
    observation: str | None = "Sampled 50000 rows",
    tokens: int | None = 120,
    duration_ms: int | None = 640,
    timestamp: str | None = "2026-08-20T10:00:00",
    agent_type: str | None = "canonical_react_engine",
):
    return (
        step,
        thought,
        action,
        tool_name,
        tool_input,
        tool_output,
        observation,
        tokens,
        duration_ms,
        timestamp,
        agent_type,
    )


def _two_beats(sid: str) -> list[dict]:
    eng = ReActEngine(tools=type("T", (), {"get": lambda self, n: None})())
    eng.tools = type("T", (), {"get": lambda self, n: None})()
    eng._log_trace(
        sid,
        ReActStep(
            0,
            "",
            "profile_dataset",
            {"dataset_key": "vingroup_pilot"},
            observation='{"total_rows": 10, "columns_count": 2}',
        ),
        status="done",
    )
    eng._log_trace(
        sid,
        ReActStep(
            1,
            "",
            "propose_quality_rules",
            {"dataset_key": "vingroup_pilot"},
            observation='{"proposals": [{}, {}, {}], "count": 3}',
        ),
        status="done",
    )
    client = TestClient(app, headers={"X-User-Role": "Admin"})
    return client.get(f"/api/v1/traces/{sid}").json()["steps"]


# --- 1) Auto-switch after Profile+Propose STEPS 2 must leave traces STEPS 2 ---


def test_autoswitch_after_profile_propose_keeps_traces_steps():
    """Auto-switch to profiler/rules (not a click) must leave Profile+Propose STEPS 2."""
    ws = _ws()
    panel = _right_panel(ws)
    auto = _autoswitch_block(ws)
    load = _load_traces()
    code = _strip_comments(load)

    # The wipe path: setRightTab after chat, not panel-tab onClick
    assert "setRightTab('tab-profiler')" in auto
    assert "setRightTab('tab-rules')" in auto
    assert "Profile Summary" in auto or "profile_dataset" in auto
    assert "Quality Rule Proposals" in auto or "propose_quality_rules" in auto
    assert "onClick" not in auto
    assert "setTraces" not in auto
    assert "tracesApi" not in auto

    # That setRightTab must not remount traces (hidden=, not &&)
    assert "<AgentTracesTab" in panel
    assert "hidden={rightTab !== 'tab-traces'}" in panel
    assert "rightTab === 'tab-traces' &&" not in panel
    assert _AND_UNMOUNT.search(panel) is None
    assert "key={rightTab}" not in panel

    # Empty GET after auto-switch must not clobber beats already on screen
    assert "setTraces([])" not in code
    assert "keep existing" in load.lower() or "never clobber" in load.lower()

    # STEPS 2 = profile + propose beats already persisted — GET still returns both
    steps = _two_beats(f"qa-autoswitch-steps2-{uuid.uuid4().hex}")
    names = {s.get("tool_name") or s.get("tool") or s.get("action") for s in steps}
    assert "profile_dataset" in names
    assert "propose_quality_rules" in names
    assert len(steps) == 2


def test_autoswitch_does_not_unmount_traces_or_clear_on_empty_get():
    """Do not unmount traces or setTraces([]) on empty GET if beats already exist."""
    ws = _ws()
    traces = _traces()
    load = _load_traces()
    code = _strip_comments(load)
    auto = _autoswitch_block(ws)

    assert "[chatMessages" in auto
    assert "setRightTab('tab-profiler')" in auto
    assert "setRightTab('tab-rules')" in auto

    assert "active={rightTab === 'tab-traces'}" in ws
    assert "hidden={rightTab !== 'tab-traces'}" in ws
    assert "if (keep.length > 0)" in load or "if (mapped.length > 0)" in load
    assert "setTraces([])" not in code
    # Hidden poll must not wipe; empty/error keeps the trail
    assert "if (!active)" in traces
    assert "keep existing" in traces.lower()


# --- 2) Split empty-GET cannot clobber existing rows ---


def test_split_empty_get_does_not_clobber_existing_rows():
    """Same keep-if-already-have as traces: empty GET must not replace existing rows."""
    ui = _split()
    fetch = ui.split("const fetchData", 1)[1].split("useEffect", 1)[0]
    code = _strip_comments(fetch)

    assert "setQuarantineRows([])" not in code
    assert "setCleanRows([])" not in code
    # Must detect empty and keep prev (traces/rules pattern)
    assert "prev" in fetch, (
        "Split fetchData assigns GET rows blindly; empty quarantine/sample "
        "clobbers rows already on screen after auto-switch"
    )
    assert re.search(r"length\s*===\s*0", fetch) or "prev.length" in fetch, (
        "Split empty-GET must keep-if-already-have (prev.length > 0), "
        "not setQuarantineRows(empty)"
    )
    assert (
        "keep existing" in fetch.lower()
        or "never clobber" in fetch.lower()
        or "prev.length" in fetch
    ), "Split must keep existing rows when GET returns []"


# --- 3) Each beat has msgId and/or tool so jump-to-chat can resolve ---


def test_trace_beats_have_msgid_or_tool_for_jump_to_chat():
    """Click a beat → chat scrolls to that tool message (selectedTool / msgId / tool)."""
    traces = _traces()
    labels = _labels()
    ws = _ws()
    load = _load_traces()

    # Persist/normalize: Profile+Propose beats carry tool (and msgId if stored)
    profile = normalize_trace_step(_norm_row())
    propose = normalize_trace_step(
        _norm_row(
            step=2,
            action="propose_quality_rules",
            tool_name="propose_quality_rules",
            observation="Proposed 3 rules",
            tool_output='{"proposals": [{}, {}, {}], "count": 3}',
        )
    )
    for card in (profile, propose):
        jump = card.get("msgId") or card.get("tool") or card.get("tool_name")
        assert jump, f"normalize must expose msgId and/or tool, got {card.keys()}"
        assert jump != "warehouse", "jump target must be the real tool/message, not a fake warehouse"

    steps = _two_beats(f"qa-jump-chat-{uuid.uuid4().hex}")
    assert len(steps) == 2
    for card in steps:
        jump = card.get("msgId") or card.get("tool") or card.get("tool_name")
        assert jump in {"profile_dataset", "propose_quality_rules"}

    # mapTraceStep / loadTraces persist those fields onto the beat
    assert "msgId: raw.msgId" in labels
    assert "tool_name" in labels
    assert "mapTraceStep" in load

    # Tab click handler: Open-in-chat + selectedTool / message id
    assert "jumpToChat" in traces
    assert "trace.msgId" in traces
    assert "[data-msgid=" in traces
    assert "[data-tool=" in traces
    assert "selectedTool" in traces
    assert "onSelectStep" in traces
    assert "selectedTool={selectedTraceTool}" in ws
    assert "data-msgid={msg.id}" in ws
    assert "data-tool=" in ws
    assert "setSelectedTraceTool" in ws
    assert "a1b2c3d4e5f6" not in traces
    assert "I will now" not in traces


# --- Non-regression: existing Unhappy / HITL / keep-mount gates stay ---


def test_autoswitch_does_not_relax_vin_flash_hitl_or_keep_mount():
    """Auto-switch keep must not trade away VIN 60 / flash-hold / Approve≠Execute / Propose-once."""
    bar = (ROOT / "frontend/src/demo/DemoStoryBar.tsx").read_text()
    profiler = (ROOT / "frontend/src/components/workspace/DataProfilerTab.tsx").read_text()
    rules = (ROOT / "frontend/src/components/workspace/QualityRulesTab.tsx").read_text()
    facts = (ROOT / "frontend/src/demo/pilotFacts.ts").read_text()
    routes = (ROOT / "src/api/routes/__init__.py").read_text()
    engine = (ROOT / "src/orchestrator/engine.py").read_text()
    ws = _ws()
    panel = _right_panel(ws)

    assert "60 VIN" in bar
    assert "vins: 60" in facts
    assert "holdHealth" in profiler
    assert "holdPendingHealth" in profiler
    assert "holdUnhappyHealth" in profiler
    assert "warehouseFaults" in profiler
    assert "Critical" in profiler
    assert "socBelowZero: 172" in facts
    assert "openIncidents: 8" in facts

    approve = rules.split("const handleApprove")[1].split("const handleConfirmReject")[0]
    assert "hitlApi.approve" in approve
    assert "hitlApi.execute" not in approve
    assert "Execute disabled · sandbox not run · quarantine=0" in rules

    assert "def _session_has_tool_beat" in routes
    assert "_skip_duplicate_propose" in engine
    assert "Stop for HITL" in ws or "dừng HITL" in ws or "stop at HITL" in ws

    for tab_id, component in (
        ("tab-traces", "AgentTracesTab"),
        ("tab-profiler", "DataProfilerTab"),
        ("tab-rules", "QualityRulesTab"),
        ("tab-split", "SplitDbQuarantineTab"),
    ):
        assert f"<{component}" in panel
        assert f"hidden={{rightTab !== '{tab_id}'}}" in panel
        assert f"rightTab === '{tab_id}' &&" not in panel
