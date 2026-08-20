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
    facts = (ROOT / "frontend/src/demo/pilotFacts.ts").read_text()
    bar = (ROOT / "frontend/src/demo/DemoStoryBar.tsx").read_text()
    profiler = (ROOT / "frontend/src/components/workspace/DataProfilerTab.tsx").read_text()
    traces = (ROOT / "frontend/src/components/workspace/AgentTracesTab.tsx").read_text()
    rules = (ROOT / "frontend/src/components/workspace/QualityRulesTab.tsx").read_text()

    # Unhappy entry + warehouse facts (do not invent other numbers)
    assert "loadSnapshot('unhappy')" in ws
    assert "story=unhappy" in ws
    assert "172 SoC / 8 OPEN" in ws
    assert "socBelowZero: 172" in facts
    assert "openIncidents: 8" in facts
    assert "172 SoC / 8 OPEN" in bar
    assert "vins: 60" in facts

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

    # HITL: proposed count is proposals.filter status===proposed
    assert "proposedCount" in rules
    assert '=== \'proposed\'' in rules or '=== "proposed"' in rules
    assert "{proposedCount}" in rules

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

    approve = rules.split("const handleApprove")[1].split("const handleReject")[0]
    assert "hitlApi.approve" in approve
    assert "hitlApi.execute" not in approve
    assert "Execute disabled · sandbox not run · quarantine=0" in rules

    assert "def _session_has_tool_beat" in routes
    force = routes.split("for tool_name in missing_requested_tools", 1)[1]
    guard = force.split("executed_tools", 1)[0]
    assert "if _session_has_tool_beat(session_id, tool_name)" in guard
    assert "continue" in guard
