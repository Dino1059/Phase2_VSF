from typing import List, Dict, Any, Tuple, Optional
from src.reliability.models.signal import Signal


class AdmissionPolicy:
    """
    Evaluates whether a cluster of fused signals qualifies for Incident Admission.
    """

    def evaluate_admission(self, signals: List[Signal]) -> Tuple[bool, str]:
        """
        Returns (is_admitted, admission_reason).
        """
        if not signals:
            return False, "No signals provided"

        layers = {s.layer for s in signals}
        severities = {s.severity for s in signals}

        # Rule 1: Critical L1 signal
        for s in signals:
            if s.layer == "L1" and s.severity == "CRITICAL":
                return True, f"Critical L1 signal admitted: {s.metric_or_relationship}"

        # Rule 2: Multi-layer agreement (>= 2 layers)
        if len(layers) >= 2:
            return True, f"Multi-layer agreement across {', '.join(sorted(layers))} layers"

        # Rule 3: High-severity or persistent signals
        for s in signals:
            if s.severity in ("HIGH", "CRITICAL"):
                return True, f"High severity {s.layer} signal admitted ({s.metric_or_relationship})"

        # Rule 4: Persistent signals (>= 3 signals for same entity)
        if len(signals) >= 3:
            return True, f"Persistent signal cluster ({len(signals)} signals detected)"

        return False, "Signals do not meet incident admission thresholds"
