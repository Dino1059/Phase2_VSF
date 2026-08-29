"""Happy snapshot is clean CSVs, not a fault_injected=False row pointing at faulty paths."""
from pathlib import Path

from src.api.routes.system import resolve_demo_source


ROOT = Path(__file__).resolve().parents[1]


def test_happy_source_is_clean_csv_dir():
    src = resolve_demo_source("happy", str(ROOT))
    assert src.name == "vingroup_pilot_dataset"
    assert (src / "synthetic_ev_telemetry_ved_ref.csv").is_file()
    assert not (src / "fault_manifest.json").exists()


def test_unhappy_source_is_faulty_dir():
    src = resolve_demo_source("unhappy", str(ROOT))
    assert src.name == "vingroup_faulty_pilot_dataset"
    assert (src / "fault_manifest.json").is_file()


def test_unhappy_incident_fixture_has_focus_case():
    import json
    cases = json.loads((ROOT / "fixtures/demo/unhappy_incidents.json").read_text())
    ids = {c["incident_id"] for c in cases}
    assert "inc-5c6fd288" in ids
    assert len(cases) == 8


def test_landing_has_no_fake_rca():
    landing = (ROOT / "frontend/src/pages/LandingPage.tsx").read_text()
    assert "99.8%" not in landing
    assert "Automated RCA Accuracy" not in landing

def test_steward_queue_has_gps_103():
    facts = (ROOT / "frontend/src/demo/pilotFacts.ts").read_text()
    dash = (ROOT / "frontend/src/pages/ExecutiveDashboard.tsx").read_text()
    assert "gpsOutsideHanoi: 103" in facts
    assert "gpsOutsideHanoi" in dash


def test_unhappy_live_reboots_on_story_change():
    ws = (ROOT / "frontend/src/pages/AgentChatWorkspace.tsx").read_text()
    assert "bootToken" in ws
    assert "hitlBootsInFlight" in ws or "runStartedRef" in ws
    rules = (ROOT / "frontend/src/components/workspace/QualityRulesTab.tsx").read_text()
    assert "datatrust:agent-trace" in rules

def test_api_reads_both_jwt_keys_not_mock():
    api = (ROOT / "frontend/src/services/api.ts").read_text()
    assert "datatrust_jwt_token" in api
    assert "datatrust-token" in api
    assert "ensureDemoAuth" in api
    assert "mock-jwt-token-datatrust-v3" not in api

def test_snapshot_clears_traces_and_chat():
    src = (ROOT / "src/api/routes/system.py").read_text()
    assert "DELETE FROM agent_traces" in src
    assert "clear_messages" in src


def test_ensure_demo_auth_forces_steward():
    api = (ROOT / "frontend/src/services/api.ts").read_text()
    assert "role === 'steward'" in api
    assert "username: 'steward'" in api
    store = (ROOT / "frontend/src/stores/authStore.ts").read_text()
    assert "usr_steward_01" in store
    assert "admin@datatrust.os" not in store


def test_saigon_clock_and_honest_tokens():
    labels = (ROOT / "frontend/src/demo/stewardLabels.ts").read_text()
    assert "Asia/Saigon" in labels
    assert "Number(raw.tokens" in labels

def test_auth_store_uses_user_profile_not_username_string():
    store = (ROOT / "frontend/src/stores/authStore.ts").read_text()
    assert "profileFromAuth" in store
    assert "user_profile" in store


def test_saigon_clock_does_not_double_offset():
    labels = (ROOT / "frontend/src/demo/stewardLabels.ts").read_text()
    assert "hasZone" in labels
    assert '+07:00' in labels

def test_health_hides_when_warehouse_has_soc_or_open():
    engine = (ROOT / "src/services/dataset_engine.py").read_text()
    assert "hide_sample_health_if_warehouse_faults" in engine
    assert "battery_soc < 0" in engine
    assert "status = 'OPEN'" in engine
    routes = (ROOT / "src/api/routes/__init__.py").read_text()
    assert 'c.get("dtype", c.get("data_type"' in routes or "data_type" in routes
    ui = (ROOT / "frontend/src/components/workspace/DataProfilerTab.tsx").read_text()
    assert "warehouseFaults" in ui


