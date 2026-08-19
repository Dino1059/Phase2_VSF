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

