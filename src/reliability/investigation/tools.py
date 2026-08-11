from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class InvestigationToolResult(BaseModel):
    tool_name: str
    success: bool
    data: Dict[str, Any] = Field(default_factory=dict)
    evidence_ref: str
    tokens_used: int = 50


class InvestigationToolRegistry:
    """
    Registry of bounded diagnostic tools for A1 dynamic investigation.
    """

    def fetch_entity_telemetry(self, entity_id: str, metric: str) -> InvestigationToolResult:
        return InvestigationToolResult(
            tool_name="fetch_entity_telemetry",
            success=True,
            data={"entity_id": entity_id, "metric": metric, "sample_count": 96, "mean_val": 42.0},
            evidence_ref=f"ev-telemetry-{entity_id}-{metric}",
            tokens_used=120
        )

    def query_historical_baselines(self, entity_id: str) -> InvestigationToolResult:
        return InvestigationToolResult(
            tool_name="query_historical_baselines",
            success=True,
            data={"entity_id": entity_id, "baseline_median": 90.0, "baseline_mad": 2.1},
            evidence_ref=f"ev-baseline-{entity_id}",
            tokens_used=90
        )

    def inspect_upstream_contracts(self, dataset_key: str) -> InvestigationToolResult:
        return InvestigationToolResult(
            tool_name="inspect_upstream_contracts",
            success=True,
            data={"dataset_key": dataset_key, "contract_version": "1.2.0", "status": "ACTIVE"},
            evidence_ref=f"ev-contract-{dataset_key}",
            tokens_used=80
        )