def test_profile_summary_uses_data_type_alias():
    engine = (ROOT / "src/services/dataset_engine.py").read_text()
    assert 'setdefault("dtype"' in engine
    routes = (ROOT / "src/api/routes/__init__.py").read_text()
    assert 'c.get("dtype", c.get("data_type"' in routes or 'c.get("data_type")' in routes
    assert "emitted_actions" in routes

def test_unhappy_health_is_critical_not_not_measured():
    routes = (ROOT / "src/api/routes/__init__.py").read_text()
    engine_py = (ROOT / "src/services/dataset_engine.py").read_text()
    assert "hide_sample_health_if_warehouse_faults" in engine_py or "warehouse_faults" in routes
    datasets = (ROOT / "src/api/routes/datasets.py").read_text()
    assert "profile_rows" in datasets
    ui = (ROOT / "frontend/src/components/workspace/DataProfilerTab.tsx").read_text()
    assert "story" in ui
    assert "Critical" in ui
    assert "Critical" in ui
    assert "warehouseFaults" in ui
    assert "SoC<0 =" in ui
    assert "OPEN =" in ui
    assert "&& !warehouseFaults" in ui  # hold releases once SoC<0/OPEN arrive
    ws = (ROOT / "frontend/src/pages/AgentChatWorkspace.tsx").read_text()
    assert "setStream([])" in ws
    assert "active={rightTab === 'tab-profiler'}" in ws
    assert "hidden={rightTab !== 'tab-profiler'}" in ws

def test_story_switch_keeps_one_profile_summary():
    ws = (ROOT / "frontend/src/pages/AgentChatWorkspace.tsx").read_text()
    assert "messagesForStory" in ws

def test_happy_snapshot_reloads_after_unhappy():
    bar = (ROOT / "frontend/src/demo/DemoStoryBar.tsx").read_text()
    assert "sessionStorage.setItem('dt-snap', mode)" in bar
    assert "loaded.current === 'happy'" in bar
    assert "loaded.current = null" in bar
    assert "sessionStorage.getItem('dt-snap') === 'happy'" not in bar


def test_profiler_wipes_grade_on_story_change():
    ui = (ROOT / "frontend/src/components/workspace/DataProfilerTab.tsx").read_text()
    assert "setProfile(null)" in ui
    assert "fetchProfile" in ui
    assert "warehouseFaults" in ui


def test_hitl_opens_sandbox_after_approve():
    ui = (ROOT / "frontend/src/components/workspace/QualityRulesTab.tsx").read_text()
    assert "Run sandbox" in ui
    assert "approvalsApi.authorize" in ui
    assert "hitlApi.execute(" not in ui
    assert "hitlApi.getSandbox" in ui
    assert "SandboxDiff" in ui
    assert "Execute disabled · sandbox not run · quarantine=0" in ui
    assert 'data-testid="hitl-preview-before-approve"' in ui
    assert 'data-testid="hitl-sandbox-preview"' in ui
    assert 'data-testid="btn-rule-preview"' in ui
    assert "hitlApi.sandboxPreview" in ui


def test_traces_surfaces_existing_event_hash_only():
    ui = (ROOT / "frontend/src/components/workspace/AgentTracesTab.tsx").read_text()
    assert "hitlApi.history" in ui
    assert "event_hash" in ui
    assert "a1b2c3d4e5f6" not in ui


def test_vin_uses_data_new_60():
    bar = (ROOT / "frontend/src/demo/DemoStoryBar.tsx").read_text()
    assert "60 VIN" in bar

def test_flash_hold_happy_99_1_and_unhappy_172_8():
    ui = (ROOT / "frontend/src/components/workspace/DataProfilerTab.tsx").read_text()
    bar = (ROOT / "frontend/src/demo/DemoStoryBar.tsx").read_text()
    facts = (ROOT / "frontend/src/demo/pilotFacts.ts").read_text()
    assert "holdHealth" in ui
    assert "holdPendingHealth" in ui
    assert "holdUnhappyHealth" in ui
    assert "99.1" in ui
    assert "dt-snap-pending" in bar
    assert "172 SoC / 8 OPEN" in bar
    assert "socBelowZero: 172" in facts
    assert "openIncidents: 8" in facts
    assert "writeWarehouseOverlay" in bar
    assert "soc_below_zero: res.soc_below_zero" in bar
    assert "datatrust:demo-snapshot'," in bar or 'datatrust:demo-snapshot"' in bar
    assert "readWarehouseOverlay" in ui


