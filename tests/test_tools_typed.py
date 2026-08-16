import pytest
from pydantic import BaseModel, Field
from typing import Optional
from src.tools.base import BaseTool, ToolRegistry, ToolResult, ToolCall


class DummyInput(BaseModel):
    query: str
    limit: int = Field(default=10, ge=1)


class DummyOutput(BaseModel):
    matches: list[str]
    total: int


class DummyTypedTool(BaseTool):
    name = "dummy_typed_tool"
    description = "A typed dummy tool for testing Pydantic schemas."
    input_schema = DummyInput
    output_schema = DummyOutput

    def execute(self, input_data: dict) -> dict:
        q = input_data["query"]
        lim = input_data.get("limit", 10)
        return {"matches": [f"match_{i}_{q}" for i in range(lim)], "total": lim}


class DummyAbstainingTool(BaseTool):
    name = "dummy_abstain_tool"
    description = "Tool that returns explicit ToolResult abstained."
    input_schema = {}
    output_schema = {}

    def execute(self, input_data: dict) -> ToolResult:
        return ToolResult(
            status="abstained",
            output_data={},
            error_message="Insufficient confidence to proceed",
            evidence_artifact_id="art_123"
        )


def test_tool_result_typing():
    res_success = ToolResult(status="success", output_data={"data": 123})
    assert res_success.status == "success"
    assert res_success.output_data == {"data": 123}
    assert res_success.error_message is None
    assert res_success.evidence_artifact_id is None

    res_error = ToolResult(status="error", error_message="Failed", evidence_artifact_id="art_001")
    assert res_error.status == "error"
    assert res_error.output_data == {}
    assert res_error.error_message == "Failed"
    assert res_error.evidence_artifact_id == "art_001"

    res_abstained = ToolResult(status="abstained", error_message="Abstained reason")
    assert res_abstained.status == "abstained"


def test_registry_collision_rejection():
    registry = ToolRegistry()
    t1 = DummyTypedTool()
    t2 = DummyTypedTool()
    registry.register(t1)

    with pytest.raises(ValueError, match="collision"):
        registry.register(t2)


def test_registry_get_tool():
    registry = ToolRegistry()
    t1 = DummyTypedTool()
    registry.register(t1)

    retrieved = registry.get_tool("dummy_typed_tool")
    assert retrieved is t1


def test_safe_execute_input_validation_failure():
    tool = DummyTypedTool()
    # Missing required 'query' field
    result = tool.safe_execute({})
    assert result.success is False
    assert result.error is not None
    assert "query" in result.error
    assert result.result is not None
    assert result.result.status == "error"
    assert result.result.error_message is not None


def test_safe_execute_input_validation_type_error():
    tool = DummyTypedTool()
    # 'limit' violates ge=1 constraint
    result = tool.safe_execute({"query": "test", "limit": -5})
    assert result.success is False
    assert result.error is not None
    assert result.result.status == "error"


def test_safe_execute_success():
    tool = DummyTypedTool()
    result = tool.safe_execute({"query": "hello", "limit": 2})
    assert result.success is True
    assert result.result is not None
    assert result.result.status == "success"
    assert result.output_data["total"] == 2
    assert len(result.output_data["matches"]) == 2


def test_safe_execute_tool_returns_tool_result():
    tool = DummyAbstainingTool()
    result = tool.safe_execute({})
    assert result.result is not None
    assert result.result.status == "abstained"
    assert result.result.evidence_artifact_id == "art_123"
    assert result.error == "Insufficient confidence to proceed"
