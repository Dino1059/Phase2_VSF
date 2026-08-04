from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from typing import Any


class LLMUnavailableException(Exception):
    """Raised when the LLM service or provider is unavailable or fails."""
    pass


class StructuredOutputInvalidException(Exception):
    """Raised when structured JSON output from LLM fails validation or parsing."""
    pass


@dataclass
class LLMResponse:
    content: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    finish_reason: str = ""
    tokens_used: int = 0


class GemmaLLMAdapter:
    """Adapter for Google AI Studio (Gemini/Gemma models)."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.environ.get("GOOGLE_AI_API_KEY", "")
        self.model = model or os.environ.get("GOOGLE_AI_MODEL", "gemini-2.0-flash")
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except ImportError as e:
                raise LLMUnavailableException("google-genai not installed. Run: uv add google-genai") from e
            except Exception as e:
                raise LLMUnavailableException(f"Failed to init Gemini client: {e}") from e
        return self._client

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> LLMResponse:
        """Send chat messages to the model.
        messages: [{"role": "user"|"assistant"|"system", "content": "..."}]
        tools: OpenAI-style function specs
        """
        client = self._get_client()
        
        # Build contents for Gemini API
        contents = []
        system_instruction = None
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_instruction = content
            else:
                gemini_role = "model" if role == "assistant" else "user"
                contents.append({"role": gemini_role, "parts": [{"text": content}]})

        try:
            from google.genai import types
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.1,
                max_output_tokens=4096,
            )
            
            # Add tools if provided
            if tools:
                gemini_tools = self._convert_tools(tools)
                config.tools = gemini_tools

            response = client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            )

            # Parse response
            tool_calls = []
            content_text = ""
            
            if response.candidates and response.candidates[0].content:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'text') and part.text:
                        content_text += part.text
                    if hasattr(part, 'function_call') and part.function_call:
                        tool_calls.append({
                            "name": part.function_call.name,
                            "arguments": dict(part.function_call.args) if part.function_call.args else {}
                        })

            tokens = 0
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                tokens = getattr(response.usage_metadata, 'total_token_count', 0)

            return LLMResponse(
                content=content_text,
                tool_calls=tool_calls,
                finish_reason="tool_call" if tool_calls else "stop",
                tokens_used=tokens
            )
        except LLMUnavailableException:
            raise
        except Exception as e:
            raise LLMUnavailableException(f"LLM call failed: {e}") from e

    def structured_output(self, prompt: str, schema: dict) -> dict:
        """Get structured JSON output from the model."""
        messages = [
            {"role": "system", "content": f"Respond ONLY with valid JSON matching this schema: {json.dumps(schema)}"},
            {"role": "user", "content": prompt}
        ]
        response = self.chat(messages)
        if response.finish_reason == "error" or not response.content:
            raise StructuredOutputInvalidException("LLM returned empty or error response for structured output")
        
        content = response.content.strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try extracting JSON from markdown code block
            import re
            match = re.search(r'```(?:json)?\s*(.+?)\s*```', content, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1).strip())
                except json.JSONDecodeError as err:
                    raise StructuredOutputInvalidException(f"Failed to parse repaired JSON block: {err}") from err
            raise StructuredOutputInvalidException(f"Failed to parse JSON output from LLM: {content[:200]}")

    def _convert_tools(self, openai_tools: list[dict]) -> list:
        """Convert OpenAI-style tool specs to Gemini format."""
        from google.genai import types
        declarations = []
        for tool in openai_tools:
            func = tool.get("function", {})
            declarations.append(types.FunctionDeclaration(
                name=func.get("name", ""),
                description=func.get("description", ""),
                parameters=func.get("parameters", {})
            ))
        return [types.Tool(function_declarations=declarations)]

    def generate_agentic_tool_call(self, message: str, tools: list[dict] | None = None) -> dict:
        """Determines tool calls via LLM or keyword fallback."""
        msg_lower = message.lower()
        if "list" in msg_lower and ("dataset" in msg_lower or "db" in msg_lower or "database" in msg_lower or "how many" in msg_lower or "databases" in msg_lower or "dbs" in msg_lower):
            return {"type": "function_call", "name": "list_datasets", "args": {}}
        if "profile" in msg_lower or "scan" in msg_lower or "health" in msg_lower:
            return {"type": "function_call", "name": "profile_dataset", "args": {}}
        if "rule" in msg_lower or "propose" in msg_lower:
            return {"type": "function_call", "name": "propose_quality_rules", "args": {}}
        if "anomal" in msg_lower or "outlier" in msg_lower or "drift" in msg_lower:
            return {"type": "function_call", "name": "detect_anomalies", "args": {}}
        if "diagnos" in msg_lower or "root cause" in msg_lower:
            return {"type": "function_call", "name": "diagnose_issue", "args": {}}
        if "clean" in msg_lower or "apply rules" in msg_lower or "proceed" in msg_lower:
            return {"type": "function_call", "name": "clean_database", "args": {}}
        return {"type": "text", "content": message}

    def stream_text(self, prompt: str, system_prompt: str = ""):
        res = self.chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ])
        yield {"type": "chunk", "text": res.content}

    def generate_structured(self, prompt: str, response_model: Any = None, schema: Any = None, system_prompt: str = "") -> Any:
        target_cls = response_model
        if target_cls is not None and hasattr(target_cls, "model_json_schema"):
            schema_dict = target_cls.model_json_schema()
        elif isinstance(schema, dict):
            schema_dict = schema
        else:
            schema_dict = {}

        full_prompt = f"{system_prompt}\n{prompt}".strip() if system_prompt else prompt
        res_dict = self.structured_output(full_prompt, schema_dict)

        if target_cls and hasattr(target_cls, "model_validate"):
            try:
                return target_cls.model_validate(res_dict)
            except Exception as val_err:
                raise StructuredOutputInvalidException(f"Pydantic validation failed for {target_cls.__name__}: {val_err}") from val_err
        return res_dict


LLMService = GemmaLLMAdapter



