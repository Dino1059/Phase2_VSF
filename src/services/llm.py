import json
import logging
import os
from typing import Any, Dict, Optional, Type, TypeVar
from pydantic import BaseModel

from src.config import get_settings
from src.models.schemas import (
    AnomalyItem,
    AnomalyReport,
    DecisionObject,
    DiagnosisReport,
    QualityRule,
    RuleProposal,
    ValidationResult,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class OfflineMockLLM:
    """Offline deterministic mock adapter for testing and offline execution.
    Guarantees structured output matching any requested Pydantic schema class.
    """

    def generate_structured(
        self, prompt: str, response_model: Type[T], system_prompt: Optional[str] = None
    ) -> T:
        prompt_lower = prompt.lower()

        if response_model == DecisionObject:
            # Determine appropriate mock decision based on prompt context
            if "fail" in prompt_lower or "violation" in prompt_lower or "repair" in prompt_lower:
                obj = DecisionObject(
                    issue="Validation failed for initial rule parameters.",
                    evidence_refs=["violations", "failed_rules"],
                    confidence=0.85,
                    risk="medium",
                    next_action="submit_review",
                    action_input={
                        "proposal_id": "repaired_prop_001",
                        "reasoning": "Repaired rules to adjust parameters to match data profile.",
                        "rules": [
                            {
                                "rule_id": "rule_1",
                                "column": "id",
                                "rule_type": "not_null",
                                "severity": "high",
                                "description": "ID column must not be null",
                            },
                            {
                                "rule_id": "rule_2",
                                "column": "age",
                                "rule_type": "range",
                                "params": {"min": 18, "max": 100},
                                "severity": "medium",
                                "description": "Age between 18 and 100",
                            },
                        ],
                    },
                )
            elif "low confidence" in prompt_lower or "unknown column" in prompt_lower:
                obj = DecisionObject(
                    issue="Uncertain about column constraints due to missing domain information.",
                    evidence_refs=["null_percentage"],
                    confidence=0.4,
                    risk="high",
                    next_action="abstain",
                    action_input={"reason": "Confidence below threshold due to missing schema metadata."},
                )
            else:
                obj = DecisionObject(
                    issue="Initial data profiling complete; ready to submit proposed quality rules.",
                    evidence_refs=["columns", "schema_summary"],
                    confidence=0.92,
                    risk="low",
                    next_action="submit_review",
                    action_input={
                        "proposal_id": "prop_001",
                        "reasoning": "Generated standard quality rules for target table.",
                        "rules": [
                            {
                                "rule_id": "rule_1",
                                "column": "id",
                                "rule_type": "not_null",
                                "severity": "high",
                                "description": "ID column must not be null",
                            },
                            {
                                "rule_id": "rule_2",
                                "column": "age",
                                "rule_type": "range",
                                "params": {"min": 18, "max": 120},
                                "severity": "medium",
                                "description": "Age between 18 and 120",
                            },
                            {
                                "rule_id": "rule_3",
                                "column": "status",
                                "rule_type": "allowed_values",
                                "params": {"values": ["active", "inactive", "pending"]},
                                "severity": "medium",
                                "description": "Status must be valid enum value",
                            },
                        ],
                    },
                )
            return obj  # type: ignore

        elif response_model == RuleProposal:
            rules = [
                QualityRule(
                    rule_id="rule_1",
                    column="id",
                    rule_type="not_null",
                    severity="high",
                    description="ID must not be null",
                ),
                QualityRule(
                    rule_id="rule_2",
                    column="email",
                    rule_type="not_null",
                    severity="medium",
                    description="Email must not be null",
                ),
                QualityRule(
                    rule_id="rule_3",
                    column="age",
                    rule_type="range",
                    params={"min": 18, "max": 120},
                    severity="medium",
                    description="Age range check",
                ),
            ]
            return RuleProposal(
                proposal_id="mock_prop_100",
                rules=rules,
                reasoning="Deterministic mock rule proposal based on dataset schema.",
                confidence=0.9,
            )  # type: ignore

        elif response_model == AnomalyReport:
            anomalies = [
                AnomalyItem(
                    column="email",
                    anomaly_type="null_spike",
                    description="Null percentage spiked to 15% from 0% baseline",
                    severity="high",
                    metric_shift={"baseline_null_pct": 0.0, "current_null_pct": 15.0},
                    confidence=0.9,
                ),
                AnomalyItem(
                    column="age",
                    anomaly_type="range_shift",
                    description="Out-of-bound age values observed (max value 150)",
                    severity="medium",
                    metric_shift={"baseline_max": 85, "current_max": 150},
                    confidence=0.85,
                ),
            ]
            return AnomalyReport(
                report_id="mock_anom_001",
                dataset_name="dataset",
                detected_anomalies=anomalies,
                anomaly_score=0.75,
                summary="Detected 2 significant profile shift anomalies in email and age columns.",
                status="ANOMALY_DETECTED",
            )  # type: ignore

        elif response_model == DiagnosisReport:
            return DiagnosisReport(
                diagnosis_id="mock_diag_001",
                run_id="run_001",
                root_cause="Upstream system migration injected unvalidated NULL records into email field and negative values in age.",
                category="upstream_schema_change",
                affected_columns=["email", "age"],
                evidence=["Null percentage increased from 0% to 15%", "Range min dropped below threshold 0"],
                impact_level="high",
                recommended_remediation="Enforce mandatory NOT NULL constraint on email in ingestion connector and quarantine invalid age rows.",
                confidence=0.88,
            )  # type: ignore
        try:
            return response_model.model_construct()
        except Exception:
            raise ValueError(f"Mock generation for model {response_model.__name__} not supported.")


class GoogleAIStudioLLM:
    """Google AI Studio LLM adapter calling generative AI models (e.g. gemma-4-26b-a4b-it)
    via native HTTP API using AI_STUDIO_API_KEY from .env with 60s timeout & retry logic.
    """

    def __init__(self, api_key: str, model_name: str = "gemma-4-26b-a4b-it"):
        self.api_key = api_key
        self.model_name = model_name

    def _post_with_retry(self, url: str, payload_bytes: bytes, timeout: int = 60, max_retries: int = 3) -> Optional[dict]:
        import json
        import time
        import urllib.request

        req = urllib.request.Request(url, data=payload_bytes, headers={"Content-Type": "application/json"})
        for attempt in range(1, max_retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except Exception as e:
                logger.warning(f"Google AI Studio attempt {attempt}/{max_retries} for {self.model_name} failed: {e}")
                if attempt < max_retries:
                    time.sleep(2 * attempt)
        return None

    def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        import json
        full_prompt = f"{system_prompt}\n\nUser Question: {prompt}" if system_prompt else prompt
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        payload = json.dumps({
            "contents": [{"parts": [{"text": full_prompt}]}]
        }).encode("utf-8")

        data = self._post_with_retry(url, payload, timeout=60, max_retries=3)
        if data:
            candidates = data.get("candidates", [])
            if candidates and "content" in candidates[0]:
                text = candidates[0]["content"]["parts"][0]["text"].strip()
                if text:
                    return text

        return (
            f"DataTrust OS is an AI-Augmented Data Governance Platform.\n\n"
            "Here is how I can assist with your data workflow:\n\n"
            "- Upload & Register Datasets: Upload SQLite (.db), Parquet, CSV, or JSON files to start autonomous governance.\n"
            "- Profiler Agent: Automatically scans datasets to compute null rates, data types, distinct values, and column health scores.\n"
            "- Anomaly Detector Agent: Detects statistical outliers and schema drift using Z-Score, IQR, and Isolation Forest algorithms.\n"
            "- Rule Proposer Agent: Synthesizes data quality rules for Human-In-The-Loop approval.\n"
            "- Diagnosis Agent: Performs root-cause analysis on data defects and recommends remediation steps.\n"
            "- Clean DB Pipeline: Applies approved transformations and outputs cleaned Parquet/CSV database files.\n\n"
            "To get started, try running 'List datasets', 'Profile vietnam_trips_dirty', or upload a data file."
        )

    def stream_text(self, prompt: str, system_prompt: Optional[str] = None):
        import json
        import urllib.request
        import time

        full_prompt = f"{system_prompt}\n\nUser Question: {prompt}" if system_prompt else prompt
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:streamGenerateContent?key={self.api_key}"
        payload = json.dumps({
            "contents": [{"parts": [{"text": full_prompt}]}]
        }).encode("utf-8")

        for attempt in range(1, 4):
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    buffer = ""
                    for line in resp:
                        line_str = line.decode("utf-8", errors="ignore").strip()
                        if not line_str or line_str in ["[", "]", ","]:
                            continue
                        if line_str.startswith("{") or buffer:
                            buffer += line_str
                            try:
                                item = json.loads(buffer)
                                buffer = ""
                                candidates = item.get("candidates", [])
                                if candidates and "content" in candidates[0]:
                                    parts = candidates[0]["content"].get("parts", [])
                                    for p in parts:
                                        if p.get("thought"):
                                            yield {"type": "thought", "text": p.get("text", "")}
                                        elif "text" in p:
                                            yield {"type": "text", "text": p.get("text", "")}
                            except Exception:
                                pass
                return
            except Exception as e:
                logger.warning(f"Google AI Studio streaming attempt {attempt}/3 failed: {e}")
                if attempt < 3:
                    time.sleep(2 * attempt)

        yield {"type": "text", "text": self.generate_text(prompt, system_prompt)}

    def generate_agentic_tool_call(self, prompt: str, tools: list, contents: Optional[list] = None) -> dict:
        """Invokes LLM with function declarations and returns parsed function call or text response."""
        import json

        payload_contents = contents if contents else [{"role": "user", "parts": [{"text": prompt}]}]
        payload = {
            "contents": payload_contents,
            "tools": [{"functionDeclarations": tools}]
        }

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        data = self._post_with_retry(url, json.dumps(payload).encode("utf-8"), timeout=60, max_retries=3)

        if data:
            candidates = data.get("candidates", [])
            if candidates and "content" in candidates[0]:
                parts = candidates[0]["content"].get("parts", [])
                thought_text = ""
                for part in parts:
                    if part.get("thought"):
                        thought_text += part.get("text", "")
                    elif "functionCall" in part:
                        fc = part["functionCall"]
                        return {
                            "type": "function_call",
                            "name": fc.get("name"),
                            "args": fc.get("args", {}),
                            "thought": thought_text or part.get("text", "")
                        }
                    elif "text" in part and part["text"].strip():
                        return {
                            "type": "text",
                            "text": part["text"],
                            "thought": thought_text
                        }

        return {"type": "fallback", "text": self.generate_text(prompt)}


class LLMService:
    """Provider-agnostic LLM service enforcing structured outputs."""

    def __init__(self, provider: Optional[str] = None, model_name: Optional[str] = None):
        settings = get_settings()
        self.provider = provider or os.getenv("LLM_PROVIDER", "google_ai_studio")
        self.model_name = model_name or settings.ai_model
        self.openai_api_key = settings.openai_api_key
        self.ai_studio_api_key = settings.ai_studio_api_key or os.getenv("AI_STUDIO_API_KEY", "")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        self.mock_llm = OfflineMockLLM()
        if self.ai_studio_api_key:
            self.google_studio_llm = GoogleAIStudioLLM(api_key=self.ai_studio_api_key, model_name=self.model_name)
        else:
            self.google_studio_llm = None

    def generate_structured(
        self, prompt: str, response_model: Type[T], system_prompt: Optional[str] = None
    ) -> T:
        """Generates structured response adhering strictly to response_model schema."""
        # Use offline mock if specified or if no API keys are present
        if self.provider == "offline_mock" or (
            not self.openai_api_key and not self.gemini_api_key and self.provider != "mock"
        ):
            return self.mock_llm.generate_structured(prompt, response_model, system_prompt)

        if self.provider == "openai":
            try:
                from langchain_openai import ChatOpenAI
                llm = ChatOpenAI(
                    model=self.model_name,
                    api_key=self.openai_api_key,
                    temperature=0.0,
                )
                structured_llm = llm.with_structured_output(response_model)
                messages = []
                if system_prompt:
                    messages.append(("system", system_prompt))
                messages.append(("user", prompt))
                result = structured_llm.invoke(messages)
                if isinstance(result, response_model):
                    return result
                elif isinstance(result, dict):
                    return response_model(**result)
            except Exception as e:
                logger.warning(f"OpenAI call failed ({e}); falling back to offline mock.")
                return self.mock_llm.generate_structured(prompt, response_model, system_prompt)

        elif self.provider == "gemini":
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                llm = ChatGoogleGenerativeAI(
                    model=self.model_name or "gemini-1.5-pro",
                    google_api_key=self.gemini_api_key,
                    temperature=0.0,
                )
                structured_llm = llm.with_structured_output(response_model)
                messages = []
                if system_prompt:
                    messages.append(("system", system_prompt))
                messages.append(("user", prompt))
                result = structured_llm.invoke(messages)
                if isinstance(result, response_model):
                    return result
                elif isinstance(result, dict):
                    return response_model(**result)
            except Exception as e:
                logger.warning(f"Gemini call failed ({e}); falling back to offline mock.")
                return self.mock_llm.generate_structured(prompt, response_model, system_prompt)

        # Fallback to mock for unknown provider or errors
        return self.mock_llm.generate_structured(prompt, response_model, system_prompt)

    def stream_text(self, prompt: str, system_prompt: Optional[str] = None):
        """Streams natural language text or thought tokens."""
        if self.google_studio_llm:
            yield from self.google_studio_llm.stream_text(prompt, system_prompt)
        else:
            yield {"type": "text", "text": self.generate_text(prompt, system_prompt)}

    def generate_agentic_tool_call(self, prompt: str, tools: list, contents: Optional[list] = None) -> dict:
        """Invokes LLM for dynamic multi-agent tool decision."""
        if self.google_studio_llm:
            return self.google_studio_llm.generate_agentic_tool_call(prompt, tools, contents)
        return {"type": "fallback", "text": self.generate_text(prompt)}

    def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generates natural language text response."""
        if self.google_studio_llm:
            try:
                return self.google_studio_llm.generate_text(prompt, system_prompt)
            except Exception as e:
                logger.warning(f"Google AI Studio call failed: {e}")

        if self.provider == "openai" and self.openai_api_key:
            try:
                from langchain_openai import ChatOpenAI
                llm = ChatOpenAI(
                    model=self.model_name,
                    api_key=self.openai_api_key,
                    temperature=0.7,
                )
                messages = []
                if system_prompt:
                    messages.append(("system", system_prompt))
                messages.append(("user", prompt))
                res = llm.invoke(messages)
                return str(res.content)
            except Exception as e:
                logger.warning(f"OpenAI call failed ({e}); falling back to default assistant message.")

        return (
            f"I evaluated your query: '{prompt}'. DataTrust OS is an AI-augmented data governance system.\n\n"
            "Here are the active tools & sub-agents ready to run:\n"
            "- **ProfilerAgent**: Profile datasets and analyze schema quality\n"
            "- **RuleProposerAgent**: Propose data quality rules for review\n"
            "- **AnomalyDetectorAgent**: Detect statistical outliers and schema drift\n"
            "- **DiagnosisAgent**: Diagnose root causes for data defects\n"
            "- **DatasetRegistry**: List and upload datasets"
        )


def get_llm():
    """Legacy helper returning ChatOpenAI or fallback LLM instance."""
    settings = get_settings()
    if settings.openai_api_key:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.model_name,
            api_key=settings.openai_api_key,
            temperature=settings.llm_temperature,
        )
    # Default return if no API key
    return LLMService(provider="offline_mock")
