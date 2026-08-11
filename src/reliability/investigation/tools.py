from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set, Callable
from pydantic import BaseModel, Field
import inspect


class InvestigationToolResult(BaseModel):
    """
    Standardized typed result wrapper for A1 investigation tools.
    """
    tool_name: str
    success: bool
    data: Dict[str, Any] = Field(default_factory=dict)
    evidence_ref: str
    tokens_used: int = 50
    entity_scope: List[str] = Field(default_factory=list)
    time_scope: Dict[str, Any] = Field(default_factory=dict)


def readonly_tool(func: Callable) -> Callable:
    """Decorator marking a tool method as strictly read-only."""
    setattr(func, "_is_readonly", True)
    return func


class InvestigationToolRegistry:
    """
    Registry of typed, bounded, read-only diagnostic tools for A1 dynamic investigation.
    Guarantees zero state mutation tools exist in the registry.
    """

    # List of keywords indicating state mutation (strictly forbidden in read-only registry)
    FORBIDDEN_MUTATION_KEYWORDS: Set[str] = {
        "update", "delete", "insert", "create", "remove", "drop",
        "alter", "write", "mutate", "post", "put", "patch", "execute"
    }

    def __init__(self, mock_data: Optional[Dict[str, Any]] = None):
        self._mock_data = mock_data or {}
        self._validate_zero_mutation()

    def _validate_zero_mutation(self) -> None:
        """
        Validates that zero state mutation tools exist in the registry.
        All public methods must be strictly read-only fetchers/calculators.
        """
        cls = self.__class__
        public_methods = [
            name for name, attr in cls.__dict__.items()
            if not name.startswith("_") and callable(attr) and not isinstance(attr, property)
        ]
        for name in public_methods:
            name_lower = name.lower()
            if any(kw in name_lower for kw in self.FORBIDDEN_MUTATION_KEYWORDS):
                raise ValueError(
                    f"Mutation tool detected in read-only registry: '{name}'. "
                    f"Zero state mutation tools are permitted."
                )

    @property
    def registered_tools(self) -> List[str]:
        """Returns list of registered read-only tool names."""
        cls = self.__class__
        return [
            name for name, attr in cls.__dict__.items()
            if not name.startswith("_") and callable(attr) and not isinstance(attr, property)
        ]

    def verify_zero_state_mutation(self) -> bool:
        """Explicit assertion check confirming zero mutation tools in registry."""
        try:
            self._validate_zero_mutation()
            return True
        except ValueError:
            return False

    @readonly_tool
    def fetch_entity_telemetry(
        self,
        entity_id: str,
        metric: Optional[str] = "battery_soc",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        time_window: Optional[Dict[str, Any]] = None
    ) -> InvestigationToolResult:
        """Fetches telemetry signals for an entity within a specified time scope."""
        metric_name = metric or "battery_soc"
        t_start = start_time.isoformat() if start_time else (time_window.get("start") if time_window else None)
        t_end = end_time.isoformat() if end_time else (time_window.get("end") if time_window else None)

        mean_val = 42.0 if metric_name == "battery_soc" else (85.5 if "temp" in metric_name else 380.0)
        anomaly_detected = "soc" in metric_name or "temp" in metric_name or "voltage" in metric_name

        data = {
            "entity_id": entity_id,
            "metric": metric_name,
            "sample_count": 96,
            "mean_val": mean_val,
            "min_val": mean_val - 12.5,
            "max_val": mean_val + 5.0,
            "anomaly_detected": anomaly_detected,
            "unit": "%" if "soc" in metric_name else ("C" if "temp" in metric_name else "V"),
        }

        return InvestigationToolResult(
            tool_name="fetch_entity_telemetry",
            success=True,
            data=data,
            evidence_ref=f"ev-telemetry-{entity_id}-{metric_name}",
            tokens_used=120,
            entity_scope=[entity_id],
            time_scope={"start": t_start, "end": t_end} if (t_start or t_end) else {}
        )

    @readonly_tool
    def fetch_trip_history(
        self,
        entity_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 50
    ) -> InvestigationToolResult:
        """Fetches trip logs and operational ride-hailing history for an entity."""
        t_start = start_time.isoformat() if start_time else None
        t_end = end_time.isoformat() if end_time else None

        data = {
            "entity_id": entity_id,
            "total_trips": 18,
            "completed_trips": 17,
            "aborted_trips": 1,
            "avg_distance_km": 14.2,
            "recent_trips": [
                {
                    "trip_id": f"trip-{entity_id}-101",
                    "status": "COMPLETED",
                    "distance_km": 12.5,
                    "avg_speed_kmh": 32.0,
                    "anomaly_flag": False
                },
                {
                    "trip_id": f"trip-{entity_id}-102",
                    "status": "ABORTED_THERMAL_ALERT",
                    "distance_km": 3.1,
                    "avg_speed_kmh": 18.5,
                    "anomaly_flag": True
                }
            ]
        }

        return InvestigationToolResult(
            tool_name="fetch_trip_history",
            success=True,
            data=data,
            evidence_ref=f"ev-trip-history-{entity_id}",
            tokens_used=95,
            entity_scope=[entity_id],
            time_scope={"start": t_start, "end": t_end} if (t_start or t_end) else {}
        )

    @readonly_tool
    def fetch_charging_history(
        self,
        entity_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 50
    ) -> InvestigationToolResult:
        """Fetches charging session history and power delivery events for an EV/station entity."""
        t_start = start_time.isoformat() if start_time else None
        t_end = end_time.isoformat() if end_time else None

        related_charger = f"CS-{entity_id[-3:] if len(entity_id) >= 3 else '101'}"

        data = {
            "entity_id": entity_id,
            "sessions_count": 6,
            "primary_station_id": related_charger,
            "total_kwh_delivered": 142.5,
            "voltage_drop_events": 2,
            "thermal_warnings": 1,
            "recent_sessions": [
                {
                    "session_id": f"csess-{entity_id}-01",
                    "station_id": related_charger,
                    "kwh": 35.4,
                    "max_kw": 120.0,
                    "status": "INTERRUPTED_OVERHEAT",
                    "timestamp": t_start or "2026-08-11T10:15:00Z"
                }
            ]
        }

        return InvestigationToolResult(
            tool_name="fetch_charging_history",
            success=True,
            data=data,
            evidence_ref=f"ev-charging-history-{entity_id}",
            tokens_used=110,
            entity_scope=[entity_id, related_charger],
            time_scope={"start": t_start, "end": t_end} if (t_start or t_end) else {}
        )

    @readonly_tool
    def fetch_profile(
        self,
        entity_id: str
    ) -> InvestigationToolResult:
        """Fetches static asset metadata, specifications, and schema profile."""
        data = {
            "entity_id": entity_id,
            "entity_type": "VEHICLE" if ("VIN" in entity_id or "VF" in entity_id) else "CHARGING_STATION",
            "model": "VF8_PLUS" if ("VIN" in entity_id or "VF" in entity_id) else "DC_FAST_150KW",
            "battery_capacity_kwh": 87.7 if ("VIN" in entity_id or "VF" in entity_id) else None,
            "firmware_version": "v3.4.12-prod",
            "hardware_revision": "HW-REV-B",
            "region": "VN-HCMC",
            "status": "ACTIVE_MONITORED",
            "schema_version": "1.2.0"
        }

        return InvestigationToolResult(
            tool_name="fetch_profile",
            success=True,
            data=data,
            evidence_ref=f"ev-profile-{entity_id}",
            tokens_used=80,
            entity_scope=[entity_id]
        )

    @readonly_tool
    def fetch_dq_violations(
        self,
        entity_id: str,
        rule_type: Optional[str] = None
    ) -> InvestigationToolResult:
        """Fetches data quality / L1 rule violations recorded for an entity."""
        data = {
            "entity_id": entity_id,
            "total_violations": 3,
            "rule_filter": rule_type or "ALL",
            "violations": [
                {
                    "rule_id": "L1_RANGE_CHECK",
                    "rule_name": "Battery SoC Out of Bounds",
                    "field": "battery_soc",
                    "expected": "[0.0, 100.0]",
                    "actual": "-5.2",
                    "severity": "HIGH",
                    "timestamp": "2026-08-11T14:20:00Z"
                },
                {
                    "rule_id": "L1_NULL_CHECK",
                    "rule_name": "Non-Null Cell Voltage",
                    "field": "cell_voltage_01",
                    "expected": "NOT_NULL",
                    "actual": "NULL",
                    "severity": "CRITICAL",
                    "timestamp": "2026-08-11T14:22:00Z"
                }
            ]
        }

        return InvestigationToolResult(
            tool_name="fetch_dq_violations",
            success=True,
            data=data,
            evidence_ref=f"ev-dq-violations-{entity_id}",
            tokens_used=100,
            entity_scope=[entity_id]
        )

    @readonly_tool
    def fetch_recent_changes(
        self,
        entity_id: str,
        scope: Optional[str] = None
    ) -> InvestigationToolResult:
        """Fetches recent configuration, firmware, or schema deployments for an entity."""
        data = {
            "entity_id": entity_id,
            "scope": scope or "ALL",
            "change_count": 2,
            "recent_changes": [
                {
                    "change_id": "chg-20260810-01",
                    "change_type": "FIRMWARE_UPDATE",
                    "deployed_at": "2026-08-10T18:00:00Z",
                    "version_from": "v3.4.11",
                    "version_to": "v3.4.12-prod",
                    "author": "deploy-bot",
                    "status": "SUCCESS"
                },
                {
                    "change_id": "chg-20260811-04",
                    "change_type": "SCHEMA_FIELD_RENAME",
                    "deployed_at": "2026-08-11T12:30:00Z",
                    "field_from": "soc_val",
                    "field_to": "battery_soc",
                    "author": "data-infra",
                    "status": "COMPLETED"
                }
            ]
        }

        return InvestigationToolResult(
            tool_name="fetch_recent_changes",
            success=True,
            data=data,
            evidence_ref=f"ev-recent-changes-{entity_id}",
            tokens_used=85,
            entity_scope=[entity_id]
        )

    @readonly_tool
    def resolve_entity_relationships(
        self,
        entity_id: str,
        relationship_type: Optional[str] = None
    ) -> InvestigationToolResult:
        """
        Resolves entity relationships and graph dependencies (e.g. vehicle -> charger -> depot).
        Enables dynamic entity scope resolution based on intermediate observations.
        """
        charger_id = f"CS-{entity_id[-3:] if len(entity_id) >= 3 else '101'}"
        bms_sensor_id = f"bms-sensor-{entity_id}"
        fleet_id = "fleet-hcmc-express"

        related_entities = [
            {"entity_id": charger_id, "relationship_type": "CHARGING_STATION", "strength": "DIRECT"},
            {"entity_id": bms_sensor_id, "relationship_type": "BMS_SENSOR", "strength": "COMPONENT"},
            {"entity_id": fleet_id, "relationship_type": "PARENT_FLEET", "strength": "MEMBERSHIP"}
        ]

        if relationship_type:
            related_entities = [r for r in related_entities if r["relationship_type"] == relationship_type.upper()]

        discovered_ids = [r["entity_id"] for r in related_entities]

        data = {
            "primary_entity_id": entity_id,
            "relationship_filter": relationship_type or "ALL",
            "related_entities": related_entities,
            "discovered_entity_ids": discovered_ids
        }

        return InvestigationToolResult(
            tool_name="resolve_entity_relationships",
            success=True,
            data=data,
            evidence_ref=f"ev-relationships-{entity_id}",
            tokens_used=75,
            entity_scope=[entity_id] + discovered_ids
        )

    @readonly_tool
    def calculate_detector_detail(
        self,
        entity_id: str,
        detector_id: Optional[str] = None,
        layer: Optional[str] = None
    ) -> InvestigationToolResult:
        """Calculates detailed z-score, MAD, or changepoint metrics for a specific detector and entity."""
        target_layer = layer or "L2"
        data = {
            "entity_id": entity_id,
            "detector_id": detector_id or f"det-{target_layer.lower()}-01",
            "layer": target_layer,
            "z_score": 4.82,
            "mad_score": 3.91,
            "p_value": 0.0012,
            "threshold": 3.0,
            "is_anomalous": True,
            "diagnostic_metrics": {
                "window_size": "24h",
                "baseline_median": 90.0,
                "baseline_mad": 2.1,
                "observed_val": 42.0
            }
        }

        return InvestigationToolResult(
            tool_name="calculate_detector_detail",
            success=True,
            data=data,
            evidence_ref=f"ev-detector-{entity_id}",
            tokens_used=90,
            entity_scope=[entity_id]
        )

    # Legacy / Backward Compatibility Methods
    @readonly_tool
    def query_historical_baselines(self, entity_id: str) -> InvestigationToolResult:
        """Legacy helper for historical baseline query."""
        res = self.calculate_detector_detail(entity_id, layer="L2")
        res.tool_name = "query_historical_baselines"
        res.evidence_ref = f"ev-baseline-{entity_id}"
        return res

    @readonly_tool
    def inspect_upstream_contracts(self, dataset_key: str) -> InvestigationToolResult:
        """Legacy helper for contract inspection."""
        res = self.fetch_profile(dataset_key)
        res.tool_name = "inspect_upstream_contracts"
        res.evidence_ref = f"ev-contract-{dataset_key}"
        res.data = {"dataset_key": dataset_key, "contract_version": "1.2.0", "status": "ACTIVE"}
        return res

