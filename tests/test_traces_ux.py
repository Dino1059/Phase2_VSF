"""Traces / step-by-step UX gate.

These assertions encode the Build Phase trail:
  tool_name + human tool_about, thought from the real payload (never invented),
  AgentTracesTab who/title/purpose/Done (not the word "completed"),
  chat chip instead of raw Thought:.

Several tests MUST fail on today's dump (thought hard-nulled, tool_about missing,
"completed" fallback, Thought: bubble) and pass once Product lands the trail.
Empty traces / no-fake-hash / no-kafka-theater cases already hold.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from src.api.traces import normalize_trace_step
from src.main import app
from src.tools.chat_tools import ProfileDatasetTool, ProposeQualityRulesTool

ROOT = Path(__file__).resolve().parents[1]
_FAKE_SK = "sk-" + "proj-" + "EXAMPLETESTKEY" + "1234567890abcd"


def _row(
    *,
    step: int = 1,
    thought: str | None = "Need a column profile before proposing rules.",
    action: str = "profile_dataset",
    tool_name: str = "profile_dataset",
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


def _about_ok(about: object, tool_cls) -> None:
    assert isinstance(about, str) and about.strip(), "tool_about missing"
    assert about.strip() != tool_cls.name
    desc = (tool_cls.description or "").strip()
    if about.strip() == desc:
        return
    needles = [w for w in ("scan", "null", "health", "column", "profile", "dataset", "rule") if w in desc.lower()]
    assert any(w in about.lower() for w in needles), (
        f"tool_about must come from BaseTool.description or a catalog, got {about!r}"
    )


# --- API: fail today on hard-null thought / missing tool_about ---


def test_normalize_passes_through_real_thought():
    thought = "Need a column profile before proposing rules."
    card = normalize_trace_step(_row(thought=thought))
    assert card.get("thought") == thought
    assert thought not in (card.get("summary_done") or "")


def test_normalize_includes_tool_name_and_tool_about_from_description():
    card = normalize_trace_step(_row())
    assert card.get("tool_name") == "profile_dataset" or card.get("tool") == "profile_dataset"
    _about_ok(card.get("tool_about"), ProfileDatasetTool)

    propose = normalize_trace_step(
        _row(
            action="propose_quality_rules",
            tool_name="propose_quality_rules",
            thought="Propose HITL rules from the profile.",
            observation="Proposed 3 rules",
            tool_output='{"proposals": [{}, {}, {}], "count": 3}',
        )
    )
    assert propose.get("tool_name") == "propose_quality_rules" or propose.get("tool") == "propose_quality_rules"
    _about_ok(propose.get("tool_about"), ProposeQualityRulesTool)


def test_missing_thought_is_left_absent():
    card = normalize_trace_step(_row(thought=None))
    assert card.get("thought") in (None, "")
    assert "I will now" not in str(card.get("thought") or "")
    assert "step 1" not in (card.get("summary_done") or "").lower()


def test_done_summary_does_not_say_completed():
    card = normalize_trace_step(
        _row(
            thought=None,
            action="register_dataset",
            tool_name="register_dataset",
            tool_input=None,
            tool_output=None,
            observation=None,
            tokens=None,
            duration_ms=None,
        )
    )
    blob = (card.get("summary_done") or "").lower()
    assert "completed" not in blob
    assert "12 anomalies" not in blob
    assert "a1b2c3d4e5f6" not in blob


def test_trace_thought_redacts_secrets_without_nulling():
    raw = f"Checking dataset with key {_FAKE_SK}"
    card = normalize_trace_step(_row(thought=raw))
    thought = card.get("thought")
    assert thought not in (None, ""), "thought must not be hard-nulled"
    assert _FAKE_SK not in str(thought)
    assert "[REDACTED" in str(thought)


def test_empty_session_traces_are_empty():
    client = TestClient(app, headers={"X-User-Role": "Admin"})
    sid = f"qa-empty-traces-{uuid.uuid4().hex}"
    resp = client.get(f"/api/v1/traces/{sid}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("steps") == []
    blob = str(body).lower()
    assert "kafka" not in blob
    assert "a1b2c3d4e5f6" not in blob
    assert "industry" not in blob


def test_traces_api_returns_tool_about_and_thought():
    from src.db.connection import get_db

    sid = f"qa-traces-ux-{uuid.uuid4().hex}"
    thought = "Need a column profile before proposing rules."
    db = get_db()
    db.execute(
        "INSERT INTO agent_traces (id, session_id, agent_type, step_index, thought, action, "
        "tool_name, tool_input, tool_output, observation, tokens_used, duration_ms) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            f"tr-{uuid.uuid4().hex[:12]}",
            sid,
            "canonical_react_engine",
            1,
            thought,
            "profile_dataset",
            "profile_dataset",
            '{"dataset_key": "vingroup_pilot"}',
            '{"total_rows": 50000, "columns_count": 10, "status": "ok"}',
            "Sampled 50000 rows",
            120,
            640,
        ],
    )
    client = TestClient(app, headers={"X-User-Role": "Admin"})
    resp = client.get(f"/api/v1/traces/{sid}")
    assert resp.status_code == 200, resp.text
    steps = resp.json()["steps"]
    assert len(steps) == 1
    card = steps[0]
    assert card.get("tool_name") == "profile_dataset" or card.get("tool") == "profile_dataset"
    _about_ok(card.get("tool_about"), ProfileDatasetTool)
    assert card.get("thought") == thought
    assert "completed" not in (card.get("summary_done") or "").lower()


# --- Frontend AgentTracesTab ---


def test_agent_traces_tab_shows_who_title_purpose_done():
    ui = (ROOT / "frontend/src/components/workspace/AgentTracesTab.tsx").read_text()
    assert "actorLabel" in ui
    assert "summary_done" in ui
    assert "tool_about" in ui
    assert "tool_title" in ui
    assert "status" in ui
    assert "isVi ? 'xong' : 'done'" in ui or (": 'done'" in ui and "xong" in ui)


def test_agent_traces_tab_does_not_hardcode_completed_as_done():
    ui = (ROOT / "frontend/src/components/workspace/AgentTracesTab.tsx").read_text()
    labels = (ROOT / "frontend/src/demo/stewardLabels.ts").read_text()
    assert "${tool} completed" not in labels
    assert " completed`" not in labels
    assert "No measured summary." in ui or "summary_done" in ui
    # Status enum COMPLETED is fine; the Done summary must not be the word completed.
    assert "isVi ? 'xong' : 'done'" in ui or (": 'done'" in ui and "xong" in ui)


def test_map_trace_step_exposes_tool_about_not_completed_fallback():
    labels = (ROOT / "frontend/src/demo/stewardLabels.ts").read_text()
    assert "tool_about" in labels
    assert "tool_title" in labels or "humanTitle" in labels or "human_title" in labels
    assert "${tool} completed" not in labels


def test_io_collapsed_by_default():
    ui = (ROOT / "frontend/src/components/workspace/AgentTracesTab.tsx").read_text()
    assert "expandedSteps" in ui
    assert "View tool I/O" in ui
    assert "useState<Record<number, boolean>>({})" in ui
    assert "isExpanded &&" in ui


def test_empty_traces_tab_does_not_invent_steps():
    ui = (ROOT / "frontend/src/components/workspace/AgentTracesTab.tsx").read_text()
    assert "No measured traces" in ui
    assert "Nothing is invented here." in ui
    assert "Kafka" not in ui
    assert "a1b2c3d4e5f6" not in ui
    assert "industry" not in ui.lower()


def test_no_fake_hash_or_kafka_in_traces_tab():
    ui = (ROOT / "frontend/src/components/workspace/AgentTracesTab.tsx").read_text()
    traces_py = (ROOT / "src/api/traces.py").read_text()
    assert "a1b2c3d4e5f6" not in ui
    assert "a1b2c3d4e5f6" not in traces_py
    assert "kafka" not in traces_py.lower()
    assert "hitlApi.history" in ui
    assert "event_hash" in ui


def test_pilot_metrics_are_data_new_only():
    facts = (ROOT / "frontend/src/demo/pilotFacts.ts").read_text()
    assert "data_new" in facts
    assert "Not industry/eval theater" in facts
    assert "vins: 60" in facts
    bar = (ROOT / "frontend/src/demo/DemoStoryBar.tsx").read_text()
    assert "not a live Kafka stream" in bar
    assert "60 VIN" in bar


# --- Chat: no raw Thought:, tool-run is a chip ---


def test_chat_message_still_filters_thought_prefix():
    chat = (ROOT / "frontend/src/components/chat/ChatMessage.tsx").read_text()
    assert "startsWith('Thought:')" in chat
    assert "return null" in chat


def test_chat_does_not_render_raw_thought_as_bubble():
    agent = (ROOT / "frontend/src/components/chat/AgentMessage.tsx").read_text()
    assert "content.replace(/^Thought:" not in agent
    assert "ReAct Reasoning" not in agent
    assert "if (isThought)" in agent
    assert "return null" in agent


def test_chat_tool_run_is_a_followable_chip():
    agent = (ROOT / "frontend/src/components/chat/AgentMessage.tsx").read_text()
    chat = (ROOT / "frontend/src/components/chat/ChatMessage.tsx").read_text()
    ws = (ROOT / "frontend/src/pages/AgentChatWorkspace.tsx").read_text()
    combined = agent + chat + ws
    markers = (
        "used-tool-chip",
        "tool-run-chip",
        "toolRunChip",
        'data-testid="tool-run"',
        'data-testid="tool-run-chip"',
        'className="tool-run',
        "className={`tool-run",
    )
    assert any(m in combined for m in markers), (
        "A tool-run must render as a chip the steward can follow, not a Thought: blob"
    )



def test_missing_requested_tools_propose_only():
    from src.api.routes import missing_requested_tools

    assert missing_requested_tools(
        "Profile this dataset and propose quality rules. Stop for HITL.",
        ["profile_dataset"],
    ) == ["propose_quality_rules"]
    assert missing_requested_tools("just profile the dataset", ["profile_dataset"]) == []
    assert "profile_dataset" not in missing_requested_tools(
        "Profile and propose quality rules",
        [],
    )


def test_log_trace_writes_propose_steward_beat():
    from src.db.connection import get_db
    from src.orchestrator.engine import ReActEngine, ReActStep

    sid = f"qa-propose-beat-{uuid.uuid4().hex}"
    engine = ReActEngine()
    step = ReActStep(
        step_index=1,
        thought="",
        action="propose_quality_rules",
        action_input={"dataset_key": "vingroup_pilot"},
        observation='{"proposals": [{}, {}, {}], "count": 3}',
        duration_ms=12,
    )
    engine._log_trace(sid, step)
    rows = get_db().execute(
        "SELECT tool_name, status, observation FROM agent_traces WHERE session_id = ? AND tool_name = ?",
        [sid, "propose_quality_rules"],
    )
    assert rows, "propose must write a steward beat like profile"
    assert rows[0][0] == "propose_quality_rules"
    assert str(rows[0][1] or "").lower() in ("done", "success", "completed", "")


def test_seed_running_profile_writes_immediate_beat():
    from src.db.connection import get_db
    from src.orchestrator.engine import ReActEngine, ReActResult

    sid = f"qa-seed-profile-{uuid.uuid4().hex}"
    engine = ReActEngine()
    result = ReActResult(task="Profile this dataset", session_id=sid)
    engine._seed_running_profile(result, "Profile this dataset and propose quality rules", {"dataset_key": "vingroup_pilot"})
    rows = get_db().execute(
        "SELECT tool_name, status FROM agent_traces WHERE session_id = ?",
        [sid],
    )
    assert rows
    assert rows[0][0] == "profile_dataset"
    assert str(rows[0][1] or "").lower() in ("running", "in_progress")


def test_traces_tab_shows_pending_running_card():
    ui = (ROOT / "frontend/src/components/workspace/AgentTracesTab.tsx").read_text()
    ws = (ROOT / "frontend/src/pages/AgentChatWorkspace.tsx").read_text()
    routes = (ROOT / "src/api/routes/__init__.py").read_text()
    assert "pendingRun" in ui
    assert "now-running-card" in ui
    assert "pendingRun={waitingForBackendAgentEvents || isRunningPipeline}" in ws
    assert "asyncio.to_thread" in routes
    assert "missing_requested_tools" in routes
    force = routes.split("for tool_name in missing_requested_tools", 1)[1]
    assert "if _session_has_tool_beat(session_id, tool_name)" in force.split("executed_tools", 1)[0]


def test_propose_quality_rules_real_run_has_traces_beat_not_just_chip(monkeypatch):
    """Live click after e52727a: used-tool chip, no traces beat.

    Chat catalog chip is not a traces beat. A real propose_quality_rules run
    (nested Gemini tool_call -> persist/normalize) must produce a traces step
    with tool_name/action propose_quality_rules and a human tool_about.
    Empty sessions stay empty. Thoughts are not invented. No fake hashes.
    """
    from unittest.mock import MagicMock

    import pandas as pd

    from src.orchestrator.engine import ReActEngine
    from src.services.llm import GemmaLLMAdapter, LLMResponse
    from src.tools.base import ToolRegistry
    from src.tools import chat_tools as chat_tools_mod

    # Chip exists — not sufficient without a traces beat.
    agent = (ROOT / "frontend/src/components/chat/AgentMessage.tsx").read_text()
    chat = (ROOT / "frontend/src/components/chat/ChatMessage.tsx").read_text()
    labels = (ROOT / "frontend/src/demo/stewardLabels.ts").read_text()
    assert "used-tool-chip" in agent
    assert "propose_quality_rules" in labels
    assert "startsWith('Thought:')" in chat
    assert "if (isThought)" in agent and "return null" in agent

    sid = f"qa-propose-real-{uuid.uuid4().hex}"
    client = TestClient(app, headers={"X-User-Role": "Admin"})
    empty = client.get(f"/api/v1/traces/{sid}")
    assert empty.status_code == 200, empty.text
    assert empty.json().get("steps") == []
    empty_blob = str(empty.json()).lower()
    assert "kafka" not in empty_blob
    assert "a1b2c3d4e5f6" not in empty_blob

    tiny = pd.DataFrame(
        [
            {"soc_pct": 80.0, "battery_soc": 80.0},
            {"soc_pct": -2.0, "battery_soc": -2.0},
            {"soc_pct": 50.0, "battery_soc": 50.0},
        ]
    )
    monkeypatch.setattr(chat_tools_mod, "load_dataset", lambda *a, **k: tiny)

    registry = ToolRegistry()
    registry.register(ProposeQualityRulesTool())
    mock_llm = MagicMock(spec=GemmaLLMAdapter)
    mock_llm.chat.side_effect = [
        LLMResponse(
            content="",
            tool_calls=[
                {
                    "id": "call_propose",
                    "type": "function",
                    "function": {
                        "name": "propose_quality_rules",
                        "arguments": '{"dataset_key": "vingroup_pilot"}',
                    },
                }
            ],
            tokens_used=8,
        ),
        LLMResponse(
            content="Action: FINISH\nAction Input: {}",
            tokens_used=3,
        ),
    ]
    engine = ReActEngine(llm=mock_llm, tools=registry)
    engine.run(
        "Propose quality rules. Stop for HITL review.",
        context={"dataset_key": "vingroup_pilot", "session_id": sid},
        session_id=sid,
    )

    resp = client.get(f"/api/v1/traces/{sid}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "a1b2c3d4e5f6" not in str(body)
    assert "kafka" not in str(body).lower()
    propose = [
        s
        for s in (body.get("steps") or [])
        if (s.get("tool_name") == "propose_quality_rules"
            or s.get("action") == "propose_quality_rules"
            or s.get("tool") == "propose_quality_rules")
    ]
    assert propose, (
        "used-tool chip for propose_quality_rules is not a traces beat; "
        "persist/normalize must write tool_name/action propose_quality_rules"
    )
    card = propose[0]
    _about_ok(card.get("tool_about"), ProposeQualityRulesTool)
    assert card.get("thought") in (None, "")
    assert "I will now" not in str(card.get("thought") or "")
    assert "completed" not in (card.get("summary_done") or "").lower() or "rule" in (card.get("summary_done") or "").lower()

def test_force_log_does_not_duplicate_propose_when_already_ran(monkeypatch):
    """Live click after 7c40468: STEPS=3 because Propose was logged twice.

    LLM already persisted profile_dataset + propose_quality_rules. The chat/send
    missing_requested_tools force-run / force-log must not write a second
    propose_quality_rules beat. Empty sessions stay empty. No invented thoughts.
    No fake hashes.
    """
    import pandas as pd

    import src.api.routes as routes
    from src.orchestrator.engine import ReActEngine, ReActResult, ReActStep
    from src.tools import chat_tools as chat_tools_mod

    sid = f"qa-no-dup-propose-{uuid.uuid4().hex}"
    client = TestClient(app, headers={"X-User-Role": "Admin"})
    empty = client.get(f"/api/v1/traces/{sid}")
    assert empty.status_code == 200, empty.text
    assert empty.json().get("steps") == []
    empty_blob = str(empty.json()).lower()
    assert "kafka" not in empty_blob
    assert "a1b2c3d4e5f6" not in empty_blob
    assert "I will now" not in empty_blob

    tiny = pd.DataFrame(
        [
            {"soc_pct": 80.0, "battery_soc": 80.0},
            {"soc_pct": -2.0, "battery_soc": -2.0},
        ]
    )
    monkeypatch.setattr(chat_tools_mod, "load_dataset", lambda *a, **k: tiny)

    class EngineProposeAlreadyRan(ReActEngine):
        """LLM already wrote both beats; result.steps omits Propose so today's
        missing_requested_tools still force-logs a second Propose."""

        def run(self, task, context=None, session_id=None):
            sid_ = session_id or (context or {}).get("session_id") or "default"
            result = ReActResult(task=task, session_id=sid_)
            profile = ReActStep(
                step_index=0,
                thought="",
                action="profile_dataset",
                action_input={"dataset_key": "vingroup_pilot"},
                observation='{"total_rows": 3, "columns_count": 2, "status": "ok"}',
            )
            propose = ReActStep(
                step_index=1,
                thought="",
                action="propose_quality_rules",
                action_input={"dataset_key": "vingroup_pilot"},
                observation='{"proposals": [{}, {}, {}], "count": 3}',
            )
            self._log_trace(sid_, profile)
            self._log_trace(sid_, propose)
            result.steps = [
                profile,
                ReActStep(step_index=2, thought="", action="FINISH"),
            ]
            result.final_answer = "Profiled and proposed rules. Stop for HITL."
            result.status = "completed"
            return result

    monkeypatch.setattr(routes, "BoundedReActEngine", EngineProposeAlreadyRan)

    resp = client.post(
        "/api/v1/chat/send",
        json={
            "message": "Profile this dataset and propose quality rules. Stop for HITL review.",
            "session_id": sid,
            "dataset_key": "vingroup_pilot",
            "lang": "en",
        },
    )
    assert resp.status_code == 200, resp.text

    traces = client.get(f"/api/v1/traces/{sid}")
    assert traces.status_code == 200, traces.text
    body = traces.json()
    assert "a1b2c3d4e5f6" not in str(body)
    assert "kafka" not in str(body).lower()
    steps = body.get("steps") or []

    def _tool(step: dict) -> str:
        return str(step.get("tool_name") or step.get("action") or step.get("tool") or "")

    names = [_tool(s) for s in steps]
    assert names.count("profile_dataset") == 1, names
    assert names.count("propose_quality_rules") == 1, (
        "missing_requested_tools force-log must not write a second Propose "
        f"when Propose already ran; got {names}"
    )
    for card in steps:
        assert card.get("thought") in (None, "")
        assert "I will now" not in str(card.get("thought") or "")

def test_engine_skips_second_propose_execute_and_log(monkeypatch):
    """Tab remount / second HITL send must not re-run Propose (live STEPS 2→3)."""
    import pandas as pd
    from unittest.mock import MagicMock

    from src.orchestrator.engine import ReActEngine
    from src.services.llm import GemmaLLMAdapter, LLMResponse
    from src.tools.base import ToolRegistry
    from src.tools import chat_tools as chat_tools_mod
    from src.tools.chat_tools import ProposeQualityRulesTool

    engine_src = (ROOT / "src/orchestrator/engine.py").read_text()
    assert "def _skip_duplicate_propose" in engine_src
    assert "if self._skip_duplicate_propose" in engine_src

    tiny = pd.DataFrame(
        [
            {"soc_pct": 80.0, "battery_soc": 80.0},
            {"soc_pct": -2.0, "battery_soc": -2.0},
        ]
    )
    monkeypatch.setattr(chat_tools_mod, "load_dataset", lambda *a, **k: tiny)

    sid = f"qa-skip-dup-propose-{uuid.uuid4().hex}"
    client = TestClient(app, headers={"X-User-Role": "Admin"})
    assert client.get(f"/api/v1/traces/{sid}").json().get("steps") == []

    def _llm_propose_then_finish():
        mock_llm = MagicMock(spec=GemmaLLMAdapter)
        mock_llm.chat.side_effect = [
            LLMResponse(
                content="",
                tool_calls=[{
                    "id": "call_propose",
                    "type": "function",
                    "function": {
                        "name": "propose_quality_rules",
                        "arguments": '{"dataset_key": "vingroup_pilot"}',
                    },
                }],
                tokens_used=4,
            ),
            LLMResponse(content="Action: FINISH\nAction Input: {}", tokens_used=2),
        ]
        return mock_llm

    registry = ToolRegistry()
    registry.register(ProposeQualityRulesTool())
    engine = ReActEngine(llm=_llm_propose_then_finish(), tools=registry)
    engine.run(
        "Profile this dataset and propose quality rules. Stop for HITL review.",
        context={"dataset_key": "vingroup_pilot", "session_id": sid},
        session_id=sid,
    )

    first = client.get(f"/api/v1/traces/{sid}").json()["steps"]

    def _tool(step: dict) -> str:
        return str(step.get("tool_name") or step.get("action") or step.get("tool") or "")

    first_names = [_tool(s) for s in first]
    assert first_names.count("propose_quality_rules") == 1, first_names

    engine2 = ReActEngine(llm=_llm_propose_then_finish(), tools=registry)
    engine2.run(
        "Profile this dataset and propose quality rules. Stop for HITL review.",
        context={"dataset_key": "vingroup_pilot", "session_id": sid},
        session_id=sid,
    )
    second = client.get(f"/api/v1/traces/{sid}").json()["steps"]
    names = [_tool(s) for s in second]
    assert names.count("propose_quality_rules") == 1, (
        "second engine run must not execute/log another Propose; got " + str(names)
    )
    assert "a1b2c3d4e5f6" not in str(second)
    assert "kafka" not in str(second).lower()
    from src.api.routes import missing_requested_tools
    assert missing_requested_tools(
        "Profile this dataset and propose quality rules. Stop for HITL.",
        ["profile_dataset", "FINISH"],
    ) == ["propose_quality_rules"]

