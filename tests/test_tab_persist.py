"""Right-rail tab persist after Unhappy snapshot.

Known wipe (today): AgentChatWorkspace remounts Profiler / Traces / Rules / Split
via `{rightTab === ... && (` and unmounts the whole rail via `{rightPanelOpen && (`.
Remount re-runs each tab\'s mount effect (profiler `setProfile(null)` + fetch,
traces `setTraces([])` + load, HITL `setProposals([])` + fetch) and drops:

  - profiler health/faults (Unhappy Critical + warehouse 172 SoC<0 / 8 OPEN)
  - traces Measured steps
  - HITL proposedCount

Product fix: keep all four tabs mounted (hidden / CSS collapse is fine).
These assertions fail on today\'s `&&` dump and pass once idle tabs stay mounted.
Numbers are the existing Unhappy warehouse facts — not invented KPIs/hashes/thoughts.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_TABS = (
    ("tab-traces", "AgentTracesTab"),
    ("tab-profiler", "DataProfilerTab"),
    ("tab-rules", "QualityRulesTab"),
    ("tab-split", "SplitDbQuarantineTab"),
)

_AND_UNMOUNT = re.compile(
    r"""rightTab\s*===\s*['"]tab-(?:traces|profiler|rules|split)['"]\s*&&"""
)
_TERNARY_UNMOUNT = re.compile(
    r"""rightTab\s*===\s*['"](tab-(?:traces|profiler|rules|split))['"]\s*\?\s*\(?\s*<(AgentTracesTab|DataProfilerTab|QualityRulesTab|SplitDbQuarantineTab)"""
)


def _ws() -> str:
    return (ROOT / "frontend/src/pages/AgentChatWorkspace.tsx").read_text()


def _right_panel(ws: str) -> str:
    start = ws.find("RIGHT PANEL")
    end = ws.find("RULE EDIT MODAL")
    assert start != -1 and end != -1 and end > start, "right panel block missing"
    return ws[start:end]


def test_workspace_keeps_four_tabs_mounted_not_unmounted_with_and():
    """Idle Profiler / Traces / Rules / Split must stay mounted (hidden), not `&&`."""
    panel = _right_panel(_ws())
    for tab_id, component in _TABS:
        assert f"<{component}" in panel, f"{component} must stay in the right rail"
        gate = f"rightTab === '{tab_id}' &&"
        gate_dq = f'rightTab === "{tab_id}" &&'
        assert gate not in panel and gate_dq not in panel, (
            f"{tab_id} is unmounted with `&&`; remount wipes Unhappy Critical / "
            f"172/8 warehouse faults, traces STEPS, HITL proposed count"
        )
    assert _AND_UNMOUNT.search(panel) is None, (
        "right-rail tabs still remount via rightTab === ... &&"
    )
    assert _TERNARY_UNMOUNT.search(panel) is None, (
        "ternary mount of a single tab is the same remount wipe as `&&`"
    )
    assert "key={rightTab}" not in panel
    assert "key={`${rightTab" not in panel
    assert "switch (rightTab)" not in panel
    assert "switch(rightTab)" not in panel
    # Intended fix: keep-mounted + hidden, not remount
    for tab_id, _component in _TABS:
        hidden = f"hidden={{rightTab !== '{tab_id}'}}"
        hidden_dq = f'hidden={{rightTab !== "{tab_id}"}}'
        display = f"display: rightTab === '{tab_id}'"
        assert hidden in panel or hidden_dq in panel or display in panel, (
            f"{tab_id} must stay mounted and hidden when idle "
            "(hidden={{rightTab !== ...}} or display), not unmounted"
        )


def test_right_rail_collapse_does_not_unmount_tabs():
    """Collapse / reopen must hide the rail, not `{rightPanelOpen && (` remount."""
    panel = _right_panel(_ws())
    gate = panel.find("{rightPanelOpen &&")
    for _tab_id, component in _TABS:
        comp = panel.find(f"<{component}")
        assert comp != -1, f"{component} missing from right panel"
        assert gate == -1 or gate > comp, (
            f"{component} sits inside {{rightPanelOpen && ...}} — collapse/reopen "
            "remounts and drops Unhappy Critical + 172/8, traces STEPS, HITL proposed"
        )
    assert "aria-hidden={!rightPanelOpen}" in panel or "hidden={!rightPanelOpen}" in panel, (
        "collapse must hide the keep-mounted rail, not unmount it"
    )


