import json
import logging
import os
from typing import Any, Dict, Optional, Type, TypeVar
from pydantic import BaseModel

from src.config import get_settings
from src.models.schemas import DecisionObject, QualityRule, RuleProposal, ValidationResult

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

        # Default fallback creation for any Pydantic model
        try:
            return response_model.model_construct()
        except Exception:
            raise ValueError(f"Mock generation for model {response_model.__name__} not supported.")


class LLMService:
    """Provider-agnostic LLM service enforcing structured outputs."""

    def __init__(self, provider: Optional[str] = None, model_name: Optional[str] = None):
        settings = get_settings()
        self.provider = provider or os.getenv("LLM_PROVIDER", "offline_mock")
        self.model_name = model_name or settings.model_name
        self.openai_api_key = settings.openai_api_key
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        self.mock_llm = OfflineMockLLM()

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
