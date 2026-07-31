import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from src.tools.validator import RuleSpec


class LLMResponse(BaseModel):
    rules: List[RuleSpec] = Field(default_factory=list)
    reasoning: str = ""
    prompt_tokens: int = 150
    completion_tokens: int = 100
    cost_usd: float = 0.0005


class LLMAdapter:
    def __init__(self, provider: str = "mock", model_name: str = "gpt-4o-mini", api_key: str = ""):
        self.provider = provider
        self.model_name = model_name
        self.api_key = api_key

    def propose_rules(self, context: str, retry_error: Optional[str] = None) -> LLMResponse:
        """Proposes data quality and transformation rules based on context."""
        # For mock/test execution, return deterministic structured rules
        rules = [
            RuleSpec(
                rule_id="rule_dup_01",
                rule_type="unique",
                target_column=None,
                action="drop_duplicates",
                severity="high",
                description="Drop duplicate rows in dataset",
            ),
            RuleSpec(
                rule_id="rule_null_01",
                rule_type="not_null",
                target_column="driver_pay",
                parameters={"fill_value": 0.0},
                action="fill_null",
                severity="medium",
                description="Fill null driver_pay with 0.0",
            ),
            RuleSpec(
                rule_id="rule_range_01",
                rule_type="range",
                target_column="trip_miles",
                parameters={"min": 0.0, "max": 500.0},
                action="quarantine_range",
                severity="high",
                description="Quarantine trip_miles outside [0, 500]",
            ),
            RuleSpec(
                rule_id="rule_cross_01",
                rule_type="cross_field",
                target_column="PULocationID",
                parameters={
                    "col1": "PULocationID",
                    "col2": "DOLocationID",
                    "operator": "equal_implies_miles_zero",
                    "miles_col": "trip_miles",
                    "rule_type": "pickup_dropoff_miles",
                },
                action="quarantine_cross_field",
                severity="medium",
                description="Quarantine rows where PULocationID == DOLocationID but trip_miles > 0",
            ),
        ]

        # If retry_error indicates a compile or validation issue, repair the rule list
        if retry_error:
            # Modify or remove problematic rules to demonstrate repair
            rules = [r for r in rules if r.rule_id != "rule_invalid"]

        return LLMResponse(
            rules=rules,
            reasoning="Analyzed data profile and generated 4 structured data quality rules.",
            prompt_tokens=200 if not retry_error else 350,
            completion_tokens=120,
            cost_usd=0.0008 if not retry_error else 0.0014,
        )
