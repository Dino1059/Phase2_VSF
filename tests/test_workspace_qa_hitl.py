"""QA gates for uploaded-dataset HITL: honest profile, scoped rules, traces JSON."""
import json
from types import SimpleNamespace

from src.api.routes import format_friendly_observation
from src.orchestrator.engine import json_preview
from src.services.dataset_engine import generate_rules_for_baseline, profile_rows
from src.tools.chat_tools import namespace_rule_id


def test_format_friendly_profile_uses_data_type_not_unknown():
    observation = json.dumps({
        "dataset_key": "uploaded_vingroup_pilot",
        "total_rows": 50000,
        "columns_count": 3,
        "health_score": None,
        "profile": {
            "data_health_score": None,
            "columns": [
                {"name": "soc_pct", "data_type": "FLOAT", "null_count": 0, "unique_count": 12, "total_count": 50000},
                {"name": "timestamp", "data_type": "DATETIME", "null_count": 0, "distinct_count": 1440, "total_count": 50000},
            ],
        },
    })
    md = format_friendly_observation("profile_dataset", observation, lang="en")
    assert "uploaded_vingroup_pilot" in md
    assert "`unknown`" not in md
    assert "`FLOAT`" in md
    assert "`DATETIME`" in md
    assert "99.0%" not in md
    assert "🟢 Excellent" not in md


def test_format_friendly_profile_no_default_perfect_health():
    observation = json.dumps({
        "dataset_key": "uploaded_vingroup_pilot",
        "total_rows": 10,
        "columns_count": 1,
        "profile": {"columns": [{"name": "vin", "data_type": "STRING", "null_count": 0, "unique_count": 3}]},
    })
    md = format_friendly_observation("profile_dataset", observation, lang="en")
    assert "100%" not in md
    assert "99.0%" not in md


def test_namespace_rule_id_is_dataset_scoped():
    rid = namespace_rule_id("uploaded_vingroup_pilot", "R1_A1")
    assert rid.startswith("uploaded_vingroup_pilot__")
    assert rid != "R1_A1"
    assert namespace_rule_id("other_ds", "R1_A1") != rid


def test_accel_negatives_do_not_become_range_or_health_hits():
    rows = [
        {"soc_pct": 80.0, "accel_z": -1.2, "telemetry_coverage": "full"},
        {"soc_pct": -2.0, "accel_z": 0.4, "telemetry_coverage": "full"},
    ]
    profile = profile_rows(rows)
    cols = {c["name"]: c for c in profile["columns"]}
    assert cols["accel_z"]["anomaly_count"] == 0
    assert cols["soc_pct"]["anomaly_count"] >= 1

    rules, _ = generate_rules_for_baseline("A1", profile)
    expr_by_col = {(r["column"], r["rule_type"]): r["expression"] for r in rules}
    assert ("soc_pct", "range") in expr_by_col
    assert ("accel_z", "range") not in expr_by_col
    assert all(r["column"] != "telemetry_coverage" for r in rules)


def test_json_preview_is_valid_json_when_truncated():
    blob = json.dumps({"columns": [{"name": f"c{i}"} for i in range(400)]})
    preview = json_preview(blob, limit=200)
    parsed = json.loads(preview)
    assert isinstance(parsed, dict)
    assert parsed.get("truncated") is True


def test_missing_requested_tools_forces_propose_after_profile_only():
    from src.api.routes import missing_requested_tools
    prompt = "Profile this dataset and propose quality rules. Stop for HITL review."
    assert missing_requested_tools(prompt, ["profile_dataset", "FINISH"]) == ["detect_anomalies", "propose_quality_rules"]
    assert missing_requested_tools(prompt, ["profile_dataset", "detect_anomalies", "propose_quality_rules"]) == []


def test_summarize_does_not_dump_raw_profile_json():
    from src.api.traces import _measured_summary
    obs = json.dumps({
        "dataset_key": "uploaded_vingroup_pilot",
        "total_rows": 50000,
        "columns_count": 10,
        "health_score": 100.0,
        "profile": {"columns": [{"name": "soc_pct"}]},
    })
    parsed = json.loads(obs)
    summary = _measured_summary("profile_dataset", None, parsed)
    assert "50,000 rows" in summary or "50000" in summary
    assert "vehicle_vin" not in summary


