from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
import json
from typing import Any, Literal, Optional, Type
import uuid
from pydantic import BaseModel, Field, ValidationError, create_model


class ToolResult(BaseModel):
    status: Literal["success", "error", "abstained"]
    output_data: dict = Field(default_factory=dict)
    error_message: Optional[str] = None
    evidence_artifact_id: Optional[str] = None


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
    result: ToolResult | None = None


class BaseTool(ABC):
    name: str = ""
    description: str = ""
    input_schema: dict | Type[BaseModel] = {}
    output_schema: dict | Type[BaseModel] = {}
    target_workflow_state: Optional[Any] = None

    def steward_meta(self) -> dict[str, str]:
        """Human card from the real tool name + .description (never invented)."""
        title = (self.name or "").replace("_", " ").strip().capitalize()
        return {
            "tool_name": self.name,
            "tool_title": title,
            "tool_about": (self.description or "").strip(),
        }

    @abstractmethod
    def execute(self, input_data: dict) -> dict | ToolResult | BaseModel:
        ...

    def validate_input(self, input_data: dict) -> dict:
        """Validate input arguments against input_schema using Pydantic validation."""
        schema = self.input_schema
        if not schema:
            return input_data
        if isinstance(schema, type) and issubclass(schema, BaseModel):
            validated = schema.model_validate(input_data)
            return validated.model_dump()
        if isinstance(schema, dict):
            required = schema.get("required", [])
            for r in required:
                if r not in input_data:
                    raise ValueError(f"Missing required input argument: '{r}'")
            props = schema.get("properties", {})
            if props:
                type_mapping = {
                    "string": str,
                    "integer": int,
                    "number": float,
                    "boolean": bool,
                    "array": list,
                    "object": dict,
                }
                fields = {}
                for fname, fdef in props.items():
                    ftype_str = fdef.get("type") if isinstance(fdef, dict) else None
                    py_type = type_mapping.get(ftype_str, Any)
                    if fname in required:
                        fields[fname] = (py_type, ...)
                    else:
                        fields[fname] = (Optional[py_type], None)
                Model = create_model(f"{self.name.capitalize()}InputModel", **fields)
                Model.model_validate(input_data)
        return input_data

    def validate_output(self, output_data: dict) -> dict:
        """Validate output data against output_schema using Pydantic validation."""
        schema = self.output_schema
        if not schema:
            return output_data
        if isinstance(schema, type) and issubclass(schema, BaseModel):
            validated = schema.model_validate(output_data)
            return validated.model_dump()
        if isinstance(schema, dict):
            required = schema.get("required", [])
            for r in required:
                if r not in output_data:
                    raise ValueError(f"Missing required output field: '{r}'")
            props = schema.get("properties", {})
            if props:
                type_mapping = {
                    "string": str,
                    "integer": int,
                    "number": float,
                    "boolean": bool,
                    "array": list,
                    "object": dict,
                }
                fields = {}
                for fname, fdef in props.items():
                    ftype_str = fdef.get("type") if isinstance(fdef, dict) else None
                    py_type = type_mapping.get(ftype_str, Any)
                    if fname in required:
                        fields[fname] = (py_type, ...)
                    else:
                        fields[fname] = (Optional[py_type], None)
                Model = create_model(f"{self.name.capitalize()}OutputModel", **fields)
                Model.model_validate(output_data)
        return output_data

    def safe_execute(self, input_data: dict) -> ToolCall:
        """Execute with error handling, Pydantic schema validation, and timing."""
        import time
        start = time.time()
        try:
            validated_input = self.validate_input(input_data)
            raw_result = self.execute(validated_input)

            if isinstance(raw_result, ToolResult):
                tool_result = raw_result
            elif isinstance(raw_result, BaseModel):
                tool_result = ToolResult(
                    status="success",
                    output_data=raw_result.model_dump()
                )
            elif isinstance(raw_result, dict):
                if "error" in raw_result and len(raw_result) == 1:
                    tool_result = ToolResult(
                        status="error",
                        error_message=str(raw_result["error"]),
                        output_data=raw_result
                    )
                else:
                    self.validate_output(raw_result)
                    tool_result = ToolResult(
                        status="success",
                        output_data=raw_result
                    )
            else:
                tool_result = ToolResult(
                    status="success",
                    output_data={"result": raw_result}
                )

            duration = int((time.time() - start) * 1000)
            is_success = (tool_result.status == "success")
            return ToolCall(
                tool_name=self.name,
                input_data=input_data,
                output_data=tool_result.output_data,
                success=is_success,
                error=tool_result.error_message,
                duration_ms=duration,
                result=tool_result
            )
        except Exception as e:
            duration = int((time.time() - start) * 1000)
            err_msg = str(e)
            tool_result = ToolResult(
                status="error",
                error_message=err_msg,
                output_data={"error": err_msg}
            )
            return ToolCall(
                tool_name=self.name,
                input_data=input_data,
                output_data=tool_result.output_data,
                success=False,
                error=err_msg,
                duration_ms=duration,
                result=tool_result
            )

    def to_function_spec(self) -> dict:
        """OpenAI-compatible function calling spec."""
        if isinstance(self.input_schema, type) and issubclass(self.input_schema, BaseModel):
            params = self.input_schema.model_json_schema()
        else:
            params = self.input_schema
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": params
            }
        }


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool name collision: tool '{tool.name}' is already registered.")
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}. Available: {list(self._tools.keys())}")
        return self._tools[name]

    def get_tool(self, name: str) -> BaseTool:
        return self.get(name)

    def list_tools(self) -> list[dict]:
        return [t.to_function_spec() for t in self._tools.values()]

    def execute(self, name: str, input_data: dict) -> ToolCall:
        tool = self.get(name)
        return tool.safe_execute(input_data)

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())
