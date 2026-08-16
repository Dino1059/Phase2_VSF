"""Fault injection for benchmark evaluation. 9 fault families, seed=42."""
import random
import uuid
from dataclasses import dataclass, field


@dataclass
class InjectedFault:
    fault_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    fault_family: str = ""
    table: str = ""
    column: str = ""
    row_index: int = 0
    original_value: str = ""
    injected_value: str = ""
    description: str = ""


class FaultInjector:
    """Injects synthetic faults for ground-truth evaluation."""

    FAULT_FAMILIES = [
        "type_error", "range_error", "referential_error",
        "temporal_error", "geographic_error", "financial_error",
        "business_error", "privacy_error", "distribution_shift"
    ]

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.rng = random.Random(seed)
        self.injected: list[InjectedFault] = []

    def inject_type_error(self, table: str = "vgreen_telemetry") -> InjectedFault:
        f = InjectedFault(fault_family="type_error", table=table, column="temperature_celsius",
                          original_value="45.0", injected_value="HOT",
                          description="String in numeric column")
        self.injected.append(f)
        return f

    def inject_range_error(self, table: str = "vgreen_telemetry") -> InjectedFault:
        f = InjectedFault(fault_family="range_error", table=table, column="temperature_celsius",
                          original_value="45.0", injected_value="-999",
                          description="Value outside valid range [-10, 85]")
        self.injected.append(f)
        return f

    def inject_referential_error(self, table: str = "vgreen_telemetry") -> InjectedFault:
        f = InjectedFault(fault_family="referential_error", table=table, column="station_id",
                          original_value="VG-001", injected_value="INVALID-999",
                          description="Invalid foreign key reference")
        self.injected.append(f)
        return f

    def inject_temporal_error(self, table: str = "xanhsm_trips") -> InjectedFault:
        f = InjectedFault(fault_family="temporal_error", table=table, column="pickup_time",
                          original_value="2025-01-01T08:00:00", injected_value="2025-01-01T23:00:00",
                          description="Pickup time after dropoff time")
        self.injected.append(f)
        return f

    def inject_geographic_error(self, table: str = "xanhsm_trips") -> InjectedFault:
        f = InjectedFault(fault_family="geographic_error", table=table, column="pickup_lat",
                          original_value="10.762", injected_value="55.123",
                          description="Coordinates outside Vietnam")
        self.injected.append(f)
        return f

    def inject_financial_error(self, table: str = "xanhsm_trips") -> InjectedFault:
        f = InjectedFault(fault_family="financial_error", table=table, column="fare",
                          original_value="50000", injected_value="-1",
                          description="Negative fare")
        self.injected.append(f)
        return f

    def inject_business_error(self, table: str = "xanhsm_trips") -> InjectedFault:
        f = InjectedFault(fault_family="business_error", table=table, column="status",
                          original_value="completed", injected_value="completed_no_dropoff",
                          description="Completed trip with null dropoff")
        self.injected.append(f)
        return f

    def inject_privacy_error(self, table: str = "xanhsm_feedback") -> InjectedFault:
        f = InjectedFault(fault_family="privacy_error", table=table, column="review_text",
                          original_value="Dịch vụ tốt", injected_value="SĐT 0901234567 dịch vụ tốt",
                          description="Phone number in text field (PII leak)")
        self.injected.append(f)
        return f

    def inject_distribution_shift(self, table: str = "xanhsm_feedback") -> InjectedFault:
        f = InjectedFault(fault_family="distribution_shift", table=table, column="rating",
                          original_value="3.5", injected_value="1.0",
                          description="Batch of 1-star ratings (distribution anomaly)")
        self.injected.append(f)
        return f

    def inject_all(self) -> list[InjectedFault]:
        """Inject one fault from each family."""
        self.inject_type_error()
        self.inject_range_error()
        self.inject_referential_error()
        self.inject_temporal_error()
        self.inject_geographic_error()
        self.inject_financial_error()
        self.inject_business_error()
        self.inject_privacy_error()
        self.inject_distribution_shift()
        return self.injected

    def get_ground_truth(self) -> list[dict]:
        """Return ground truth labels for all injected faults."""
        return [
            {"fault_id": f.fault_id, "fault_family": f.fault_family, "table": f.table,
             "column": f.column, "description": f.description}
            for f in self.injected
        ]