def test_hitl_prompt_does_not_append_leftover_dataset_list(monkeypatch):
    import src.api.routes as routes
    from fastapi.testclient import TestClient
    from src.main import app

    class FakeEngine:
        def __init__(self, **kwargs):
            pass

        def run(self, task, context=None, **kwargs):
            return SimpleNamespace(
                steps=[],
                final_answer="Profiled uploaded_vingroup_pilot. Stopping for HITL.",
                status="completed",
            )

    monkeypatch.setattr(routes, "BoundedReActEngine", FakeEngine)
    client = TestClient(app, headers={"X-User-Role": "Admin"})
    resp = client.post(
        "/api/v1/chat/send",
        json={
            "message": "Profile this dataset and propose quality rules. Do not clean, quarantine, or execute. Stop for HITL review.",
            "session_id": "dataset:uploaded_vingroup_pilot_qa",
            "dataset_key": "uploaded_vingroup_pilot",
            "lang": "en",
        },
    )
    assert resp.status_code == 200
    body = resp.json()["response"]
    assert "vinfast_bms" not in body
    assert "vgreen_telemetry" not in body


def test_hitl_bootstrap_does_not_call_clean_database():
    """HITL Profile & Propose must stop at Propose — no clean/search/list beats."""
    from pathlib import Path
    from src.orchestrator.engine import (
        HITL_BLOCKED_TOOLS,
        HITL_STOP_ALLOWED_TOOLS,
        is_hitl_blocked_tool,
        is_hitl_stop_prompt,
        is_propose_tool,
    )

    root = Path(__file__).resolve().parents[1]
    routes = (root / "src/api/routes/__init__.py").read_text()
    engine = (root / "src/orchestrator/engine.py").read_text()
    ws = (root / "frontend/src/pages/AgentChatWorkspace.tsx").read_text()

    prompt_en = "Profile this dataset and propose quality rules. Do not clean, quarantine, or execute. Stop for HITL review."
    prompt_vi = "Khảo sát dữ liệu và đề xuất luật chất lượng. Không làm sạch, không cách ly, không thực thi. Dừng lại để steward duyệt HITL."
    assert is_hitl_stop_prompt(prompt_en) is True
    assert is_hitl_stop_prompt(prompt_vi) is True
    assert is_hitl_stop_prompt("How many datasets are registered?") is False
    assert is_hitl_blocked_tool("clean_database") is True
    assert is_hitl_blocked_tool("algolia_search") is True
    assert is_hitl_blocked_tool("list_datasets") is True
    assert is_hitl_blocked_tool("profile_dataset") is False
    assert is_hitl_blocked_tool("propose_quality_rules") is False
    assert is_propose_tool("propose_quality_rules") is True
    assert "clean_database" in HITL_BLOCKED_TOOLS
    assert "profile_dataset" in HITL_STOP_ALLOWED_TOOLS
    assert "propose_quality_rules" in HITL_STOP_ALLOWED_TOOLS
    assert "quality_rule_proposer" in HITL_STOP_ALLOWED_TOOLS
    assert "clean_database" not in HITL_STOP_ALLOWED_TOOLS
    assert "algolia_search" not in HITL_STOP_ALLOWED_TOOLS
    assert "list_datasets" not in HITL_STOP_ALLOWED_TOOLS

    send = routes.split("async def send_chat_message", 1)[1].split("async def get_chat_history", 1)[0]
    assert "is_hitl_stop_prompt" in send
    assert "if not hitl_stop:" in send
    assert "CleanDatabaseTool()" in send.split("if not hitl_stop:", 1)[1]
    assert "ListDatasetsTool()" in send.split("if not hitl_stop:", 1)[1]
    assert "AlgoliaSearchTool()" in send
    assert "tool_allowlist" in send or "HITL_STOP_ALLOWED_TOOLS" in send

    assert "def is_hitl_blocked_tool" in engine
    assert "_hitl_refuse" in engine or "_allow_hitl_tool" in engine
    assert "_hitl_finish_after_propose" in engine
    assert "HITL_STOP_ALLOWED_TOOLS" in engine
    assert "HITL_STOP_PROMPT_EN" in ws
    assert "Stop for HITL review" in ws
    run_fn = engine.split("def run(", 1)[1].split("def _parse_response", 1)[0]
    exec_idx = run_fn.find("self.tools.execute")
    allow_idx = run_fn.find("_allow_hitl_tool")
    refuse_idx = run_fn.find("_hitl_refuse")
    gate = allow_idx if allow_idx >= 0 else refuse_idx
    assert 0 <= gate < exec_idx
    assert "if hitl_stop" in run_fn
    send = routes.split("async def send_chat_message", 1)[1].split("async def get_chat_history", 1)[0]
    assert "HITL_STOP_ALLOWED_TOOLS" in send or "tool_allowlist" in send


