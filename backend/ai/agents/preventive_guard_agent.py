"""
DataTrust OS: Preventive Guard Sub-Agent (Real-Time Early Warning)
Proactively inspects L2 distribution drift, L3 policy failure rates, and L4 downstream risk.
Emits PreventiveAlertModel alerts before corrupt records breach critical L1 runtime thresholds.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import uuid

from backend.database.models import PreventiveAlertModel, ProposedRuleModel
from backend.ai.tools.anomaly_tool import AnomalyTool
from backend.ai.engine.react_engine import ReActEngine


class PreventiveGuardAgent:
    def __init__(
        self,
        react_engine: Optional[ReActEngine] = None,
        anomaly_tool: Optional[AnomalyTool] = None
    ):
        self.react_engine = react_engine or ReActEngine()
        self.anomaly_tool = anomaly_tool or AnomalyTool()
        self.alerts: List[PreventiveAlertModel] = []

    def scan_for_preventive_risks(
        self,
        dataset_id: str,
        monitored_columns: List[str]
    ) -> List[PreventiveAlertModel]:
        """
        Scans columns for distribution drift and issues early-warning alerts.
        """
        new_alerts: List[PreventiveAlertModel] = []

        for col in monitored_columns:
            res = self.anomaly_tool.execute({"dataset_id": dataset_id, "column_name": col})
            if "error" in res:
                continue

            outlier_pct = res.get("outlier_percentage", 0.0)
            status = res.get("status", "NORMAL")

            if status in ("WARNING", "CRITICAL") or outlier_pct > 1.0:
                alert = PreventiveAlertModel(
                    alert_id=f"ALT-{uuid.uuid4().hex[:8].upper()}",
                    dataset_id=dataset_id,
                    column_name=col,
                    signal_layer=res.get("risk_layer", "L2_STATISTICAL_DISTRIBUTION"),
                    drift_metric=res.get("drift_metric", "modified_zscore_mad"),
                    current_value=float(outlier_pct),
                    warning_threshold=1.0,
                    predicted_risk=f"Tỷ lệ điểm dữ liệu lệch chuẩn là {outlier_pct}%. Nguy cơ bản ghi bị cách ly ở chu kỳ tiếp theo.",
                    detected_at=datetime.now(timezone.utc)
                )
                self.alerts.append(alert)
                new_alerts.append(alert)

        return new_alerts

    def get_all_alerts(self) -> List[PreventiveAlertModel]:
        return list(self.alerts)