def test_unhappy_warehouse_faults_hide_sample_health_on_profiler_and_traces():
    """Unhappy + SoC<0/OPEN → Critical + measured counts, never Not measured / health 99.1."""
    ui = (ROOT / "frontend/src/components/workspace/DataProfilerTab.tsx").read_text()
    engine = (ROOT / "src/orchestrator/engine.py").read_text()
    ws = (ROOT / "frontend/src/pages/AgentChatWorkspace.tsx").read_text()

    assert "active?: boolean" in ui
    assert "fetchProfile" in ui
    assert "if (!active) return" in ui
    assert "SoC<0 =" in ui
    assert "OPEN =" in ui
    assert "warehouseFaults && !holdHealth" in ui
    grade = ui.split("const healthGrade = useMemo", 1)[1].split("}, [", 1)[0]
    assert "Critical" in grade
    assert "warehouseFaults" in grade

    assert "hidden={rightTab !== 'tab-traces'}" in ws
    assert "hidden={rightTab !== 'tab-profiler'}" in ws
    assert "HITL_STOP_PROMPT" in ws
    traces = (ROOT / "frontend/src/components/workspace/AgentTracesTab.tsx").read_text()
    assert "sendChatMessage" not in traces


def test_hitl_approve_is_not_execute():
    ui = (ROOT / "frontend/src/components/workspace/QualityRulesTab.tsx").read_text()
    approve = ui.split("const handleApprove")[1].split("const handleConfirmReject")[0]
    assert "hitlApi.approve" in approve
    assert "hitlApi.execute" not in approve
    assert "approvalsApi.authorize" in ui
    assert "hitlApi.execute(" not in ui
    assert "Execute disabled · sandbox not run · quarantine=0" in ui



def test_traces_api_does_not_hardcode_thought_none():
    src = (ROOT / "src/api/traces.py").read_text()
    assert '"thought": None' not in src
    assert "_pass_through_thought" in src
    assert "tool_about" in src
    assert "tool_title" in src


def test_log_trace_keeps_thought_and_tool_about():
    engine = (ROOT / "src/orchestrator/engine.py").read_text()
    assert "def _log_trace" in engine
    assert "tool_about" in engine
    assert "_pass_thought(step.thought)" in engine
    assert "thought or content[:200]" not in engine
    log_fn = engine.split("def _log_trace", 1)[1]
    assert '""' not in log_fn.split("except Exception")[0] or "tool_about" in log_fn
    assert "status=\"running\"" in engine or 'status="running"' in engine


def test_traces_tab_steward_beat_and_running_card():
    ui = (ROOT / "frontend/src/components/workspace/AgentTracesTab.tsx").read_text()
    assert "steward-beat" in ui
    assert "Now running" in ui
    assert "tool_title" in ui
    assert "tool_about" in ui
    assert "No measured traces" in ui
    assert "Technical detail" in ui
    assert "Why this tool" in ui


def test_steward_catalog_has_profile_dataset():
    labels = (ROOT / "frontend/src/demo/stewardLabels.ts").read_text()
    assert "TOOL_CATALOG" in labels
    assert "profile_dataset" in labels
    assert "scans nulls, types, health" in labels


def test_chat_used_chip_no_observation_dump():
    agent = (ROOT / "frontend/src/components/chat/AgentMessage.tsx").read_text()
    chat = (ROOT / "frontend/src/components/chat/ChatMessage.tsx").read_text()
    assert "Used " in agent
    assert "used-tool-chip" in agent
    assert "Used chip" in chat
    assert "Tool Observation" not in agent
    assert "renderFormattedContent(content.replace(/^Observation:" not in agent
    assert "Thought:" in chat


def test_unwrap_nested_function_call_names_propose():
    from src.orchestrator.engine import unwrap_tool_call
    name, args = unwrap_tool_call({
        "id": "call_1",
        "type": "function",
        "function": {
            "name": "propose_quality_rules",
            "arguments": '{"dataset_key": "vingroup_pilot"}',
        },
    })
    assert name == "propose_quality_rules"
    assert args.get("dataset_key") == "vingroup_pilot"
    flat_name, _ = unwrap_tool_call({"name": "profile_dataset", "arguments": {}})
    assert flat_name == "profile_dataset"
    empty_name, empty_args = unwrap_tool_call({"type": "function", "function": {}})
    assert empty_name == ""
    assert empty_args == {}