def test_hitl_engine_refuses_write_tools_and_finishes_after_propose():
    """Even if extra tools are registered, HITL stop refuses them and FINISH after Propose."""
    from src.orchestrator.engine import ReActEngine
    from src.services.llm import LLMResponse
    from src.tools.base import BaseTool, ToolRegistry, ToolResult

    executed: list[str] = []

    def make_tool(n: str):
        class T(BaseTool):
            name = n
            description = n

            def execute(self, input_data):
                executed.append(n)
                data = {"ok": True, "dataset_key": input_data.get("dataset_key")}
                if "propose" in n:
                    data["proposals"] = [{"id": "r1"}]
                return ToolResult(status="success", output_data=data)

        return T()

    class ScriptedLLM:
        def __init__(self):
            self.n = 0

        def chat(self, messages, tools=None):
            self.n += 1
            seq = [
                ("profile_dataset", {}),
                ("propose_quality_rules", {}),
                ("algolia_search", {"query": "rules"}),
                ("list_datasets", {}),
                ("clean_database", {}),
            ]
            name, args = seq[min(self.n - 1, len(seq) - 1)]
            return LLMResponse(
                content=f"Thought: next\nAction: {name}\nAction Input: {{}}",
                tool_calls=[{"name": name, "arguments": args}],
                tokens_used=1,
            )

    reg = ToolRegistry()
    for n in ("profile_dataset", "propose_quality_rules", "clean_database", "algolia_search", "list_datasets"):
        reg.register(make_tool(n))

    import uuid
    sid = f"qa-hitl-stop-{uuid.uuid4().hex}"
    engine = ReActEngine(llm=ScriptedLLM(), tools=reg, max_steps=8, tool_allowlist=None)
    result = engine.run(
        "Profile this dataset and propose quality rules. Do not clean. Stop for HITL review.",
        context={"stop_at_hitl": True, "dataset_key": "vingroup_pilot", "session_id": sid},
        session_id=sid,
    )
    assert "clean_database" not in executed
    assert "algolia_search" not in executed
    assert "list_datasets" not in executed
    names = [s.action for s in result.steps]
    assert "clean_database" not in names
    assert "algolia_search" not in names
    assert "list_datasets" not in names
    assert "propose_quality_rules" in names
    assert result.status == "completed"


def test_hitl_chat_registers_only_profile_and_propose(monkeypatch):
    import src.api.routes as routes
    from fastapi.testclient import TestClient
    from src.main import app
    from types import SimpleNamespace

    registered: list[str] = []

    class RecReg:
        def __init__(self):
            self._tools = {}

        def register(self, tool):
            registered.append(getattr(tool, "name", type(tool).__name__))
            self._tools[registered[-1]] = tool

        def get_tool(self, name):
            return self._tools.get(name)

        def execute(self, name, inp):
            return SimpleNamespace(output_data={}, duration_ms=0)

        def list_tools(self):
            return []

        @property
        def tool_names(self):
            return list(self._tools)

    class FakeEngine:
        def __init__(self, **kwargs):
            self.tools = kwargs.get("tools")

        def run(self, task, context=None, **kwargs):
            return SimpleNamespace(steps=[], final_answer="Stopping for HITL review.", status="completed")

    monkeypatch.setattr(routes, "ToolRegistry", RecReg)
    monkeypatch.setattr(routes, "BoundedReActEngine", FakeEngine)
    client = TestClient(app, headers={"X-User-Role": "Admin"})
    resp = client.post(
        "/api/v1/chat/send",
        json={
            "message": "Profile this dataset and propose quality rules. Do not clean, quarantine, or execute. Stop for HITL review.",
            "session_id": "dataset:vingroup_pilot_hitl_allowlist",
            "dataset_key": "vingroup_pilot",
            "lang": "en",
        },
    )
    assert resp.status_code == 200
    assert "profile_dataset" in registered
    assert "propose_quality_rules" in registered
    assert "clean_database" not in registered
    assert "list_datasets" not in registered
    from src.orchestrator.engine import HITL_REFUSED_TOOLS, HITL_STOP_ALLOWED_TOOLS
    assert "algolia_search" in HITL_REFUSED_TOOLS
    assert "algolia_search" not in HITL_STOP_ALLOWED_TOOLS
    assert "vinfast_bms" not in resp.json()["response"]


