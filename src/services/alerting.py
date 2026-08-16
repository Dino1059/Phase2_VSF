import uuid
import datetime
import logging
import json
import hmac
import hashlib
from enum import Enum
from typing import Dict, List, Optional, Any, Union
import httpx
from pydantic import BaseModel, Field
from src.services.security import validate_webhook_url

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RootCauseDiagnosis(BaseModel):
    """Structured JSON format for root-cause diagnosis of anomalies/alerts."""

    summary: str = Field(..., description="High-level summary of root cause diagnosis")
    category: str = Field(
        default="DATA_QUALITY",
        description="Category: DATA_DRIFT, SCHEMA_DRIFT, ARITHMETIC_MISMATCH, BOUND_VIOLATION, PIPELINE_ERROR",
    )
    affected_component: str = Field(..., description="Impacted column, dataset, or pipeline component")
    triggering_metric: Optional[str] = Field(default=None, description="Metric triggering the alert")
    current_value: Optional[Any] = Field(default=None, description="Observed current value")
    expected_baseline: Optional[Any] = Field(default=None, description="Expected baseline value or range")
    suspected_cause: str = Field(..., description="Deep explanation of suspected root cause")
    suggested_action: str = Field(..., description="Actionable remediation recommendation")
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Diagnosis confidence score")


class Alert(BaseModel):
    """In-app alert notification schema."""

    alert_id: str = Field(default_factory=lambda: f"alert_{uuid.uuid4().hex[:8]}")
    title: str
    message: str
    severity: str = "MEDIUM"  # LOW, MEDIUM, HIGH, CRITICAL
    source: str = "DataTrust OS"
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now().isoformat())
    status: str = "ACTIVE"  # ACTIVE, ACKNOWLEDGED, RESOLVED
    webhook_url: Optional[str] = None
    root_cause: Optional[Dict[str, Any]] = None  # Structured JSON format
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AlertService:
    """Alert Service managing in-app notifications and webhook dispatch."""

    def __init__(self, default_webhook_url: Optional[str] = None, webhook_secret: str = "datatrust-secret-key"):
        self._alerts: Dict[str, Alert] = {}
        self.default_webhook_url = default_webhook_url
        self.webhook_secret = webhook_secret

    def create_alert(
        self,
        title: str,
        message: str,
        severity: Union[str, AlertSeverity] = AlertSeverity.MEDIUM,
        source: str = "DataTrust OS",
        root_cause: Optional[Union[Dict[str, Any], RootCauseDiagnosis]] = None,
        webhook_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        auto_dispatch: bool = True,
    ) -> Alert:
        """Create a new alert and optionally dispatch webhook."""
        sev_str = severity.value if isinstance(severity, AlertSeverity) else str(severity).upper()
        if sev_str not in [s.value for s in AlertSeverity]:
            sev_str = "MEDIUM"

        rc_dict = None
        if isinstance(root_cause, RootCauseDiagnosis):
            rc_dict = root_cause.model_dump()
        elif isinstance(root_cause, dict):
            rc_dict = root_cause

        w_url = webhook_url or self.default_webhook_url

        alert = Alert(
            title=title,
            message=message,
            severity=sev_str,
            source=source,
            webhook_url=w_url,
            root_cause=rc_dict,
            metadata=metadata or {},
        )

        self._alerts[alert.alert_id] = alert
        logger.info(f"Created Alert '{title}' [{sev_str}] (ID: {alert.alert_id})")

        if auto_dispatch and w_url:
            self.dispatch_webhook(alert, w_url)

        return alert

    def dispatch_webhook(self, alert: Alert, webhook_url: Optional[str] = None) -> bool:
        target_url = webhook_url or alert.webhook_url or self.default_webhook_url
        if not target_url or not validate_webhook_url(target_url):
            logger.warning(f"Invalid or unsafe webhook URL for alert {alert.alert_id}: {target_url}")
            return False

        payload = {
            "event": "alert.triggered",
            "alert": alert.model_dump(),
            "dispatched_at": datetime.datetime.now().isoformat(),
        }
        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        signature = hmac.new(self.webhook_secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "X-DataTrust-Signature": f"sha256={signature}",
            "User-Agent": "DataTrust-AlertService/4.2"
        }

        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.post(target_url, content=payload_bytes, headers=headers)
                if resp.status_code in (200, 201, 202, 204):
                    logger.info(f"Successfully dispatched webhook for alert {alert.alert_id} to {target_url}")
                    return True
                else:
                    logger.warning(
                        f"Webhook endpoint returned non-2xx status {resp.status_code} for alert {alert.alert_id}"
                    )
                    return False
        except Exception as e:
            logger.error(f"Failed to dispatch webhook for alert {alert.alert_id} to {target_url}: {e}")
            return False

    def get_alerts(
        self, severity: Optional[str] = None, status: Optional[str] = None
    ) -> List[Alert]:
        """Retrieve in-app alerts filtered by severity and/or status."""
        result = list(self._alerts.values())

        if severity:
            sev_target = severity.upper()
            result = [a for a in result if a.severity.upper() == sev_target]

        if status:
            stat_target = status.upper()
            result = [a for a in result if a.status.upper() == stat_target]

        # Sort newest first
        result.sort(key=lambda x: x.timestamp, reverse=True)
        return result

    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """Get alert by ID."""
        return self._alerts.get(alert_id)

    def acknowledge_alert(self, alert_id: str) -> Optional[Alert]:
        """Mark alert as ACKNOWLEDGED."""
        alert = self._alerts.get(alert_id)
        if alert:
            alert.status = "ACKNOWLEDGED"
            logger.info(f"Alert {alert_id} marked ACKNOWLEDGED")
        return alert

    def resolve_alert(self, alert_id: str) -> Optional[Alert]:
        """Mark alert as RESOLVED."""
        alert = self._alerts.get(alert_id)
        if alert:
            alert.status = "RESOLVED"
            logger.info(f"Alert {alert_id} marked RESOLVED")
        return alert

    def clear(self) -> None:
        """Clear all alerts."""
        self._alerts.clear()

    @staticmethod
    def create_root_cause_diagnosis(
        summary: str,
        affected_component: str,
        suspected_cause: str,
        suggested_action: str,
        category: str = "DATA_QUALITY",
        triggering_metric: Optional[str] = None,
        current_value: Optional[Any] = None,
        expected_baseline: Optional[Any] = None,
        confidence_score: float = 1.0,
    ) -> Dict[str, Any]:
        """Helper function to build a structured root-cause diagnosis JSON format."""
        rc = RootCauseDiagnosis(
            summary=summary,
            category=category,
            affected_component=affected_component,
            triggering_metric=triggering_metric,
            current_value=current_value,
            expected_baseline=expected_baseline,
            suspected_cause=suspected_cause,
            suggested_action=suggested_action,
            confidence_score=confidence_score,
        )
        return rc.model_dump()


# Global singleton instance
alert_service = AlertService()
