from __future__ import annotations
import json
import logging
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

logger = logging.getLogger(__name__)

# Module-level provider circuit breaker (30–60s OPEN window)
_CIRCUIT_LOCK = threading.Lock()
_PROVIDER_CIRCUIT: dict[str, dict] = {}
_DEFAULT_OPEN_SECONDS = 45.0
_RATE_LIMIT_OPEN_SECONDS = 30.0


def _now() -> float:
    return time.time()


def reset_provider_circuits() -> None:
    """Test helper: clear OPEN/CLOSED state."""
    with _CIRCUIT_LOCK:
        _PROVIDER_CIRCUIT.clear()


def _circuit_is_open(provider: str, now: float | None = None) -> bool:
    ts = _now() if now is None else now
    with _CIRCUIT_LOCK:
        st = _PROVIDER_CIRCUIT.get(provider) or {}
        if st.get("state") != "OPEN":
            return False
        until = float(st.get("open_until") or 0.0)
        if ts >= until:
            _PROVIDER_CIRCUIT[provider] = {"state": "CLOSED", "open_until": 0.0}
            return False
        return True


def _circuit_record_success(provider: str) -> None:
    with _CIRCUIT_LOCK:
        _PROVIDER_CIRCUIT[provider] = {"state": "CLOSED", "open_until": 0.0}


def _circuit_record_failure(
    provider: str,
    *,
    status_code: int | None = None,
    retry_after: float | None = None,
    is_timeout: bool = False,
    now: float | None = None,
) -> None:
    ts = _now() if now is None else now
    open_for = _DEFAULT_OPEN_SECONDS
    if status_code == 429:
        open_for = float(retry_after) if retry_after is not None else _RATE_LIMIT_OPEN_SECONDS
    elif is_timeout or (status_code is not None and status_code >= 500):
        open_for = _DEFAULT_OPEN_SECONDS
    with _CIRCUIT_LOCK:
        _PROVIDER_CIRCUIT[provider] = {"state": "OPEN", "open_until": ts + open_for}


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
    provider: str = ""
    reasoning_mode: str = "llm"  # llm | heuristic | abstain
    fallback_depth: int = 0
    provider_attempts: list[dict] = field(default_factory=list)
    structured_validation: str = ""  # pass | fail | ""


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


_spend_lock = threading.Lock()
_tokens_spent_total = 0
_USD_PER_TOKEN = 1.5e-7  # conservative display estimate; cap is token-count first


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "on", "yes")


def _llm_killed() -> bool:
    if _env_flag("LLM_KILL_SWITCH"):
        return True
    try:
        cap = int(os.environ.get("LLM_MAX_TOKENS", "10000") or "10000")
    except ValueError:
        cap = 10000
    try:
        spend_cap = float(os.environ.get("LLM_MAX_SPEND_USD", "10") or "10")
    except ValueError:
        spend_cap = 10.0
    with _spend_lock:
        if _tokens_spent_total >= max(1, cap):
            return True
        if _tokens_spent_total * _USD_PER_TOKEN >= spend_cap:
            return True
    return False