def test_approved_header_uses_same_status_helper_as_cards():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    rules = (root / "frontend/src/components/workspace/QualityRulesTab.tsx").read_text()
    api = (root / "frontend/src/services/api.ts").read_text()
    hitl = (root / "src/api/hitl.py").read_text()

    helper = rules.split("function ruleCardStatus", 1)[1].split("export const QualityRulesTab", 1)[0]
    assert "approved" in helper
    assert "edited" in helper
    assert "return 'proposed'" in helper
    assert "const proposedCount" in rules
    assert "const approvedCount" in rules
    assert "ruleCardStatus(r) === 'approved'" in rules
    assert "keptApproved" in rules
    approve = rules.split("const handleApprove")[1].split("const handleConfirmReject")[0]
    assert "hitlApi.approve" in approve
    assert "fetchRules({ silent: true })" in approve
    assert "status: 'approved'" in approve
    assert "keptApproved" in rules
    assert "include_active" in hitl or "include_active" in api
    assert "approved" in hitl.split("if include_active", 1)[1].split("else:", 1)[0]

def test_hitl_stop_path_cannot_execute_clean_algolia_list():
    """Source-inspection: HITL-stop path cannot execute extra tools or log them as beats."""
    from pathlib import Path
    from src.orchestrator.engine import (
        HITL_STOP_ALLOWED_TOOLS,
        HITL_REFUSED_TOOLS,
        _allow_hitl_tool,
        is_hitl_blocked_tool,
        is_hitl_stop_prompt,
    )

    root = Path(__file__).resolve().parents[1]
    engine = (root / "src/orchestrator/engine.py").read_text()
    routes = (root / "src/api/routes/__init__.py").read_text()

    for allowed in ("profile_dataset", "propose_quality_rules", "quality_rule_proposer"):
        assert allowed in HITL_STOP_ALLOWED_TOOLS
        assert _allow_hitl_tool(allowed) is True
        assert is_hitl_blocked_tool(allowed) is False
    for banned in ("clean_database", "algolia_search", "list_datasets"):
        assert banned in HITL_REFUSED_TOOLS
        assert banned not in HITL_STOP_ALLOWED_TOOLS
        assert _allow_hitl_tool(banned) is False
        assert is_hitl_blocked_tool(banned) is True

    prompt = "Profile this dataset and propose quality rules. Do not clean, quarantine, or execute. Stop for HITL review."
    assert is_hitl_stop_prompt(prompt)
    assert is_hitl_stop_prompt(
        "Khảo sát dữ liệu và đề xuất luật chất lượng. Không làm sạch, không cách ly, không thực thi. Dừng lại để steward duyệt HITL."
    )

    run_fn = engine.split("def run(", 1)[1].split("def _parse_response", 1)[0]
    assert "HITL_STOP_ALLOWED_TOOLS" in engine
    assert "_allow_hitl_tool" in run_fn or "_hitl_refuse" in run_fn
    assert "self.tools.execute" in run_fn
    gate = run_fn.find("_allow_hitl_tool")
    if gate < 0:
        gate = run_fn.find("_hitl_refuse")
    assert 0 <= gate < run_fn.find("self.tools.execute")
    assert "_log_trace" in run_fn
    assert gate < run_fn.find("_log_trace")
    # refused path must continue/break without execute or _log_trace
    if "refused = self._refuse_reason" in run_fn:
        refuse_block = run_fn.split("refused = self._refuse_reason", 1)[1].split("if self._skip_duplicate_propose", 1)[0]
    elif "and not _allow_hitl_tool" in run_fn:
        refuse_block = run_fn.split("and not _allow_hitl_tool", 1)[1].split("if self._skip_duplicate_propose", 1)[0]
    else:
        refuse_block = run_fn.split("if self._hitl_refuse", 1)[1].split("if self._skip_duplicate_propose", 1)[0]
    assert "continue" in refuse_block
    assert "self.tools.execute" not in refuse_block
    assert "_log_trace" not in refuse_block

    send = routes.split("async def send_chat_message", 1)[1].split("async def get_chat_history", 1)[0]
    gated = send.split("if not hitl_stop:", 1)[1]
    assert "CleanDatabaseTool()" in gated
    assert "AlgoliaSearchTool()" in gated
    assert "ListDatasetsTool()" in gated
    assert "HITL_STOP_ALLOWED_TOOLS" in send
    assert "tool_allowlist" in send
    force = send.split("for tool_name in missing_requested_tools", 1)[1].split("step = ReActStep", 1)[0]
    assert "clean_database" in force or "_allow_hitl_tool" in force or "HITL_REFUSED_TOOLS" in force
    assert "continue" in force