def test_missing_requested_tools_forces_propose_after_profile_only():
    from src.api.routes import missing_requested_tools
    prompt = "Profile this dataset and propose quality rules. Stop for HITL review."
    assert missing_requested_tools(prompt, ["profile_dataset", "FINISH"]) == ["detect_anomalies", "propose_quality_rules"]
    assert missing_requested_tools(prompt, ["profile_dataset", "detect_anomalies", "propose_quality_rules"]) == []
    vi = "Khảo sát dữ liệu và đề xuất luật chất lượng. Dừng HITL."
    assert missing_requested_tools(vi, ["profile_dataset"]) == ["detect_anomalies", "propose_quality_rules"]


def test_missing_requested_tools_skips_second_propose_when_beat_exists():
    """If a named Propose beat already exists, chat/send must not force-run a second."""
    routes = (ROOT / "src/api/routes/__init__.py").read_text()
    assert "def missing_requested_tools" in routes
    assert "def _session_has_tool_beat" in routes
    assert "if not _session_has_tool_beat(session_id, action)" in routes
    force = routes.split("for tool_name in missing_requested_tools", 1)[1]
    guard = force.split("executed_tools", 1)[0]
    assert "if _session_has_tool_beat(session_id, tool_name)" in guard
    assert "continue" in guard
    from src.api.routes import missing_requested_tools, _session_has_tool_beat
    from src.orchestrator.engine import ReActEngine, ReActStep
    import uuid
    prompt = "Profile this dataset and propose quality rules. Stop for HITL review."
    assert missing_requested_tools(prompt, ["profile_dataset", "FINISH"]) == ["detect_anomalies", "propose_quality_rules"]
    sid = f"qa-no-dup-propose-{uuid.uuid4().hex}"
    assert _session_has_tool_beat(sid, "propose_quality_rules") is False
    eng = ReActEngine(tools=type("T", (), {"get": lambda self, n: None})())
    eng.tools = type("T", (), {"get": lambda self, n: None})()
    eng._log_trace(sid, ReActStep(1, "", "propose_quality_rules", {"dataset_key": "vingroup_pilot"},
                                  observation='{"proposals": [{}, {}, {}], "count": 3}'), status="done")
    assert _session_has_tool_beat(sid, "propose_quality_rules") is True
    assert _session_has_tool_beat(sid, "default_api:propose_quality_rules") is True
    missing = missing_requested_tools(prompt, ["profile_dataset", "FINISH"])
    assert missing == ["detect_anomalies", "propose_quality_rules"]
    assert _session_has_tool_beat(sid, "propose_quality_rules") is True


def test_chat_send_backfills_missing_propose_and_logs_trace():
    routes = (ROOT / "src/api/routes/__init__.py").read_text()
    assert "def missing_requested_tools" in routes
    assert "react_engine._log_trace" in routes
    assert 'status="running"' in routes or "status=\"running\"" in routes or 'status="running"' in routes
    engine = (ROOT / "src/orchestrator/engine.py").read_text()
    assert "def unwrap_tool_call" in engine
    assert "coalesce(tool_name, action, '')" in engine
    assert 'if not tool_name or tool_name in ("FINISH", "ABSTAIN", "FINISH_DEFAULT")' in engine
    traces = (ROOT / "src/api/traces.py").read_text()
    assert 'if action in ("FINISH", "ABSTAIN", "FINISH_DEFAULT") or not action' in traces
    ui = (ROOT / "frontend/src/components/workspace/AgentTracesTab.tsx").read_text()
    assert "steward-beat" in ui
    assert "Why this tool" in ui
    assert "selectedTool" in ui
    assert "def _seed_running_profile" in engine
    assert "asyncio.to_thread" in routes


def test_log_trace_persists_profile_and_propose_beats():
    """Named Profile + Propose must both survive _log_trace (no step_index clobber)."""
    import uuid
    from fastapi.testclient import TestClient
    from src.main import app
    from src.orchestrator.engine import ReActEngine, ReActStep

    sid = f"qa-two-beats-{uuid.uuid4().hex}"
    eng = ReActEngine(tools=type("T", (), {"get": lambda self, n: None})())
    eng.tools = type("T", (), {"get": lambda self, n: None})()
    eng._log_trace(sid, ReActStep(0, "", "profile_dataset", {"dataset_key": "vingroup_pilot"},
                                  observation='{"total_rows": 10, "columns_count": 2}'), status="done")
    eng._log_trace(sid, ReActStep(1, "", "propose_quality_rules", {"dataset_key": "vingroup_pilot"},
                                  observation='{"proposals": [{}, {}, {}], "count": 3}'), status="done")
    client = TestClient(app, headers={"X-User-Role": "Admin"})
    steps = client.get(f"/api/v1/traces/{sid}").json()["steps"]
    names = {s.get("tool_name") or s.get("tool") or s.get("action") for s in steps}
    assert "profile_dataset" in names
    assert "propose_quality_rules" in names

