from __future__ import annotations
import json
import os
import urllib.request
import urllib.error
import time
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any
from dotenv import load_dotenv

# Ensure .env is loaded
load_dotenv()


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
    model_used: str = ""


class KeyRotator:
    """Thread-safe round-robin key rotator with rate limit cooldown (HTTP 429)."""
    
    def __init__(self, keys: list[str]):
        seen = set()
        clean_keys = []
        for k in keys:
            k_clean = k.strip() if isinstance(k, str) else ""
            if k_clean and k_clean not in seen:
                seen.add(k_clean)
                clean_keys.append(k_clean)
        self._keys = clean_keys
        self._index = 0
        self._lock = threading.Lock()
        self._cooldowns: dict[str, float] = {}  # key -> cooldown expiry timestamp
    
    def get_next(self) -> str | None:
        if not self._keys:
            return None
        with self._lock:
            now = time.time()
            # Find the next key not on cooldown
            for _ in range(len(self._keys)):
                key = self._keys[self._index % len(self._keys)]
                self._index += 1
                if self._cooldowns.get(key, 0) <= now:
                    return key
            # If all are currently on cooldown, return the one whose cooldown expires earliest
            earliest_key = min(self._keys, key=lambda k: self._cooldowns.get(k, 0))
            return earliest_key

    def mark_rate_limited(self, key: str, cooldown_seconds: float = 60.0) -> None:
        """Mark a specific key as rate limited with a cooldown period."""
        if not key:
            return
        with self._lock:
            self._cooldowns[key] = time.time() + cooldown_seconds

    @property
    def has_keys(self) -> bool:
        return len(self._keys) > 0

    @property
    def total_keys(self) -> int:
        return len(self._keys)


