from __future__ import annotations
import json
import os
from dataclasses import dataclass, field


@dataclass
class LLMResponse:
    content: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    finish_reason: str = ""
    tokens_used: int = 0


class GemmaLLMAdapter:
    """Adapter for Google AI Studio (Gemini/Gemma models)."""

    def __init__(self, api_key: str | None = None, model: str = "gemma-4-27b-it"):
        self.api_key = api_key or os.environ.get("GOOGLE_AI_API_KEY", "")
        self.model = model
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except ImportError:
                raise RuntimeError("google-genai not installed. Run: uv add google-genai")
            except Exception as e:
                raise RuntimeError(f"Failed to init Gemini client: {e}")
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
        except Exception as e:
            return LLMResponse(content=f"[LLM_ERROR] {e}", finish_reason="error")

    def structured_output(self, prompt: str, schema: dict) -> dict:
        """Get structured JSON output from the model."""
        messages = [
            {"role": "system", "content": f"Respond ONLY with valid JSON matching this schema: {json.dumps(schema)}"},
            {"role": "user", "content": prompt}
        ]
        response = self.chat(messages)
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            # Try extracting JSON from markdown code block
            import re
            match = re.search(r'```(?:json)?\s*(.+?)\s*```', response.content, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            return {"error": "Failed to parse JSON", "raw": response.content}

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


LLMService = GemmaLLMAdapter

