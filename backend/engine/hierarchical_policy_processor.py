from typing import Dict, Any, List, Optional
import os
import re
from dataclasses import dataclass, field

from backend.engine.jurisdiction_config import JurisdictionHierarchyConfig
from backend.engine.operation_registry import OperationRegistry


@dataclass
class LaneBVerdict:
    record_id: str
    status: str  # "PASS", "FAIL", "WARNING"
    treated_record: Optional[Dict[str, Any]]
    raw_record: Dict[str, Any]
    compliance_evidence: List[str] = field(default_factory=list)
    required_treatments: List[Dict[str, Any]] = field(default_factory=list)
    failure_reasons: List[str] = field(default_factory=list)
    jurisdiction_chain: List[str] = field(default_factory=list)


class HierarchicalPolicyProcessor:
    """
    Lane B Engine: Hierarchical Policy Processing & Compliance Evaluation.
    7-Step Lifecycle:
    1. Resolve Zone/Country
    2. Select Policies (IFRS 15, GDPR, CCPA, Luật 91/2025/QH15 & NĐ 356/2025/NĐ-CP)
    3. Pre-check (Pre-processing rules)
    4. Determine Treatment (Declarative required_treatments)
    5. Generic Processing (Execute through OperationRegistry)
    6. Post-check (Post-processing rules on treated_record)
    7. Lane B Verdict
    """

    def __init__(
        self,
        hierarchy_config: Optional[JurisdictionHierarchyConfig] = None,
        active_treatments: Optional[List[Dict[str, Any]]] = None
    ):
        self.hierarchy_config = hierarchy_config or JurisdictionHierarchyConfig()
        self.active_treatments = active_treatments or []

    def process_records(
        self,
        dataset_id: str,
        records: List[Dict[str, Any]],
        pk_col: Optional[str] = None
    ) -> List[LaneBVerdict]:
        """
        Executes Lane B for a batch of records.
        """
        verdicts: List[LaneBVerdict] = []
        for raw_item in records:
            verdict = self.process_single_record(dataset_id, raw_item, pk_col)
            verdicts.append(verdict)
        return verdicts

    def process_single_record(
        self,
        dataset_id: str,
        raw_record: Dict[str, Any],
        pk_col: Optional[str] = None
    ) -> LaneBVerdict:
        raw_item = dict(raw_record)

        # Determine PK
        resolved_pk = pk_col
        if not resolved_pk:
            for cand in ["trip_id", "record_id", "session_id", "customer_id", "driver_id", "feedback_id", "id"]:
                if cand in raw_item:
                    resolved_pk = cand
                    break
        pk_val = str(raw_item.get(resolved_pk, "unknown"))

        # Step 1: Resolve Zone/Country Hierarchy
        zone = raw_item.get("subject_zone") or raw_item.get("zone")
        country = raw_item.get("country") or raw_item.get("subject_jurisdiction")
        jurisdiction_chain = self.hierarchy_config.resolve_chain(zone, country)

        evidence: List[str] = [f"Jurisdiction chain resolved: {' -> '.join(jurisdiction_chain)}"]
        failure_reasons: List[str] = []
        is_fail = False
        is_warning = False

        # Step 2 & 3: Pre-check (Pre-processing rules evaluated on raw data)
        # 3.1 Geographical licensing boundary check for Trips
        if "trips" in dataset_id or "pickup_latitude" in raw_item:
            lat = self._safe_float(raw_item.get("pickup_latitude"))
            lon = self._safe_float(raw_item.get("pickup_longitude"))

            if "VN" in jurisdiction_chain:
                # Vietnam territorial operating jurisdiction: lat [8.0, 24.0]
                if lat is not None and not (8.0 <= lat <= 24.0):
                    is_fail = True
                    reason = f"Pre-check failed: Tọa độ điểm đón ({lat}) nằm ngoài lãnh thổ cấp phép VN (Luật 91/2025/QH15 & NĐ 356/2025)"
                    failure_reasons.append(reason)
                    evidence.append(reason)
            elif "EU" in jurisdiction_chain:
                # EU Berlin pilot operating jurisdiction: lat [52.0, 53.0]
                if lat is not None and not (52.0 <= lat <= 53.5):
                    is_fail = True
                    reason = f"Pre-check failed: Tọa độ ({lat}) nằm ngoài phạm vi cấp phép đội xe Berlin EU (GDPR Art. 5)"
                    failure_reasons.append(reason)
                    evidence.append(reason)

        # 3.2 Currency unverified flag check (soft advisory warning)
        if raw_item.get("currency_unverified") in [True, "true", "TRUE", 1, "1"]:
            is_warning = True
            evidence.append("Pre-check warning: Đơn vị tiền tệ chưa xác thực đối soát liên ngân hàng")

        # Step 4: Determine Treatment (Declarative Specification from DB / Policy)
        required_treatments: List[Dict[str, Any]] = []

        # If custom active treatments configured from DB/policy, incorporate them
        for trt in self.active_treatments:
            col = trt.get("column")
            if col in raw_item and raw_item[col] is not None:
                required_treatments.append(trt)

        configured_cols = {t.get("column") for t in required_treatments}

        # Customer Phone -> MASK
        for phone_key in ["customer_phone", "phone_number", "customer_contact"]:
            if phone_key in raw_item and raw_item[phone_key] and phone_key not in configured_cols:
                required_treatments.append({
                    "column": phone_key,
                    "operation_id": "MASK",
                    "params": {"prefix_len": 3, "suffix_len": 2},
                    "law_ref": "Luật 91/2025/QH15 Điều 9 & NĐ 356/2025 Điều 17"
                })

        # Customer Email -> MASK
        for email_key in ["customer_email", "email"]:
            if email_key in raw_item and raw_item[email_key] and email_key not in configured_cols:
                required_treatments.append({
                    "column": email_key,
                    "operation_id": "MASK",
                    "params": {"prefix_len": 2, "suffix_len": 4},
                    "law_ref": "Luật 91/2025/QH15 & GDPR Art. 5"
                })

        # Driver ID -> HASH
        if "driver_id" in raw_item and raw_item["driver_id"] and "driver_id" not in configured_cols:
            required_treatments.append({
                "column": "driver_id",
                "operation_id": "HASH",
                "params": {"algorithm": "sha256", "salt_ref": "gsm_driver_salt_2026"},
                "law_ref": "GDPR Art. 5(1)(c) & NĐ 356/2025 Điều 4"
            })

        # GPS Coordinates -> ROUND (2 decimals)
        for lat_key in ["pickup_latitude", "latitude"]:
            if lat_key in raw_item and raw_item[lat_key] is not None and lat_key not in configured_cols:
                required_treatments.append({
                    "column": lat_key,
                    "operation_id": "ROUND",
                    "params": {"decimals": 2},
                    "law_ref": "GDPR Art. 25 & CCPA § 1798.121"
                })
        for lon_key in ["pickup_longitude", "longitude"]:
            if lon_key in raw_item and raw_item[lon_key] is not None and lon_key not in configured_cols:
                required_treatments.append({
                    "column": lon_key,
                    "operation_id": "ROUND",
                    "params": {"decimals": 2},
                    "law_ref": "GDPR Art. 25 & CCPA § 1798.121"
                })

        # Step 5: Generic Processing via OperationRegistry
        treated_item = dict(raw_item)
        if not is_fail:
            for trt in required_treatments:
                col = trt["column"]
                op_id = trt["operation_id"]
                pms = trt.get("params", {})
                if col in treated_item:
                    orig_val = treated_item[col]
                    new_val = OperationRegistry.execute(op_id, orig_val, pms)
                    treated_item[col] = new_val

        # Step 6: Post-check (Post-processing rules evaluated on treated_record)
        if not is_fail:
            # 6.1 IFRS 15 / SOX 404: Commercial Revenue Recognition
            if "fare_amount" in treated_item:
                fare = self._safe_float(treated_item.get("fare_amount"))
                dist = self._safe_float(treated_item.get("trip_distance_km"))
                if fare is not None and fare <= 0.0:
                    is_fail = True
                    reason = f"Post-check failed: Cước chuyến đi ({fare}) <= 0 vi phạm chuẩn IFRS 15 / SOX 404"
                    failure_reasons.append(reason)
                    evidence.append(reason)
                elif dist is not None and dist < 0.1:
                    is_fail = True
                    reason = f"Post-check failed: Cự ly ({dist} km) < 0.1km vi phạm chuẩn ghi nhận cuốc xe IFRS 15"
                    failure_reasons.append(reason)
                    evidence.append(reason)

            # 6.2 Commercial EV Battery Safety Window
            if "battery_temp_c" in treated_item:
                temp = self._safe_float(treated_item.get("battery_temp_c"))
                if temp is not None and temp > 65.0:
                    is_fail = True
                    reason = f"Post-check failed: Nhiệt độ pack pin ({temp}°C) vượt ngưỡng an toàn vận hành thương mại 65°C IEC 62660-1"
                    failure_reasons.append(reason)
                    evidence.append(reason)

            # 6.3 Charging Meter Discrepancy
            if "meter_kwh_delta" in treated_item and "bms_kwh_delta" in treated_item:
                meter = self._safe_float(treated_item.get("meter_kwh_delta"))
                bms = self._safe_float(treated_item.get("bms_kwh_delta"))
                if meter is not None and bms is not None and meter > 0:
                    if abs(meter - bms) > 0.03 * meter:
                        is_fail = True
                        reason = f"Post-check failed: Sai lệch công tơ trụ sạc ({abs(meter-bms):.2f} kWh) vượt 3% chuẩn thương mại V-GREEN"
                        failure_reasons.append(reason)
                        evidence.append(reason)

            # 6.4 Verification of Successful Treatment (PII is sanitized)
            for phone_key in ["customer_phone", "customer_contact"]:
                if phone_key in treated_item and treated_item[phone_key]:
                    val_str = str(treated_item[phone_key])
                    # Ensure phone number was masked with '*'
                    if "*" not in val_str and len(val_str) >= 6:
                        is_fail = True
                        reason = f"Post-check failed: Số điện thoại chưa được che mờ hợp lệ theo Luật 91/2025/QH15"
                        failure_reasons.append(reason)
                        evidence.append(reason)

        # Step 7: Lane B Verdict
        if is_fail:
            status = "FAIL"
        elif is_warning:
            status = "WARNING"
        else:
            status = "PASS"

        return LaneBVerdict(
            record_id=pk_val,
            status=status,
            treated_record=treated_item if status == "PASS" else None,
            raw_record=raw_item,
            compliance_evidence=evidence,
            required_treatments=required_treatments,
            failure_reasons=failure_reasons,
            jurisdiction_chain=jurisdiction_chain
        )

    def _safe_float(self, val: Any) -> Optional[float]:
        if val is None or val == "":
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None