def test_hitl_stop_refuses_extra_tools_before_profile_without_logging():
    """LLM extras first (algolia/list/clean) must not execute or become STEPS beats."""
    from src.orchestrator.engine import HITL_STOP_ALLOWED_TOOLS, ReActEngine
    from src.services.llm import LLMResponse
    from src.tools.base import BaseTool, ToolRegistry, ToolResult

    executed: list[str] = []
    logged: list[str] = []

    def make_tool(n: str):
        class T(BaseTool):
            name = n
            description = n

            def execute(self, input_data):
                executed.append(n)
                data = {"ok": True}
                if "propose" in n:
                    data["proposals"] = [{"id": "r1"}]
                if "profile" in n:
                    data["total_rows"] = 2
                return ToolResult(status="success", output_data=data)

        return T()

    class ScriptedLLM:
        def __init__(self):
            self.n = 0

        def chat(self, messages, tools=None):
            self.n += 1
            seq = [
                ("algolia_search", {"query": "rules"}),
                ("list_datasets", {}),
                ("clean_database", {}),
                ("profile_dataset", {}),
                ("propose_quality_rules", {}),
            ]
            name, args = seq[min(self.n - 1, len(seq) - 1)]
            return LLMResponse(
                content=f"Action: {name}",
                tool_calls=[{"name": name, "arguments": args}],
                tokens_used=1,
            )

    reg = ToolRegistry()
    for n in ("profile_dataset", "propose_quality_rules", "clean_database", "algolia_search", "list_datasets"):
        reg.register(make_tool(n))

    engine = ReActEngine(
        llm=ScriptedLLM(),
        tools=reg,
        max_steps=8,
        tool_allowlist=HITL_STOP_ALLOWED_TOOLS,
    )
    orig = engine._log_trace

    def wrap(session_id, step, status=None):
        logged.append(step.action)
        return orig(session_id, step, status)

    engine._log_trace = wrap
    import uuid
    sid = f"qa-hitl-allowlist-first-{uuid.uuid4().hex}"
    result = engine.run(
        "Profile this dataset and propose quality rules. Do not clean, quarantine, or execute. Stop for HITL review.",
        context={"dataset_key": "vingroup_pilot", "session_id": sid},
        session_id=sid,
    )
    assert executed == ["profile_dataset", "propose_quality_rules"], executed
    assert "clean_database" not in executed
    assert "algolia_search" not in executed
    assert "list_datasets" not in executed
    assert "clean_database" not in logged
    assert "algolia_search" not in logged
    assert "list_datasets" not in logged
    names = [s.action for s in result.steps]
    assert names == ["profile_dataset", "propose_quality_rules"], names
    assert result.status == "completed"




def test_propose_persists_namespaced_rows_queue_reads(monkeypatch):
    """propose_quality_rules must persist HITL rows queue(dataset_key) returns."""
    import uuid
    import pandas as pd
    from fastapi.testclient import TestClient
    from src.main import app
    from src.tools.chat_tools import ProposeQualityRulesTool, persist_hitl_proposals, namespace_rule_id
    from src.tools import chat_tools as chat_tools_mod

    key = f"qa_hitl_persist_{uuid.uuid4().hex[:10]}"
    tiny = pd.DataFrame(
        [
            {"soc_pct": 80.0, "battery_soc": 80.0},
            {"soc_pct": -2.0, "battery_soc": -2.0},
        ]
    )
    monkeypatch.setattr(chat_tools_mod, "load_dataset", lambda *a, **k: tiny)
    monkeypatch.setattr(chat_tools_mod, "_resolve_table_target", lambda k: ("", None, k))
    monkeypatch.setattr(chat_tools_mod, "_pipeline_tables", lambda *a, **k: ["ev_telemetry"])
    # Collision: bare R1_A1 already exists from another dataset.
    from src.db.connection import get_db
    db = get_db()
    try:
        db.execute(
            "INSERT INTO quality_rules (id, rule_name, rule_type, rule_expression, confidence, status, proposed_by) "
            "VALUES ('R1_A1', 'legacy', 'range', 'x > 0', 0.9, 'proposed', 'legacy')"
        )
    except Exception:
        pass
    result = ProposeQualityRulesTool().execute({"dataset_key": key})
    assert result.status == "success"
    proposals = result.output_data["proposals"]
    assert len(proposals) >= 1
    for p in proposals:
        assert p["id"].startswith(f"{key}__")
        assert p["status"] == "proposed"
    client = TestClient(app, headers={"X-User-Role": "Admin"})
    resp = client.get(f"/api/v1/hitl/queue?include_active=true&dataset_key={key}")
    assert resp.status_code == 200, resp.text
    ids = {p["rule_id"] for p in resp.json()["proposals"]}
    assert all(i.startswith(f"{key}__") for i in ids)
    assert len(ids) == len(proposals)
    assert namespace_rule_id(key, "R1_A1") in ids or any(i.endswith("R1_A1") for i in ids)
    written = persist_hitl_proposals(key, proposals)
    assert {w["id"] for w in written} == ids