def test_unhappy_tab_state_is_critical_172_8_measured_steps_and_proposed_count():
    """After Unhappy snapshot, persist must keep these measured values — not invent new ones."""
    ws = _ws()
    profiler = (ROOT / "frontend/src/components/workspace/DataProfilerTab.tsx").read_text()
    traces = (ROOT / "frontend/src/components/workspace/AgentTracesTab.tsx").read_text()
    rules = (ROOT / "frontend/src/components/workspace/QualityRulesTab.tsx").read_text()

    # Table+day SoT replaced DemoStoryBar snapshot theater; keep-mount + warehouse faults remain.
    assert "hidden={rightTab !== 'tab-profiler'}" in ws
    assert "story" in ws
    assert "warehouseFaults" in profiler

    # Profiler: Unhappy Critical from warehouse faults, flash-hold until they settle
    assert "warehouseFaults" in profiler
    assert "warehouse_soc_below_zero" in profiler
    assert "warehouse_open_incidents" in profiler
    assert "holdUnhappyHealth" in profiler
    assert "holdHealth" in profiler
    assert "Critical" in profiler
    assert "story" in profiler
    assert "story={story}" in ws

    # Traces: measured steps stay (count is traces.length, never a fake STEPS)
    assert "Measured steps" in traces
    assert "traces.length" in traces
    assert "No measured traces" in traces
    assert "a1b2c3d4e5f6" not in traces
    assert "I will now" not in traces

    # HITL: header counts the same cards that render (pending/queued/unlabeled → PROPOSED)
    assert "proposedCount" in rules
    assert "approvedCount" in rules
    assert "ruleCardStatus" in rules
    assert "{proposedCount}" in rules
    assert "{approvedCount}" in rules
    assert "ruleCardStatus" in rules
    assert "ruleCardStatus(r) === 'approved'" in rules

    # Remount is what wipes the above; keep-mount is the fix
    panel = _right_panel(ws)
    assert _AND_UNMOUNT.search(panel) is None, (
        "Unhappy Critical / 172/8, traces STEPS, HITL proposedCount cannot persist "
        "while idle tabs unmount with `&&`"
    )


def test_persist_does_not_relax_vin_flash_hitl_approve_or_propose_once():
    """Keep-mount must not trade away VIN 60 / flash-hold / Approve≠Execute / Propose-once."""
    bar = (ROOT / "frontend/src/demo/DemoStoryBar.tsx").read_text()
    profiler = (ROOT / "frontend/src/components/workspace/DataProfilerTab.tsx").read_text()
    rules = (ROOT / "frontend/src/components/workspace/QualityRulesTab.tsx").read_text()
    facts = (ROOT / "frontend/src/demo/pilotFacts.ts").read_text()
    routes = (ROOT / "src/api/routes/__init__.py").read_text()

    assert "60 VIN" in bar
    assert "vins: 60" in facts
    assert "holdHealth" in profiler
    assert "holdPendingHealth" in profiler
    assert "holdUnhappyHealth" in profiler
    assert "99.1" in profiler
    assert "dt-snap-pending" in bar

    approve = rules.split("const handleApprove")[1].split("const handleConfirmReject")[0]
    assert "hitlApi.approve" in approve
    assert "hitlApi.execute" not in approve
    assert "Execute disabled · sandbox not run · quarantine=0" in rules

    assert "def _session_has_tool_beat" in routes
    force = routes.split("for tool_name in missing_requested_tools", 1)[1]
    guard = force.split("executed_tools", 1)[0]
    assert "if _session_has_tool_beat(session_id, tool_name)" in guard
    assert "continue" in guard

def test_rules_tab_refetches_on_show_and_trace_without_rerunning_propose():
    """Keep-mounted Rules fetched empty at boot; must GET-refetch, never POST Propose."""
    rules = (ROOT / "frontend/src/components/workspace/QualityRulesTab.tsx").read_text()
    traces = (ROOT / "frontend/src/components/workspace/AgentTracesTab.tsx").read_text()
    ws = _ws()
    panel = _right_panel(ws)

    assert "active?: boolean" in rules
    assert "datatrust:agent-trace" in rules
    assert "hitlApi.queue" in rules
    assert "sendChatMessage" not in rules
    assert "/chat/send" not in rules
    assert "proposeRules" not in rules
    assert "ruleCardStatus" in rules
    assert "fetchRules({ silent: true })" in rules
    assert "active={rightTab === 'tab-rules'}" in panel

    assert "active?: boolean" in traces
    assert "sendChatMessage" not in traces
    assert "/chat/send" not in traces
    assert "tracesApi.get" in traces
    assert "active={rightTab === 'tab-traces'}" in panel

    for tab_id in ("tab-traces", "tab-profiler", "tab-rules", "tab-split"):
        assert f"onClick={{() => setRightTab('{tab_id}')}}" in panel
    assert "sendChatMessage" not in panel
    assert "loadSnapshot" not in panel
    assert "sessionStorage.removeItem(bootKey)" not in ws
    assert "hitlBootsInFlight" in ws
    assert "_skip_duplicate_propose" in (ROOT / "src/orchestrator/engine.py").read_text()