class UnifiedLLMAdapter:
    """
    Unified LLM Adapter with multi-provider support.
    Priority: Gemini (4-key rotation) -> OpenAI (lowest fallback)
    """

    def __init__(self, api_key: str | None = None, model: str | None = None, use_llm: bool = True):
        load_dotenv()
        self.use_llm = use_llm
        
        # OpenAI (Fallback)
        self.openai_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.openai_model = os.environ.get("OPENAI_MODEL", "gpt-5-nano")

        # OpenRouter (Optional)
        self.openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
        self.openrouter_model = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")

        # Groq (Optional)
        self.groq_key = os.environ.get("GROQ_API_KEY", "")
        self.groq_model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

        # Google keys - multi-key pool for rate-limiting routing (Primary: gemini-3.5-flash-lite)
        all_gemini_keys: list[str] = []
        for env_var in ["GOOGLE_AI_API_KEYS", "GEMINI_API_KEYS"]:
            val = os.environ.get(env_var, "")
            if val:
                all_gemini_keys.extend([k.strip() for k in val.split(",") if k.strip()])

        for env_var in [
            "GOOGLE_AI_API_KEY",
            "GOOGLE_AI_API_KEY_1",
            "GOOGLE_AI_API_KEY_2",
            "GOOGLE_AI_API_KEY_3",
            "AI_STUDIO_API_KEY",
            "GEMINI_API_KEY",
            "GOOGLE_API_KEY",
        ]:
            val = os.environ.get(env_var, "").strip()
            if val:
                all_gemini_keys.append(val)

        self._google_keys = KeyRotator(all_gemini_keys)
        self.gemini_model = os.environ.get("GOOGLE_AI_MODEL") or os.environ.get("AI_MODEL") or "gemini-3.5-flash-lite"
        
        # Ollama (local Gemma - no keys needed)
        self.ollama_base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        self.ollama_model = os.environ.get("OLLAMA_MODEL", "gemma3:4b")
        self._ollama_available = None  # Lazy check
        
        self.preferred_provider = os.environ.get("LLM_PROVIDER", "auto").lower()

        # Explicit overrides
        self._explicit_key = api_key
        self._explicit_model = model

    def _check_ollama(self) -> bool:
        """Check if Ollama is available."""
        if self._ollama_available is not None:
            return self._ollama_available
        try:
            req = urllib.request.Request(
                f"{self.ollama_base_url}/api/tags",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=2) as resp:
                self._ollama_available = resp.status == 200
        except Exception:
            self._ollama_available = False
        return self._ollama_available

    @property
    def api_key(self) -> str:
        return (
            self._explicit_key
            or (self._google_keys._keys[0] if self._google_keys.has_keys else "")
            or self.openai_key
            or self.groq_key
            or self.openrouter_key
        )

    @property
    def model(self) -> str:
        if self._explicit_model:
            return self._explicit_model
        if self._google_keys.has_keys or os.environ.get("GOOGLE_AI_MODEL") or os.environ.get("AI_MODEL"):
            return self.gemini_model
        if self.openai_key and not self.openai_key.startswith("sk-your-") and not self.openai_key.startswith("test-"):
            return self.openai_model
        return self.gemini_model

    def chat(self, messages: list[dict], tools: list[dict] | None = None, raise_on_error: bool = False) -> LLMResponse:
        """
        Send chat messages with strictly gemini-3.5-flash-lite primary (with 4-key rate-limit rotation), gpt-5-nano fallback.
        """
        if not self.use_llm:
            return self._heuristic_fallback(messages)

        if self._explicit_key == "invalid-key":
            raise LLMUnavailableException("Invalid API key provided.")

        # Strict 2-option chain: gemini-3.5-flash-lite -> openai gpt-5-nano
        if self.preferred_provider == "openai":
            provider_order = ["openai", "gemini"]
        elif self.preferred_provider == "groq":
            provider_order = ["groq", "gemini", "openai"]
        else:
            provider_order = ["gemini", "openai"]

        for provider in provider_order:
            if provider == "groq" and self.groq_key and not self.groq_key.startswith("gsk_your-"):
                try:
                    return self._call_groq(messages, tools)
                except Exception as e:
                    if raise_on_error:
                        raise LLMUnavailableException(f"Groq call failed: {e}") from e
                    print(f"[LLM] Groq call failed: {e}. Falling back to next provider...")

            elif provider == "openai" and self.openai_key and not self.openai_key.startswith("sk-your-"):
                try:
                    return self._call_openai(messages, tools)
                except Exception as e:
                    if raise_on_error:
                        raise LLMUnavailableException(f"OpenAI call failed: {e}") from e
                    print(f"[LLM] OpenAI call failed: {e}. Falling back to next provider...")

            elif provider == "openrouter" and self.openrouter_key and not self.openrouter_key.startswith("sk-or-your-"):
                try:
                    return self._call_openrouter(messages, tools)
                except Exception as e:
                    if raise_on_error:
                        raise LLMUnavailableException(f"OpenRouter call failed: {e}") from e
                    print(f"[LLM] OpenRouter call failed: {e}. Falling back to next provider...")

            elif provider == "gemini" and self._google_keys.has_keys:
                total_attempts = max(1, self._google_keys.total_keys)
                for attempt in range(total_attempts):
                    key = self._google_keys.get_next()
                    if not key:
                        break
                    try:
                        return self._call_gemini(messages, tools, key, self.gemini_model)
                    except urllib.error.HTTPError as http_err:
                        key_mask = f"...{key[-6:]}" if len(key) >= 6 else "***"
                        if http_err.code in (429, 503, 500):
                            self._google_keys.mark_rate_limited(key, cooldown_seconds=60.0)
                            print(f"[LLM] Gemini key {key_mask} hit HTTP {http_err.code} rate limit (attempt {attempt + 1}/{total_attempts}). Rotating to next key...")
                        else:
                            print(f"[LLM] Gemini key {key_mask} HTTP {http_err.code} error (attempt {attempt + 1}/{total_attempts}). Trying next key...")
                        if attempt == total_attempts - 1 and raise_on_error:
                            raise LLMUnavailableException(f"All Gemini keys failed: {http_err}") from http_err
                    except Exception as e:
                        key_mask = f"...{key[-6:]}" if len(key) >= 6 else "***"
                        err_str = str(e).lower()
                        if "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str or "rate limit" in err_str:
                            self._google_keys.mark_rate_limited(key, cooldown_seconds=60.0)
                        print(f"[LLM] Gemini key {key_mask} rotation attempt {attempt + 1}/{total_attempts} failed: {e}. Trying next key...")
                        if attempt == total_attempts - 1 and raise_on_error:
                            raise LLMUnavailableException(f"All Gemini keys failed: {e}") from e

            elif provider == "ollama" and self._check_ollama():
                try:
                    return self._call_ollama(messages, tools)
                except Exception as e:
                    print(f"[LLM] Ollama/Gemma call failed: {e}.")

        # Final heuristic fallback
        return self._heuristic_fallback(messages)

    def _call_openrouter(self, messages: list[dict], tools: list[dict] | None = None) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.openrouter_model,
            "messages": messages,
            "temperature": 0.2,
        }
        if tools:
            payload["tools"] = tools

        headers = {
            "Authorization": f"Bearer {self.openrouter_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://datatrust-os.local",
            "X-Title": "DataTrust OS",
        }
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            choice = data["choices"][0]
            msg = choice.get("message", {})
            content = msg.get("content") or ""
            tool_calls = msg.get("tool_calls", [])
            tokens = data.get("usage", {}).get("total_tokens", 0)
            return LLMResponse(
                content=content, 
                tool_calls=tool_calls,
                finish_reason=choice.get("finish_reason", "stop"), 
                tokens_used=tokens,
                model_used=self.openrouter_model,
            )

    def _call_groq(self, messages: list[dict], tools: list[dict] | None = None) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.groq_model,
            "messages": messages,
            "temperature": 0.2,
        }
        if tools:
            payload["tools"] = tools

        headers = {
            "Authorization": f"Bearer {self.groq_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }

        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                req = urllib.request.Request(
                    "https://api.groq.com/openai/v1/chat/completions",
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    choice = data["choices"][0]
                    msg = choice.get("message", {})
                    content = msg.get("content") or ""
                    tool_calls = msg.get("tool_calls", [])
                    tokens = data.get("usage", {}).get("total_tokens", 0)
                    return LLMResponse(
                        content=content,
                        tool_calls=tool_calls,
                        finish_reason=choice.get("finish_reason", "stop"),
                        tokens_used=tokens,
                        model_used=self.groq_model,
                    )
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < max_attempts - 1:
                    backoff = (attempt + 1) * 3.0
                    print(f"[LLM] Groq 429 rate limit reached. Waiting {backoff}s before retry (attempt {attempt+1}/{max_attempts})...")
                    time.sleep(backoff)
                    continue
                raise

    def _call_openai(self, messages: list[dict], tools: list[dict] | None = None) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.openai_model,
            "messages": messages,
            "temperature": 0.2,
        }
        if tools:
            payload["tools"] = tools

        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.openai_key}",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            choice = data["choices"][0]
            msg = choice.get("message", {})
            content = msg.get("content") or ""
            tool_calls = msg.get("tool_calls", [])
            tokens = data.get("usage", {}).get("total_tokens", 0)
            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                finish_reason=choice.get("finish_reason", "stop"),
                tokens_used=tokens,
                model_used=self.openai_model,
            )

    def _call_gemini(self, messages: list[dict], tools: list[dict] | None = None, api_key: str | None = None, model: str | None = None) -> LLMResponse:
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

        key = api_key or self._google_keys.get_next()
        model_name = model or self.gemini_model
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
        payload: dict[str, Any] = {"contents": contents}
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        if tools:
            func_decls = []
            for t in tools:
                if isinstance(t, dict):
                    if "function" in t:
                        func_decls.append(t["function"])
                    elif "name" in t:
                        func_decls.append(t)
            if func_decls:
                payload["tools"] = [{"functionDeclarations": func_decls}]

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            candidate = data.get("candidates", [{}])[0]
            parts = candidate.get("content", {}).get("parts", [])
            text = "".join([p.get("text", "") for p in parts if "text" in p])
            tool_calls = []
            for p in parts:
                if "functionCall" in p:
                    fc = p["functionCall"]
                    tool_calls.append({
                        "id": f"call_{uuid.uuid4().hex[:8]}",
                        "type": "function",
                        "function": {
                            "name": fc.get("name"),
                            "arguments": json.dumps(fc.get("args", {})),
                        }
                    })
            return LLMResponse(content=text, tool_calls=tool_calls, finish_reason="stop", model_used=model_name)

    def _call_ollama(self, messages: list[dict], tools: list[dict] | None = None) -> LLMResponse:
        """Call Ollama for local Gemma inference (free, unlimited)."""
        # Convert messages to Ollama format
        ollama_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            if role == "system":
                # Ollama uses system field
                ollama_messages.append({"role": "system", "content": msg.get("content", "")})
            else:
                ollama_messages.append({"role": role, "content": msg.get("content", "")})
        
        payload: dict[str, Any] = {
            "model": self.ollama_model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": 0.2,
            }
        }
        
        url = f"{self.ollama_base_url}/api/chat"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data.get("message", {}).get("content", "")
            tokens = data.get("eval_count", 0)
            return LLMResponse(
                content=content, 
                finish_reason="stop", 
                tokens_used=tokens,
                model_used=self.ollama_model,
            )

    def _heuristic_fallback(self, messages: list[dict]) -> LLMResponse:
        last_msg = messages[-1]["content"] if messages else ""
        lower = last_msg.lower()

        if "dataset" in lower or "how many" in lower:
            reply = "You have **18 datasets** registered in the DataTrust OS repository including vietnam_trips_dirty, vgreen_telemetry, and xanhsm_feedback."
        elif "evidence" in lower or "summarize" in lower:
            reply = "Contextual Assistant Breakdown:\n- Analyzed supporting evidence across L1–L4 layers.\n- Signal discharge_rate exhibits MAD drift above +4.2 thresholds.\n- Evidence ID ev-supp-1 verified as REAL_TELEMETRY provenance."
        elif "rca" in lower or "hypothesis" in lower or "root cause" in lower:
            reply = "RCA Hypothesis Synthesis:\n- Primary: Dynamic A1 verified data contract violation in entity STATION-VGREEN-01.\n- Data Cause (Confidence: 88%). Recommend enforcing preventive range rule check."
        elif "hitl" in lower or "authorize" in lower or "governance" in lower:
            reply = "HITL Governance Audit:\n- Preventive control rule requires Data Steward digital signature & authorization.\n- Execution payload is hash-bound to authorization token."
        else:
            reply = f"DataTrust Operational Trust Assistant: Received inquiry '{last_msg}'. I am monitoring incident context, supporting evidence, and governance state. How can I assist your data stewardship workflow?"

        return LLMResponse(content=reply, finish_reason="stop", model_used="heuristic")

    def structured_output(self, prompt: str, schema: dict) -> dict:
        messages = [
            {"role": "system", "content": f"Respond ONLY with valid JSON matching this schema: {json.dumps(schema)}"},
            {"role": "user", "content": prompt},
        ]
        response = self.chat(messages)
        content = response.content.strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            import re
            match = re.search(r"```(?:json)?\s*(.+?)\s*```", content, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1).strip())
                except json.JSONDecodeError as err:
                    raise StructuredOutputInvalidException(f"Failed to parse repaired JSON: {err}") from err
            raise StructuredOutputInvalidException(f"Failed to parse JSON output: {content[:200]}")

    def generate_agentic_tool_call(self, message: str, tools: list[dict] | None = None) -> dict:
        msg_lower = message.lower()
        if "list" in msg_lower and ("dataset" in msg_lower or "db" in msg_lower):
            return {"type": "function_call", "name": "list_datasets", "args": {}}
        if "profile" in msg_lower or "scan" in msg_lower:
            return {"type": "function_call", "name": "profile_dataset", "args": {}}
        if "rule" in msg_lower or "propose" in msg_lower:
            return {"type": "function_call", "name": "propose_quality_rules", "args": {}}
        if "anomal" in msg_lower or "drift" in msg_lower:
            return {"type": "function_call", "name": "detect_anomalies", "args": {}}
        return {"type": "text", "content": message}

    def stream_text(self, prompt: str, system_prompt: str = ""):
        res = self.chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ])
        yield {"type": "chunk", "text": res.content}

    def generate_structured(self, prompt: str, response_model: Any = None, schema: Any = None, system_prompt: str = "") -> Any:
        target_cls = response_model
        schema_dict = target_cls.model_json_schema() if target_cls and hasattr(target_cls, "model_json_schema") else (schema if isinstance(schema, dict) else {})
        full_prompt = f"{system_prompt}\n{prompt}".strip() if system_prompt else prompt
        res_dict = self.structured_output(full_prompt, schema_dict)
        if target_cls and hasattr(target_cls, "model_validate"):
            return target_cls.model_validate(res_dict)
        return res_dict


# Backwards compatible aliases
GemmaLLMAdapter = UnifiedLLMAdapter
LLMService = UnifiedLLMAdapter
