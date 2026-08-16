import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.services.llm import GemmaLLMAdapter, LLMResponse
from src.tools.base import BaseTool, ToolRegistry


class DummyTool(BaseTool):
    name = "test_tool"
    description = "A dummy test tool"

    def execute(self, input_data: dict) -> dict:
        return {"result": "ok"}


def test_import_orchestrator_engine():
    """Test that importing orchestrator engine works cleanly."""
    from src.orchestrator.engine import DecisionRecord, ReActEngine, ReActResult, ReActStep

    assert ReActEngine is not None
    assert ReActStep is not None
    assert ReActResult is not None
    assert DecisionRecord is not None


def test_react_engine_executes_steps_and_respects_max_steps():
    """Test that ReActEngine executes steps and respects max_steps limit (<= 10)."""
    from src.orchestrator.engine import ReActEngine

    mock_llm = MagicMock(spec=GemmaLLMAdapter)
    mock_llm.chat.return_value = LLMResponse(
        content="Thought: thinking\nAction: test_tool\nAction Input: {}",
        finish_reason="stop",
        tokens_used=10,
    )

    tools = ToolRegistry()
    tools.register(DummyTool())

    # Test with max_steps = 3
    engine = ReActEngine(llm=mock_llm, tools=tools, max_steps=3)
    assert engine.max_steps == 3

    result = engine.run("test task requiring max steps")
    assert result.status == "max_steps"
    assert len(result.steps) == 3
    assert len(result.decision_records) == 3

    # Test max_steps clamping to <= 10 if exceeded
    engine_clamped = ReActEngine(llm=mock_llm, tools=tools, max_steps=15)
    assert engine_clamped.max_steps == 10


def test_canonical_orchestrator_location():
    """Assert that src/orchestrator/engine.py is the canonical orchestrator."""
    from src.orchestrator.engine import ReActEngine as CanonicalEngine
    from src.orchestrator.react_engine import ReActEngine as OrchestratorReactEngine
    from src.agents.react import ReActEngine as AgentsReactEngine
    from src.agents.react_engine import ReActEngine as AgentsReactEngineModule

    # Assert engine.py exists in source tree
    engine_path = Path(__file__).parent.parent / "src" / "orchestrator" / "engine.py"
    assert engine_path.exists(), "src/orchestrator/engine.py must exist"

    # Assert re-exports resolve to the canonical engine
    assert OrchestratorReactEngine is CanonicalEngine
    assert AgentsReactEngine is CanonicalEngine
    assert AgentsReactEngineModule is CanonicalEngine