def test_right_panel_tabs_stay_mounted():
    """Tab click / collapse must not remount Profiler/Traces/Rules/Split (wipes numbers)."""
    ws = (ROOT / "frontend/src/pages/AgentChatWorkspace.tsx").read_text()
    assert "rightTab === 'tab-traces' &&" not in ws
    assert "rightTab === 'tab-profiler' &&" not in ws
    assert "rightTab === 'tab-rules' &&" not in ws
    assert "rightTab === 'tab-split' &&" not in ws
    assert "{rightPanelOpen && (" not in ws  # aside must stay mounted; expand pill may use {!rightPanelOpen
    assert "hidden={rightTab !== 'tab-traces'}" in ws
    assert "hidden={rightTab !== 'tab-profiler'}" in ws
    assert "hidden={rightTab !== 'tab-rules'}" in ws
    assert "hidden={rightTab !== 'tab-split'}" in ws
    assert "onClick={() => setRightTab('tab-traces')}" in ws
    assert "onClick={() => setRightTab('tab-profiler')}" in ws
    assert "onClick={() => setRightTab('tab-rules')}" in ws
    assert "onClick={() => setRightTab('tab-split')}" in ws
    assert "loadSnapshot" not in ws.split("RIGHT PANEL")[1].split("RULE EDIT MODAL")[0]
    css = (ROOT / "frontend/src/assets/styles.css").read_text()
    assert "right-panel-collapsed .right-panel" in css
    assert "translateX(100%)" in css or "display: none" in css



def test_first_run_cannot_force_log_a_second_propose():
    """First Unhappy Profile & Propose must not force-log a second Propose."""
    from src.api.routes import missing_requested_tools, _session_has_tool_beat
    from src.orchestrator.engine import ReActEngine, ReActStep
    import uuid
    from fastapi.testclient import TestClient
    from src.main import app

    prompt = "Profile this dataset and propose quality rules. Stop for HITL review."
    # Profile-then-FINISH still force-runs once
    assert missing_requested_tools(prompt, ["profile_dataset", "FINISH"]) == ["detect_anomalies", "propose_quality_rules"]
    # LLM already ran Propose (canonical or alias) — do not force a second
    assert missing_requested_tools(prompt, ["profile_dataset", "detect_anomalies", "propose_quality_rules"]) == []
    assert missing_requested_tools(prompt, ["profile_dataset", "detect_anomalies", "quality_rule_proposer"]) == []
    assert missing_requested_tools(prompt, ["profile_dataset", "default_api:propose_quality_rules"]) == ["detect_anomalies"]

    sid = f"qa-first-run-one-propose-{uuid.uuid4().hex}"
    eng = ReActEngine(tools=type("T", (), {"get": lambda self, n: None})())
    eng.tools = type("T", (), {"get": lambda self, n: None})()
    eng._log_trace(
        sid,
        ReActStep(1, "", "quality_rule_proposer", {"dataset_key": "vingroup_pilot"},
                  observation='{"proposals": [{}, {}, {}], "count": 3}'),
        status="done",
    )
    assert _session_has_tool_beat(sid, "propose_quality_rules") is True
    assert eng._skip_duplicate_propose(sid, "propose_quality_rules") is True
    # second log (canonical name, new step_index) must not insert another Propose row
    eng._log_trace(
        sid,
        ReActStep(2, "", "propose_quality_rules", {"dataset_key": "vingroup_pilot"},
                  observation='{"proposals": [{}, {}, {}], "count": 3}'),
        status="done",
    )
    client = TestClient(app, headers={"X-User-Role": "Admin"})
    steps = client.get(f"/api/v1/traces/{sid}").json()["steps"]
    propose = [
        s for s in steps
        if (s.get("tool_name") or s.get("tool") or s.get("action") or "").replace("default_api:", "")
        in ("propose_quality_rules", "quality_rule_proposer")
    ]
    assert len(propose) == 1

    # source-inspection: first Unhappy bootstrap cannot POST chat twice
    ws = (ROOT / "frontend/src/pages/AgentChatWorkspace.tsx").read_text()
    handle = ws.split("const handleRunFullPipeline")[1].split("}, [")[0]
    assert "sendChatMessage" in handle
    assert "hitlBootsInFlight" in ws
    assert "proposeStartedRef" in ws
    routes = (ROOT / "src/api/routes/__init__.py").read_text()
    force = routes.split("for tool_name in missing_requested_tools", 1)[1]
    guard = force.split("step = ReActStep", 1)[0]
    assert "if _session_has_tool_beat(session_id, tool_name)" in guard
    assert "_skip_duplicate_propose" in guard
    assert "continue" in guard
    engine = (ROOT / "src/orchestrator/engine.py").read_text()
    log_fn = engine.split("def _log_trace", 1)[1]
    assert "_skip_duplicate_propose" in log_fn