def test_traces_get_and_poll_never_force_propose():
    """GET /traces and the tab poll must not POST chat or call missing_requested_tools."""
    traces_py = (ROOT / "src/api/traces.py").read_text()
    get_fn = traces_py.split("async def get_trace", 1)[1]
    assert "missing_requested_tools" not in traces_py
    assert "_log_trace" not in get_fn
    assert "ProposeQualityRulesTool" not in get_fn
    assert "/chat/send" not in get_fn
    ui = (ROOT / "frontend/src/components/workspace/AgentTracesTab.tsx").read_text()
    load = ui.split("const loadTraces", 1)[1].split("useEffect", 1)[0]
    assert "tracesApi.get" in load
    assert "hitlApi.history" in load
    assert "sendChatMessage" not in load
    assert "proposeRules" not in load
    assert "/chat/send" not in ui
    routes = (ROOT / "src/api/routes/__init__.py").read_text()
    assert "_PROPOSE_ALIASES" in routes or "quality_rule_proposer" in routes.split("def _session_has_tool_beat", 1)[1]



def test_traces_tab_does_not_wipe_steps_on_empty_refetch():
    """Profiler → Traces must keep STEPS. loadTraces must not clobber existing steps with empty."""
    import re
    ui = (ROOT / "frontend/src/components/workspace/AgentTracesTab.tsx").read_text()
    load = ui.split("const loadTraces", 1)[1].split("useEffect", 1)[0]
    code = re.sub(r"//.*?$", "", load, flags=re.M)
    assert "setTraces([])" not in code
    assert "Never clobber existing steps with empty" in load
    assert "keep existing" in load
    assert "resolvedSessionRef" in ui
    assert "tracesApi.list" in load
    assert "dataset:${datasetKey}" in load
    poll = ui.split("window.setInterval", 1)[0]
    assert "if (!active)" in ui
    rules = (ROOT / "frontend/src/components/workspace/QualityRulesTab.tsx").read_text()
    fetch = rules.split("const fetchRules", 1)[1].split("useEffect", 1)[0]
    assert "fromDb.length === 0" in fetch
    assert "prev.length > 0" in fetch
    assert "emptyBootRef" in rules
    assert "setProposals([])" not in fetch
    assert "if (active)" in rules
    assert "datatrust:agent-trace" in rules
    traces_py = (ROOT / "src/api/traces.py").read_text()
    assert "def workspace_trace_sessions" in traces_py
    assert "def resolve_trace_rows" in traces_py
    get_fn = traces_py.split("async def get_trace", 1)[1]
    assert "if since_dt and not normalized and unfiltered" in traces_py
    assert "ProposeQualityRulesTool" not in get_fn
    hitl = (ROOT / "src/api/hitl.py").read_text()
    assert "id LIKE" in hitl
    assert "_hydrate_queue_from_traces" in hitl
    tools = (ROOT / "src/tools/chat_tools.py").read_text()
    assert "def persist_hitl_proposals" in tools
    assert "def namespace_rule_id" in tools
    assert "namespace_rule_id(" in tools
    assert '"status": "proposed"' in tools


def test_autoswitch_does_not_wipe_traces_or_split_store():
    """Auto-switch is display-only. Empty GET / hidden mount cannot clobber the store."""
    ws = _ws()
    store = (ROOT / "frontend/src/stores/workspaceStore.ts").read_text()
    traces = (ROOT / "frontend/src/components/workspace/AgentTracesTab.tsx").read_text()
    split = (ROOT / "frontend/src/components/workspace/SplitDbQuarantineTab.tsx").read_text()

    assert "tracesByDataset" in store
    assert "splitRowsByDataset" in store
    assert "datasetStoreKey" in store
    assert "if (!incoming.length) return state" in store
    merge_split = store.split("mergeSplitRows:", 1)[1]
    assert "never clobber" in merge_split.lower() or "quarantineRows.length > 0" in merge_split

    auto = ws.split("Context-Aware Auto-Switch", 1)[1].split("useEffect", 1)[1].split("}, [chatMessages", 1)[0]
    assert "setRightTab('tab-profiler')" in auto
    assert "setRightTab('tab-rules')" in auto
    assert "loadSnapshot" not in auto
    assert "resetDemoSession" not in auto
    assert "clearMessages" not in auto
    assert "setTraces([])" not in auto
    assert "mergeTraces(" not in auto or "mergeTraces(storeKey, [])" not in auto

    load = traces.split("const loadTraces", 1)[1].split("useEffect", 1)[0]
    assert "setTraces([])" not in load
    assert "mergeTraces" in load
    assert "Never clobber existing steps with empty" in load
    assert "useWorkspaceStore" in traces

    assert "useWorkspaceStore" in split
    assert "mergeSplitRows" in split
    assert "Empty GET must never clobber" in split
    assert "Clean has not run" in split
    assert "No quarantine or clean rows invented" in split
    assert "if (active) void fetchData()" in split
    assert "active={rightTab === 'tab-split'}" in ws


