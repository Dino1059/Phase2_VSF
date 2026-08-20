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
    assert "forceLive" in ws
    assert "bootToken" in ws
    assert "datatrust:agent-trace" in ws

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
    assert "health_cell" in routes
    assert 'health_cell = "—"' in routes
    ui = (ROOT / "frontend/src/components/workspace/DataProfilerTab.tsx").read_text()
    assert "warehouseFaults" in ui


def test_profile_summary_uses_data_type_alias():
    engine = (ROOT / "src/services/dataset_engine.py").read_text()
    assert 'setdefault("dtype"' in engine
    routes = (ROOT / "src/api/routes/__init__.py").read_text()
    assert 'c.get("data_type")' in routes
    assert "emitted_actions" in routes

def test_unhappy_health_is_critical_not_not_measured():
    routes = (ROOT / "src/api/routes/__init__.py").read_text()
    assert "warehouse_faults" in routes
    assert "🔴 Critical" in routes
    datasets = (ROOT / "src/api/routes/datasets.py").read_text()
    assert "profile_rows" in datasets
    assert "warehouse_soc_below_zero" in datasets
    ui = (ROOT / "frontend/src/components/workspace/DataProfilerTab.tsx").read_text()
    assert "story" in ui
    ws = (ROOT / "frontend/src/pages/AgentChatWorkspace.tsx").read_text()
    assert "setStream([])" in ws

def test_story_switch_keeps_one_profile_summary():
    ws = (ROOT / "frontend/src/pages/AgentChatWorkspace.tsx").read_text()
    assert "messagesForStory" in ws
    assert "isProfileSummary" in ws
    assert "HAPPY · clean CSVs" in ws

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
    assert "hitlApi.execute" in ui
    assert "Execute disabled · sandbox not run · quarantine=0" in ui


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


def test_hitl_approve_is_not_execute():
    ui = (ROOT / "frontend/src/components/workspace/QualityRulesTab.tsx").read_text()
    approve = ui.split("const handleApprove")[1].split("const handleReject")[0]
    assert "hitlApi.approve" in approve
    assert "hitlApi.execute" not in approve
    assert "approvalsApi.authorize" in ui
    assert "hitlApi.execute" in ui
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