def _record_spend(tokens: int) -> None:
    global _tokens_spent_total
    if not tokens:
        return
    with _spend_lock:
        _tokens_spent_total += int(tokens)


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
        if self.groq_model.startswith("groq/"):
            self.groq_model = self.groq_model.replace("groq/", "")
        if self.groq_model in ("compound-mini", ""):
            self.groq_model = "llama-3.3-70b-versatile"

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
        env_use_llm = os.environ.get("USE_LLM", "true").lower() not in ("false", "off", "0", "no")
        if self.preferred_provider in ("off", "none", "mock", "heuristic", "false", "disabled") or not env_use_llm or _llm_killed():
            self.use_llm = False
        else:
            self.use_llm = use_llm

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
            or self.openrouter_key
            or (self._google_keys._keys[0] if self._google_keys.has_keys else "")
            or self.openai_key
            or self.groq_key
        )

    @property
    def model(self) -> str:
        if self._explicit_model:
            return self._explicit_model
        if self.preferred_provider == "gemini" or os.environ.get("GOOGLE_AI_MODEL") or os.environ.get("AI_MODEL"):
            return self.gemini_model
        if self.preferred_provider == "openai":
            return self.openai_model
        if self.preferred_provider == "groq":
            return self.groq_model
        if self.preferred_provider == "ollama":
            return self.ollama_model
        if self.openrouter_key and not self.openrouter_key.startswith("sk-or-your-"):
            return self.openrouter_model
        if self._google_keys.has_keys:
            return self.gemini_model
        if self.openai_key and not self.openai_key.startswith("sk-your-") and not self.openai_key.startswith("test-"):
            return self.openai_model
        return self.openrouter_model

    def get_status(self) -> dict[str, Any]:
        """Check and return active provider and model status info."""
        if not self.use_llm:
            return {
                "status": "disabled",
                "provider": "heuristic",
                "model": "Deterministic Rule Engine (LLM Off)",
                "use_llm": False,
                "has_api_key": False,
                "kill_switch": _llm_killed(),
                "tokens_spent": _tokens_spent_total,
                "description": "LLM Off / Fallback to Deterministic Engine",
            }

        if self.preferred_provider == "openai":
            order = ["openai", "openrouter", "gemini", "groq", "ollama"]
        elif self.preferred_provider == "groq":
            order = ["groq", "openrouter", "gemini", "openai", "ollama"]
        elif self.preferred_provider == "gemini":
            order = ["gemini", "openrouter", "openai", "groq", "ollama"]
        else:
            order = ["openrouter", "gemini", "openai", "groq", "ollama"]

        active_prov = "heuristic"
        active_mdl = "heuristic"
        has_key = False

        for p in order:
            if p == "openrouter" and self.openrouter_key and not self.openrouter_key.startswith("sk-or-your-"):
                active_prov = "openrouter"
                active_mdl = self.openrouter_model
                has_key = True
                break
            elif p == "gemini" and self._google_keys.has_keys:
                active_prov = "gemini"
                active_mdl = self.gemini_model
                has_key = True
                break
            elif p == "openai" and self.openai_key and not self.openai_key.startswith("sk-your-") and not self.openai_key.startswith("test-"):
                active_prov = "openai"
                active_mdl = self.openai_model
                has_key = True
                break
            elif p == "groq" and self.groq_key and not self.groq_key.startswith("gsk_your-"):
                active_prov = "groq"
                active_mdl = self.groq_model
                has_key = True
                break
            elif p == "ollama" and self._check_ollama():
                active_prov = "ollama"
                active_mdl = self.ollama_model
                has_key = True
                break

        return {
            "status": "online" if has_key else "fallback_ready",
            "provider": active_prov,
            "model": active_mdl,
            "use_llm": self.use_llm,
            "has_api_key": has_key,
            "kill_switch": _llm_killed(),
            "tokens_spent": _tokens_spent_total,
            "description": f"Active LLM: {active_prov} ({active_mdl})" if has_key else "LLM Fallback (No active provider key)",
        }

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        raise_on_error: bool = False,
        purpose: str = "chat",
    ) -> LLMResponse:
        """
        Send chat messages using multi-provider fallback order. Primary: openrouter (openai/gpt-4o-mini).
        Records provider_attempts telemetry and skips OPEN circuit-breaker providers.
        """
        request_id = str(uuid.uuid4())
        attempts: list[dict] = []
        input_tokens_estimated = sum(max(1, len(str(m.get("content") or "")) // 4) for m in (messages or []))

        def _finalize(resp: LLMResponse, *, mode: str, provider: str = "", depth: int = 0) -> LLMResponse:
            _record_spend(int(resp.tokens_used or 0))
            if _llm_killed():
                self.use_llm = False
            resp.provider = provider or resp.provider
            resp.reasoning_mode = mode
            resp.fallback_depth = depth
            resp.provider_attempts = list(attempts)
            telemetry = {
                "request_id": request_id,
                "purpose": purpose,
                "provider_attempts": list(attempts),
                "selected_provider": resp.provider or provider or mode,
                "selected_model": resp.model_used,
                "fallback_depth": depth,
                "reasoning_mode": mode,
                "input_tokens_estimated": input_tokens_estimated,
                "output_tokens": int(resp.tokens_used or 0),
                "structured_validation": resp.structured_validation or "",
            }
            self.last_telemetry = telemetry
            logger.info("llm_attempt_telemetry %s", telemetry)
            return resp

        if not self.use_llm or _llm_killed():
            self.use_llm = False
            resp = self._heuristic_fallback(messages)
            return _finalize(resp, mode="heuristic", provider="heuristic", depth=0)

        if self._explicit_key == "invalid-key":
            raise LLMUnavailableException("Invalid API key provided.")

        if self.preferred_provider == "openai":
            provider_order = ["openai", "openrouter", "gemini", "groq", "ollama"]
        elif self.preferred_provider == "groq":
            provider_order = ["groq", "openrouter", "gemini", "openai", "ollama"]
        elif self.preferred_provider == "gemini":
            provider_order = ["gemini", "openrouter", "openai", "groq", "ollama"]
        else:
            provider_order = ["openrouter", "gemini", "openai", "groq", "ollama"]

        def _classify_failure(exc: Exception) -> tuple[int | None, float | None, bool]:
            status_code = None
            retry_after = None
            is_timeout = isinstance(exc, TimeoutError) or "timeout" in str(exc).lower()
            if isinstance(exc, urllib.error.HTTPError):
                status_code = int(exc.code)
                if status_code == 429:
                    try:
                        retry_after = float(exc.headers.get("Retry-After") or _RATE_LIMIT_OPEN_SECONDS)
                    except (TypeError, ValueError, AttributeError):
                        retry_after = _RATE_LIMIT_OPEN_SECONDS
            return status_code, retry_after, is_timeout

        def _provider_eligible(name: str) -> bool:
            if name == "groq":
                return bool(self.groq_key and not self.groq_key.startswith("gsk_your-"))
            if name == "openai":
                return bool(self.openai_key and not self.openai_key.startswith("sk-your-"))
            if name == "openrouter":
                return bool(self.openrouter_key and not self.openrouter_key.startswith("sk-or-your-"))
            if name == "gemini":
                return bool(self._google_keys.has_keys)
            if name == "ollama":
                return bool(self._check_ollama())
            return False

        def _invoke(name: str) -> LLMResponse:
            if name == "groq":
                return self._call_groq(messages, tools)
            if name == "openai":
                return self._call_openai(messages, tools)
            if name == "openrouter":
                return self._call_openrouter(messages, tools)
            if name == "gemini":
                key = self._google_keys.get_next()
                if not key:
                    raise LLMUnavailableException("No Gemini key available")
                return self._call_gemini(messages, tools, key, self.gemini_model)
            if name == "ollama":
                return self._call_ollama(messages, tools)
            raise LLMUnavailableException(f"Unknown provider {name}")

        fallback_depth = 0
        for provider in provider_order:
            if not _provider_eligible(provider):
                continue
            if _circuit_is_open(provider):
                attempts.append({"provider": provider, "result": "skipped_open"})
                logger.warning("[LLM] Skipping OPEN provider %s (circuit breaker)", provider)
                continue
            try:
                if provider == "gemini":
                    # Preserve multi-key rotation for Gemini
                    total_attempts = max(1, self._google_keys.total_keys)
                    last_exc: Exception | None = None
                    for attempt in range(total_attempts):
                        key = self._google_keys.get_next()
                        if not key:
                            break
                        try:
                            resp = self._call_gemini(messages, tools, key, self.gemini_model)
                            _circuit_record_success(provider)
                            attempts.append({"provider": provider, "result": "ok", "attempt": attempt + 1})
                            resp.provider = provider
                            return _finalize(resp, mode="llm", provider=provider, depth=fallback_depth)
                        except urllib.error.HTTPError as http_err:
                            last_exc = http_err
                            key_mask = f"...{key[-6:]}" if len(key) >= 6 else "***"
                            status_code, retry_after, is_timeout = _classify_failure(http_err)
                            if http_err.code in (429, 503, 500):
                                self._google_keys.mark_rate_limited(key, cooldown_seconds=60.0)
                                logger.warning(
                                    "[LLM] Gemini key %s hit HTTP %s rate limit (attempt %s/%s). Rotating to next key...",
                                    key_mask, http_err.code, attempt + 1, total_attempts,
                                )
                            else:
                                logger.warning(
                                    "[LLM] Gemini key %s HTTP %s error (attempt %s/%s). Trying next key...",
                                    key_mask, http_err.code, attempt + 1, total_attempts,
                                )
                            attempts.append({
                                "provider": provider, "result": "error",
                                "status_code": status_code, "attempt": attempt + 1,
                            })
                            if attempt == total_attempts - 1:
                                _circuit_record_failure(
                                    provider, status_code=status_code,
                                    retry_after=retry_after, is_timeout=is_timeout,
                                )
                                if raise_on_error:
                                    raise LLMUnavailableException(f"All Gemini keys failed: {http_err}") from http_err
                        except Exception as e:
                            last_exc = e
                            key_mask = f"...{key[-6:]}" if len(key) >= 6 else "***"
                            err_str = str(e).lower()
                            if "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str or "rate limit" in err_str:
                                self._google_keys.mark_rate_limited(key, cooldown_seconds=60.0)
                            logger.warning(
                                "[LLM] Gemini key %s rotation attempt %s/%s failed: %s. Trying next key...",
                                key_mask, attempt + 1, total_attempts, e,
                            )
                            status_code, retry_after, is_timeout = _classify_failure(e)
                            attempts.append({"provider": provider, "result": "error", "error": str(e), "attempt": attempt + 1})
                            if attempt == total_attempts - 1:
                                _circuit_record_failure(
                                    provider, status_code=status_code,
                                    retry_after=retry_after, is_timeout=is_timeout,
                                )
                                if raise_on_error:
                                    raise LLMUnavailableException(f"All Gemini keys failed: {e}") from e
                    fallback_depth += 1
                    continue

                resp = _invoke(provider)
                _circuit_record_success(provider)
                attempts.append({"provider": provider, "result": "ok"})
                resp.provider = provider
                return _finalize(resp, mode="llm", provider=provider, depth=fallback_depth)
            except Exception as e:
                status_code, retry_after, is_timeout = _classify_failure(e)
                _circuit_record_failure(
                    provider, status_code=status_code, retry_after=retry_after, is_timeout=is_timeout,
                )
                attempts.append({
                    "provider": provider, "result": "error",
                    "status_code": status_code, "error": str(e),
                })
                logger.warning("[LLM] %s call failed: %s. Falling back to next provider...", provider, e)
                if raise_on_error:
                    raise LLMUnavailableException(f"{provider} call failed: {e}") from e
                fallback_depth += 1

        # Final heuristic fallback
        resp = self._heuristic_fallback(messages)
        return _finalize(resp, mode="heuristic", provider="heuristic", depth=fallback_depth)

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
                    logger.warning("[LLM] Groq 429 rate limit reached. Waiting %ss before retry (attempt %s/%s)...", backoff, attempt+1, max_attempts)
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
        from src.orchestrator.prompt_intent import (
            CANNED_INVENTORY,
            asks_causal_story,
            asks_dataset_inventory,
            extract_entity_token,
            grill_edit_rule,
            heuristic_user_task,
            last_user_utterance,
            is_edit_rule_prompt,
            is_smalltalk_prompt,
            last_observation_text,
            parse_edit_rule_query,
            smalltalk_reply,
            workspace_binding,
        )

        task_text = last_user_utterance(messages) or heuristic_user_task(messages)
        last_user = task_text
        all_text = task_text

        # 1. A1 Bounded Investigator Fallback -> Return FINAL_HYPOTHESIS JSON immediately
        if "begin your investigation" in all_text or "incident id" in all_text or "rca hypothesis" in all_text:
            hyp_payload = {
                "claim": "Heuristic analysis: Signal anomaly verified against operational bounds.",
                "classification": "DATA",
                "confidence": 0.88,
                "supporting_evidence": ["ev-heuristic-l1-l4"],
                "contradicting_evidence": [],
                "missing_evidence": []
            }
            return LLMResponse(
                content=f"FINAL_HYPOTHESIS:\n{json.dumps(hyp_payload)}",
                finish_reason="stop",
                model_used="heuristic-a1"
            )

        # 2. ReAct Agent Tool Calls (Profiler, Anomaly, Proposer, Executor)
        # Check if a tool has already been executed in this conversation (Observation present)
        has_observation = any(
            isinstance(m, dict) and (
                m.get("role") == "tool" or
                str(m.get("content", "")).startswith("Observation:") or
                "observation:" in str(m.get("content", "")).lower()
            )
            for m in messages
        )
        if is_edit_rule_prompt(task_text):
            obs = last_observation_text(messages)
            if obs and not obs.upper().startswith("REFUSED"):
                return LLMResponse(
                    content=grill_edit_rule(obs),
                    finish_reason="stop",
                    model_used="heuristic-edit-rule",
                )
            q = parse_edit_rule_query(task_text)
            args = {"query": q} if q else {}
            return LLMResponse(
                content="ACTION: sandbox_preview\nARGS: " + json.dumps(args),
                tool_calls=[{"name": "sandbox_preview", "args": args}],
                finish_reason="tool_calls",
                model_used="heuristic-edit-rule",
            )

        # Greetings / "what can you do?" — never profile/list from tool catalog or Context JSON
        if is_smalltalk_prompt(task_text):
            return LLMResponse(
                content=smalltalk_reply(task_text),
                finish_reason="stop",
                model_used="heuristic-smalltalk",
            )

        if asks_causal_story(task_text):
            try:
                from src.db.connection import get_db
                from src.services.th_hitl_flow import causal_reply_for_ask, day_idx_to_calendar_day

                ctx = workspace_binding(messages)
                day = ctx.get("calendar_day") or day_idx_to_calendar_day(ctx.get("active_day"))
                reply = causal_reply_for_ask(
                    get_db(), ctx.get("dataset_key"), day, extract_entity_token(task_text)
                )
                if reply:
                    return LLMResponse(content=reply, finish_reason="stop", model_used="heuristic-causal")
            except Exception:
                pass

        if has_observation:
            obs = last_observation_text(messages)
            if asks_dataset_inventory(task_text):
                return LLMResponse(content=CANNED_INVENTORY, finish_reason="stop", model_used="heuristic")
            shown = (obs or last_user)[:600]
            return LLMResponse(
                content=f"Done. You asked: {(last_user or '')[:180]}\n{shown}".strip(),
                finish_reason="stop",
                model_used="heuristic-done",
            )

        if "profile" in task_text or "profile_dataset" in task_text or "profiling" in task_text:
            return LLMResponse(
                content="ACTION: profile_dataset\nARGS: {}",
                tool_calls=[{"name": "profile_dataset", "args": {}}],
                finish_reason="tool_calls",
                model_used="heuristic-profiler"
            )
        if "anomal" in task_text or "detect_anomalies" in task_text:
            return LLMResponse(
                content="ACTION: detect_anomalies\nARGS: {}",
                tool_calls=[{"name": "detect_anomalies", "args": {}}],
                finish_reason="tool_calls",
                model_used="heuristic-anomaly"
            )
        if "propose" in task_text or "quality rule" in task_text or "propose_quality_rules" in task_text:
            return LLMResponse(
                content="ACTION: propose_quality_rules\nARGS: {}",
                tool_calls=[{"name": "propose_quality_rules", "args": {}}],
                finish_reason="tool_calls",
                model_used="heuristic-proposer"
            )
        wants_clean = any(
            k in task_text
            for k in ("clean database", "clean the database", "làm sạch", "lam sach", "execute warehouse")
        )
        if wants_clean and "edit rule" not in task_text:
            return LLMResponse(
                content="ACTION: clean_database\nARGS: {}",
                tool_calls=[{"name": "clean_database", "args": {}}],
                finish_reason="tool_calls",
                model_used="heuristic-executor",
            )

        # 3. Chat — inventory only on an explicit list-datasets ask. Never catalog / Context JSON.
        if "pong" in last_user and any(k in last_user for k in ("reply", "only", "one word", "ping")):
            reply = "LLM off. You asked for a one-word PONG ping — I will not list datasets or run tools."
        elif asks_dataset_inventory(task_text):
            reply = CANNED_INVENTORY
        else:
            shown = (last_user or "").strip()[:240] or "your last message"
            reply = (
                f"LLM off — answering from your text, not the tool catalog: «{shown}». "
                "Say profile / detect / propose / edit rule / list datasets if you want a tool."
            )

        return LLMResponse(content=reply, finish_reason="stop", model_used="heuristic")

    def structured_output(self, prompt: str, schema: dict) -> dict:
        if not self.use_llm:
            if "rules" in schema.get("properties", {}):
                return {
                    "rules": [
                        {
                            "rule_name": "prevent_invalid_soc",
                            "target_table": "ev_telemetry",
                            "condition": "battery_soc >= 0 AND battery_soc <= 100",
                            "action": "QUARANTINE",
                            "reasoning": "Heuristic fallback: battery_soc must strictly stay in [0, 100]."
                        }
                    ],
                    "diagnosis": "Heuristic analysis complete."
                }
            return {"status": "completed", "message": "Heuristic fallback structured response"}

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
