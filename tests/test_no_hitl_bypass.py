from src.tools.base import ToolResult
from src.tools.chat_tools import CleanDatabaseTool, RunFullPipelineTool, approved_rules_for_clean


def test_approved_rules_for_clean_never_synthesizes(monkeypatch):
    class EmptyDB:
        def execute(self, *a, **k):
            return []

    assert approved_rules_for_clean(EmptyDB()) == []


def test_clean_database_tool_no_approved_rules_writes_nothing(monkeypatch):
    writes = []

    class EmptyDB:
        def execute(self, *a, **k):
            writes.append(("sql", a))
            return []

    monkeypatch.setattr("src.db.connection.get_db", lambda: EmptyDB())
    monkeypatch.setattr(
        "src.tools.chat_tools.approved_rules_for_clean",
        lambda *a, **k: [],
    )

    def _boom(*a, **k):
        raise AssertionError("must not synthesize or execute")

    monkeypatch.setattr("src.tools.chat_tools.generate_rules_for_baseline", _boom, raising=False)
    monkeypatch.setattr("src.tools.chat_tools.execute_compiled_rules", _boom, raising=False)

    res = CleanDatabaseTool().execute({"dataset_key": "ev_telemetry"})
    assert isinstance(res, ToolResult)
    assert res.status in ("error", "abstained")
    assert "approved" in (res.error_message or "").lower() or res.output_data.get("status") == "awaiting_hitl"
    assert not any("INSERT" in str(x).upper() for x in writes)


def test_run_full_pipeline_stops_before_clean(monkeypatch):
    called = {"clean": 0}

    class FakeTool:
        def __init__(self, payload):
            self.payload = payload

        def execute(self, *_a, **_k):
            return ToolResult(status="success", output_data=self.payload)

    monkeypatch.setattr("src.tools.chat_tools.ProfileDatasetTool", lambda: FakeTool({"profile": True}))
    monkeypatch.setattr("src.tools.chat_tools.DetectAnomaliesTool", lambda: FakeTool({"incidents": []}))
    monkeypatch.setattr("src.tools.chat_tools.ProposeQualityRulesTool", lambda: FakeTool({"proposals": [{"id": "r1"}]}))

    class BoomClean:
        def execute(self, *_a, **_k):
            called["clean"] += 1
            raise AssertionError("CleanDatabaseTool must not run on analysis path")

    monkeypatch.setattr("src.tools.chat_tools.CleanDatabaseTool", BoomClean)
    res = RunFullPipelineTool().execute({"dataset_key": "ev_telemetry"})
    assert called["clean"] == 0
    assert res.status == "success"
    assert res.output_data.get("status") == "awaiting_hitl"
    assert "clean_database" not in (res.output_data.get("steps_executed") or [])
