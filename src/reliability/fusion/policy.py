from typing import List, Dict, Any, Tuple, Optional
from src.reliability.models.signal import Signal


class AdmissionPolicy:
    """
    Evaluates whether a cluster of fused signals qualifies for Incident Admission
    using calibrated non-LLM admission rules:
    1. Critical L1 signal
    2. Multi-layer agreement (>= 2 layers)
    3. Persistent L2 anomaly
    4. Repeated signals across related entities
    """

    def evaluate_admission(self, signals: List[Signal]) -> Tuple[bool, str]:
        """
        Returns (is_admitted, admission_reason).
        """
        if not signals:
            return False, "No signals provided"

        # Rule 1: Multi-layer agreement (>= 2 layers)
        layers = {s.layer for s in signals}
        if len(layers) >= 2:
            sorted_layers = ", ".join(sorted(layers))
            return True, f"Multi-layer agreement across {sorted_layers} layers"

        # Rule 2: Critical L1 signal
        critical_l1 = [s for s in signals if s.layer == "L1" and s.severity == "CRITICAL"]
        if critical_l1:
            first_l1 = critical_l1[0]
            return True, f"Critical L1 signal admitted: {first_l1.metric_or_relationship}"

        # Rule 3: Repeated signals across related entities
        all_entities = set()
        for s in signals:
            all_entities.update(s.entity_ids)

        if len(signals) >= 2 and (len(all_entities) >= 2 or any(len(s.entity_ids) >= 2 for s in signals)):
            entities_str = ", ".join(sorted(all_entities))
            return True, f"Repeated signals across related entities: {entities_str}"

        # Rule 4: Persistent L2 anomaly
        l2_signals = [s for s in signals if s.layer == "L2"]
        if l2_signals:
            has_high_or_critical = any(s.severity in ("HIGH", "CRITICAL") for s in l2_signals)
            is_persistent = len(l2_signals) >= 2 or has_high_or_critical
            if is_persistent:
                metrics = ", ".join(sorted({s.metric_or_relationship for s in l2_signals}))
                return True, f"Persistent L2 anomaly detected: {len(l2_signals)} signal(s) ({metrics})"

        # Fallback rule: High-severity or persistent signal cluster
        for s in signals:
            if s.severity in ("HIGH", "CRITICAL"):
                return True, f"High severity {s.layer} signal admitted ({s.metric_or_relationship})"

        if len(signals) >= 3:
            return True, f"Persistent signal cluster ({len(signals)} signals detected)"

        return False, "Signals do not meet incident admission thresholds"
