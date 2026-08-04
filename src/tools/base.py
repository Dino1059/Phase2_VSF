from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
import json
import uuid


@dataclass
class ToolCall:
    tool_name: str
    input_data: dict
    output_data: dict
    success: bool
    error: str | None = None
    duration_ms: int = 0
    call_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class BaseTool(ABC):
    name: str = ""
    description: str = ""
    input_schema: dict = {}
    output_schema: dict = {}

    @abstractmethod
    def execute(self, input_data: dict) -> dict:
        ...

    def safe_execute(self, input_data: dict) -> ToolCall:
        """Execute with error handling and timing."""
        import time
        start = time.time()
        try:
            result = self.execute(input_data)
            duration = int((time.time() - start) * 1000)
            return ToolCall(
                tool_name=self.name,
                input_data=input_data,
                output_data=result,
                success=True,
                duration_ms=duration
            )
        except Exception as e:
            duration = int((time.time() - start) * 1000)
            return ToolCall(
                tool_name=self.name,
                input_data=input_data,
                output_data={"error": str(e)},
                success=False,
                error=str(e),
                duration_ms=duration
            )

    def to_function_spec(self) -> dict:
        """OpenAI-compatible function calling spec."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema
            }
        }


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}. Available: {list(self._tools.keys())}")
        return self._tools[name]

    def list_tools(self) -> list[dict]:
        return [t.to_function_spec() for t in self._tools.values()]

    def execute(self, name: str, input_data: dict) -> ToolCall:
        tool = self.get(name)
        return tool.safe_execute(input_data)

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())