def test_beat_click_jumps_to_chat_via_msgid_or_tool():
    """Each beat stores msgId or tool_name; chat bubbles/chips have data-msgid/data-tool."""
    traces = (ROOT / "frontend/src/components/workspace/AgentTracesTab.tsx").read_text()
    ws = _ws()
    agent = (ROOT / "frontend/src/components/chat/AgentMessage.tsx").read_text()
    labels = (ROOT / "frontend/src/demo/stewardLabels.ts").read_text()
    traces_py = (ROOT / "src/api/traces.py").read_text()

    assert "msgId" in traces
    assert "tool_name" in traces
    assert "jumpToChat" in traces
    assert "dt-chat-highlight" in traces
    assert "data-msgid" in traces or "[data-msgid=" in traces
    assert "[data-tool=" in traces
    assert "jumpToChat(trace)" in traces

    assert "data-msgid={msg.id}" in ws
    assert "data-tool={toolName" in ws
    assert "used-tool-chip" in ws
    assert 'data-msgid={message.id}' in agent
    assert "data-tool={toolName" in agent
    assert "msgId: raw.msgId || raw.msg_id || raw.message_id" in labels
    assert "def attach_msg_ids" in traces_py
    assert "attach_msg_ids(db, resolved, normalized)" in traces_py


def test_split_empty_honest_when_clean_never_ran():
    """Stop-at-HITL: empty Split says clean never ran. Populated rows survive active flip."""
    split = (ROOT / "frontend/src/components/workspace/SplitDbQuarantineTab.tsx").read_text()
    ws = _ws()
    rules = (ROOT / "frontend/src/components/workspace/QualityRulesTab.tsx").read_text()

    assert "cleanRan" in split
    assert "Clean has not run" in split
    assert "Approve at HITL" in split
    fetch = split.split("const fetchData", 1)[1].split("useEffect", 1)[0]
    assert "setQuarantineRows([])" not in fetch
    assert "setCleanRows([])" not in fetch
    assert "incomingQ" in fetch
    assert "never clobber" in fetch
    assert "if (active)" in split
    assert "HITL_STOP_PROMPT" in ws
    approve = rules.split("const handleApprove")[1].split("const handleConfirmReject")[0]
    assert "hitlApi.approve" in approve
    assert "hitlApi.execute" not in approve
    assert "Execute disabled · sandbox not run · quarantine=0" in rules


def test_traces_api_attaches_msgid_from_chat_message():
    """GET /traces stamps msgId from the chat row for that tool. Empty sessions stay empty."""
    import json
    import uuid
    from fastapi.testclient import TestClient
    from src.db.connection import get_db
    from src.main import app

    sid = f"dataset:qa-msgid-{uuid.uuid4().hex[:10]}"
    mid = f"msg_{uuid.uuid4().hex[:10]}"
    db = get_db()
    db.execute(
        "INSERT INTO agent_traces (id, session_id, agent_type, step_index, thought, action, "
        "tool_name, tool_input, tool_output, observation, tokens_used, duration_ms) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            f"tr-{uuid.uuid4().hex[:12]}",
            sid,
            "C1_AI",
            1,
            None,
            "profile_dataset",
            "profile_dataset",
            json.dumps({"dataset_key": "vingroup_pilot"}),
            json.dumps({"total_rows": 2}),
            "2 rows",
            4,
            12,
        ],
    )
    db.execute(
        "INSERT INTO messages (id, session_id, type, agent_id, content, metadata_json, timestamp) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [mid, sid, "agent", "profile_dataset", "Profile Summary", "{}", "2026-08-20T10:00:00"],
    )
    client = TestClient(app, headers={"X-User-Role": "Admin"})
    steps = client.get(f"/api/v1/traces/{sid}").json()["steps"]
    assert steps
    card = steps[0]
    assert (card.get("tool_name") or card.get("action")) == "profile_dataset"
    assert card.get("msgId") == mid or card.get("msg_id") == mid
    empty = f"qa-empty-msgid-{uuid.uuid4().hex}"
    blank = client.get(f"/api/v1/traces/{empty}")
    assert blank.status_code == 200
    assert blank.json().get("steps") == []