def test_hitl_header_counts_the_cards_that_render():
    """Header Proposed/Approved must match card pills; empty only when zero cards."""
    rules = (ROOT / "frontend/src/components/workspace/QualityRulesTab.tsx").read_text()
    api = (ROOT / "frontend/src/services/api.ts").read_text()
    hitl = (ROOT / "src/api/hitl.py").read_text()

    assert "function ruleCardStatus" in rules
    assert ".trim()" in rules.split("function ruleCardStatus", 1)[1].split("export const QualityRulesTab", 1)[0]
    assert "const proposedCount" in rules
    assert "pending" in rules.split("const proposedCount", 1)[1].split("const approvedCount", 1)[0]
    assert "const approvedCount" in rules
    assert "ruleCardStatus" in rules
    assert "proposals.length === 0" in rules or "totalCount" in rules
    # unlabeled / queued still render as PROPOSED (same helper as header)
    helper = rules.split("function ruleCardStatus", 1)[1].split("export const QualityRulesTab", 1)[0]
    assert "queued" in helper or "return 'proposed'" in helper

    approve = rules.split("const handleApprove")[1].split("const handleConfirmReject")[0]
    assert "hitlApi.approve" in approve
    assert "fetchRules({ silent: true })" in approve
    assert "hitlApi.execute" not in approve

    assert "include_active" in hitl or "queue" in api
    assert "approved" in hitl.split("if include_active", 1)[1].split("else:", 1)[0]
    assert "keptApproved" in rules
    assert "keptApproved" in rules


def test_hitl_stop_engine_allowlist_refuses_clean():
    """HITL-stop may only run profile/propose; clean/search/list never execute or write a done beat."""
    engine = (ROOT / "src/orchestrator/engine.py").read_text()
    assert "def _is_hitl_stop" in engine
    assert "def _allow_hitl_tool" in engine
    assert "HITL_ALLOWED_TOOLS" in engine or "HITL_STOP_ALLOWED_TOOLS" in engine
    allow_src = engine
    if "HITL_ALLOWED_TOOLS = frozenset" in engine:
        allow_src = engine.split("HITL_ALLOWED_TOOLS = frozenset", 1)[1].split("})", 1)[0]
    elif "HITL_STOP_ALLOWED_TOOLS = frozenset" in engine:
        allow_src = engine.split("HITL_STOP_ALLOWED_TOOLS = frozenset", 1)[1].split("})", 1)[0]
    for allowed in ("profile_dataset", "propose_quality_rules", "quality_rule_proposer"):
        assert allowed in allow_src
    run_fn = engine.split("def run(", 1)[1].split("def _parse_response", 1)[0]
    assert "self.tools.execute" in run_fn
    # allowlist check sits after tool-name parse and before every execute
    assert "_allow_hitl_tool" in run_fn or "_hitl_refuse" in run_fn
    first_exec = run_fn.find("self.tools.execute")
    before_first = run_fn[:first_exec]
    assert "_allow_hitl_tool" in before_first or "_hitl_refuse" in before_first
    # both execute branches (native tool_calls + text Action:) are guarded
    assert run_fn.count("self.tools.execute") >= 4
    assert before_first.count("_allow_hitl_tool") + before_first.count("_hitl_refuse") >= 1

    routes = (ROOT / "src/api/routes/__init__.py").read_text()
    assert "def missing_requested_tools" in routes
    miss = routes.split("def missing_requested_tools", 1)[1].split("@router.post", 1)[0]
    assert "propose_quality_rules" in miss
    engine_refused = (ROOT / "src/orchestrator/engine.py").read_text()
    assert "clean_database" in engine_refused.split("HITL_REFUSED_TOOLS", 1)[1].split(")", 1)[0]
    assert "algolia_search" in engine_refused.split("HITL_REFUSED_TOOLS", 1)[1].split(")", 1)[0]
    force = routes.split("for tool_name in missing_requested_tools", 1)[1]
    guard = force.split("step = ReActStep", 1)[0]
    assert "clean_database" in guard
    assert "continue" in guard

    from src.orchestrator.engine import (
        _is_hitl_stop,
        _allow_hitl_tool,
        ReActEngine,
        HITL_ALLOWED_TOOLS,
    )
    from src.api.routes import missing_requested_tools
    from src.services.llm import LLMResponse

    assert _is_hitl_stop("Profile this dataset and propose quality rules. Stop for HITL review.")
    assert _is_hitl_stop("Khảo sát dữ liệu và đề xuất luật chất lượng. Dừng HITL.")
    assert _is_hitl_stop("không clean the warehouse")
    assert _is_hitl_stop("Do not clean, quarantine, or execute any writes.")
    assert not _is_hitl_stop("Just count the rows in telemetry")

    assert _allow_hitl_tool("profile_dataset") is True
    assert _allow_hitl_tool("propose_quality_rules") is True
    assert _allow_hitl_tool("quality_rule_proposer") is True
    assert _allow_hitl_tool("default_api:propose_quality_rules") is True
    assert _allow_hitl_tool("clean_database") is False
    assert _allow_hitl_tool("algolia_search") is False
    assert _allow_hitl_tool("list_datasets") is False
    assert HITL_ALLOWED_TOOLS >= {
        "profile_dataset",
        "propose_quality_rules",
        "quality_rule_proposer",
    }
    assert "clean_database" not in HITL_ALLOWED_TOOLS

    prompt = "Profile this dataset and propose quality rules. Stop for HITL review."
    assert missing_requested_tools(prompt, ["profile_dataset", "FINISH"]) == ["detect_anomalies", "propose_quality_rules"]
    assert missing_requested_tools(prompt, ["profile_dataset", "detect_anomalies", "propose_quality_rules"]) == []
    assert "clean_database" not in missing_requested_tools(prompt, ["profile_dataset"])
    assert "algolia_search" not in missing_requested_tools(prompt, [])
    assert "list_datasets" not in missing_requested_tools(prompt, [])

    class _SeqLLM:
        def __init__(self, names):
            self.names = list(names)
        def chat(self, messages, tools=None):
            if self.names:
                name = self.names.pop(0)
                return LLMResponse(
                    content=f"Thought: next\nAction: {name}\nAction Input: {{}}",
                    tool_calls=[{"name": name, "arguments": {}}],
                )
            return LLMResponse(content="Thought: done\nAction: FINISH\nAction Input: {}")

    class _RecTools:
        def __init__(self):
            self.executed = []
            self.tool_names = [
                "profile_dataset",
                "propose_quality_rules",
                "clean_database",
                "algolia_search",
                "list_datasets",
            ]
        def list_tools(self):
            return [{"function": {"name": n, "description": n}} for n in self.tool_names]
        def execute(self, name, args):
            self.executed.append(name)
            out = {"ok": True}
            if "propose" in name:
                out["proposals"] = [{}, {}, {}]
                out["count"] = 3
            return type("R", (), {"output_data": out})()
        def get(self, n):
            return None

    tools = _RecTools()
    eng = ReActEngine(llm=_SeqLLM(["clean_database", "algolia_search", "list_datasets", "propose_quality_rules"]), tools=tools, max_steps=6)
    result = eng.run("Profile and propose quality rules. Stop for HITL review. Do not clean, quarantine, or execute.")
    assert "clean_database" not in tools.executed
    assert "algolia_search" not in tools.executed
    assert "list_datasets" not in tools.executed
    assert any(_allow_hitl_tool(n) for n in tools.executed) or "propose_quality_rules" in [s.action for s in result.steps]
    assert "clean_database" not in [s.action for s in result.steps]
    assert result.status in ("completed", "max_steps")

