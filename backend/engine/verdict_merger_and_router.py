from typing import Dict, Any, List, Optional, Tuple
import hashlib
import json
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field

from backend.engine.hierarchical_policy_processor import LaneBVerdict, PolicyViolation
from backend.engine.jurisdiction_config import JurisdictionHierarchyConfig


@dataclass
class ConsolidatedRunResult:
    run_id: str
    dataset_id: str
    scanned_count: int = 0
    silver_count: int = 0
    quarantine_count: int = 0
    warning_count: int = 0
    silver_records: List[Dict[str, Any]] = field(default_factory=list)
    quarantine_records: List[Dict[str, Any]] = field(default_factory=list)
    warning_records: List[Dict[str, Any]] = field(default_factory=list)
    findings: List[Dict[str, Any]] = field(default_factory=list)


def _v_get(v: Any, key: str, default: Any = None) -> Any:
    """Safely get key or attribute from LaneBVerdict or dict."""
    if v is None:
        return default
    if isinstance(v, dict):
        return v.get(key, default)
    return getattr(v, key, default)


class VerdictMergerAndRouter:
    """
    Lane C Engine: Merges Lane A & Lane B Verdicts via A/B Combination Matrix
    and enforces strict precedence (FAIL > WARNING > PASS).
    Routes to Silver, Quarantine, or Warning with PII Storage Controls.
    """

    @staticmethod
    def extract_lane_a_violation_column_and_rule(
        res_a: Dict[str, Any], raw_item: Dict[str, Any]
    ) -> Tuple[str, str]:
        """
        Trích xuất chính xác tên cột và mã rule vi phạm từ Lane A,
        thay vì dùng nhãn kỹ thuật placeholder SENSOR_OR_LEDGER.
        """
        signals = res_a.get("signals", [])
        evidence_list = res_a.get("evidence", [])
        evidence_text = " ".join(evidence_list).lower()

        # 1. Trích xuất từ signals nếu có metric_or_relationship
        for s in signals:
            metric = None
            rule_id = "DATA_RELIABILITY_ANOMALY"
            if isinstance(s, dict):
                metric = s.get("metric_or_relationship")
                rule_id = s.get("rule_id") or rule_id
            elif hasattr(s, "metric_or_relationship"):
                metric = getattr(s, "metric_or_relationship")
                rule_id = getattr(s, "rule_id", rule_id)
            if metric and (not raw_item or metric in raw_item):
                return metric, rule_id

        # 2. Phân tích nội dung evidence_text
        if "fare_amount" in evidence_text:
            return "fare_amount", "L1_PHYSICAL_RANGE_FARE_AMOUNT"
        elif "total_fare" in evidence_text or "discrepancy_delta" in evidence_text or "computed_sum" in evidence_text:
            return "total_fare", "L1_LEDGER_ARITHMETIC_TOTAL_FARE"
        elif "battery_soc" in evidence_text:
            return "battery_soc", "L1_PHYSICAL_RANGE_BATTERY_SOC"
        elif "battery_temp" in evidence_text:
            return "battery_temp_c", "L1_PHYSICAL_RANGE_BATTERY_TEMP"
        elif "trip_distance" in evidence_text:
            return "trip_distance_km", "L1_PHYSICAL_RANGE_DISTANCE"
        elif "motor_rpm" in evidence_text or "speed_kmh" in evidence_text:
            return "motor_rpm", "L1_TELEMETRY_RPM_SPEED_CONDITION"
        elif "power_kw" in evidence_text:
            return "power_kw", "L1_PHYSICAL_RANGE_POWER"

        # 3. Quét các key trong raw_item
        for col_key in raw_item.keys():
            if col_key.lower() in evidence_text:
                return col_key, "DATA_RELIABILITY_ANOMALY"

        return "SENSOR_OR_LEDGER", "DATA_RELIABILITY_ANOMALY"

    @staticmethod
    def compute_lineage_hash(run_id: str, pk_val: str, payload: Dict[str, Any]) -> str:
        serialized = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(f"{run_id}:{pk_val}:{serialized}".encode("utf-8")).hexdigest()

    @staticmethod
    def redact_pii_for_warning(record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Controlled Storage: Redacts plain-text PII before persisting to warning.records.
        Preserves technical metrics, identifiers, and general context.
        """
        redacted = dict(record)
        # Redact phones
        for k in ["customer_phone", "phone_number", "customer_contact"]:
            if k in redacted and redacted[k]:
                s = str(redacted[k])
                redacted[k] = s[:3] + "*****" + s[-2:] if len(s) >= 5 else "*****"

        # Redact emails
        for k in ["customer_email", "email"]:
            if k in redacted and redacted[k]:
                redacted[k] = "r***@***.com"

        # Redact customer/driver names
        for k in ["customer_name", "first_name", "last_name"]:
            if k in redacted and redacted[k]:
                redacted[k] = "[REDACTED_NAME]"

        return redacted

    def merge_and_route(
        self,
        dataset_id: str,
        records: List[Dict[str, Any]],
        lane_a_results: Dict[str, Dict[str, Any]],
        lane_b_verdicts: List[LaneBVerdict],
        run_id: Optional[str] = None,
        pk_col: Optional[str] = None
    ) -> ConsolidatedRunResult:
        run_id = run_id or f"run_{uuid.uuid4().hex[:12]}"
        result = ConsolidatedRunResult(run_id=run_id, dataset_id=dataset_id)
        result.scanned_count = len(records)

        # Index Lane B by record_id (supporting dict-of-dicts, list-of-dicts, or list-of-dataclasses)
        if isinstance(lane_b_verdicts, dict):
            lane_b_map = lane_b_verdicts
        elif lane_b_verdicts and isinstance(lane_b_verdicts[0], dict):
            lane_b_map = {str(d.get("record_id")): d for d in lane_b_verdicts}
        else:
            lane_b_map = {str(getattr(v, "record_id")): v for v in (lane_b_verdicts or [])}


        for raw_item in records:
            # Resolve PK
            resolved_pk = pk_col
            if not resolved_pk:
                for cand in ["trip_id", "record_id", "session_id", "customer_id", "driver_id", "feedback_id", "vehicle_vin", "vin", "id"]:
                    if cand in raw_item:
                        resolved_pk = cand
                        break
            pk_val = str(raw_item.get(resolved_pk, "unknown"))
            eval_key = str(raw_item["_raw_id"]) if "_raw_id" in raw_item and raw_item["_raw_id"] else pk_val

            res_a = lane_a_results.get(eval_key) or lane_a_results.get(pk_val, {})
            status_a = res_a.get("status", "PASS")
            verdict_b = lane_b_map.get(eval_key) or lane_b_map.get(pk_val)
            status_b = _v_get(verdict_b, "status", "PASS")
            resolver = JurisdictionHierarchyConfig()
            v_chain = _v_get(verdict_b, "jurisdiction_chain")
            jurisdiction_chain = (
                list(v_chain)
                if v_chain
                else resolver.resolve_chain(
                    raw_item.get("subject_zone") or raw_item.get("zone"),
                    raw_item.get("country") or raw_item.get("subject_jurisdiction"),
                )
            )
            v_zone = _v_get(verdict_b, "normalized_zone")
            normalized_zone = (
                v_zone
                if (
                    v_zone
                    and not (
                        v_zone == "GLOBAL"
                        and len(jurisdiction_chain) > 1
                    )
                )
                else (jurisdiction_chain[1] if len(jurisdiction_chain) > 1 else "GLOBAL")
            )
            policy_violations = []
            if verdict_b:
                for violation in (_v_get(verdict_b, "violations") or []):
                    policy_violations.append(
                        violation.to_dict()
                        if hasattr(violation, "to_dict")
                        else dict(violation)
                    )

            primary_violation = policy_violations[0] if policy_violations else {}
            lane_a_col, lane_a_rule = self.extract_lane_a_violation_column_and_rule(res_a, raw_item)
            reliability_violation = {
                "rule_id": lane_a_rule,
                "column_name": lane_a_col,
                "reason": "; ".join(res_a.get("evidence", []))
                or "Violated L1 physical or ledger constraints",
                "severity": "CRITICAL",
                "jurisdiction": "GLOBAL",
                "policy_id": "POL-DATA-RELIABILITY",
                "policy_name": "Data Reliability Control",
                "law_ref": None,
            }
            applied_ids = list(_v_get(verdict_b, "applied_policy_ids") or [])
            jurisdiction_metadata = {
                "subject_zone": normalized_zone,
                "country": jurisdiction_chain[-1] if len(jurisdiction_chain) > 2 else None,
                "jurisdiction_chain": jurisdiction_chain,
                "applied_policy_ids": applied_ids,
                "policy_id": primary_violation.get("policy_id"),
                "policy_name": primary_violation.get("policy_name"),
                "law_ref": primary_violation.get("law_ref"),
                "matched_policy_id": primary_violation.get("policy_id"),
                "matched_policy_name": primary_violation.get("policy_name"),
                "matched_law_ref": primary_violation.get("law_ref"),
                "policy_snapshot": primary_violation or None,
                "policy_violations": policy_violations,
            }

            # =====================================================================
            # A/B COMBINATION MATRIX & PRECEDENCE (FAIL > WARNING > PASS)
            # =====================================================================
            if status_a == "FAIL" and status_b == "FAIL":
                # Quarantine + Compliance Finding
                result.quarantine_count += 1
                lineage = self.compute_lineage_hash(run_id, eval_key, raw_item)
                fail_reasons = (res_a.get("evidence", []) + list(_v_get(verdict_b, "failure_reasons") or []))
                quar_id = str(uuid.uuid5(uuid.NAMESPACE_OID, f"quarantine:{run_id}:{dataset_id}:{eval_key}"))
                fnd_id = f"FND-{hashlib.md5(f'{run_id}:{dataset_id}:{eval_key}'.encode('utf-8')).hexdigest()[:8]}"

                quar_rec = {
                    "quarantine_id": quar_id,
                    "run_id": run_id,
                    "dataset_id": dataset_id,
                    "source_table": f"bronze.{dataset_id}",
                    "source_row_pk": pk_val,
                    "failure_lane": "BOTH",
                    "violation_column": primary_violation.get("column_name", "MULTIPLE"),
                    "violation_rule_id": primary_violation.get("rule_id", "RELIABILITY_AND_POLICY_VIOLATION"),
                    "violation_reason": "; ".join(fail_reasons) or "Violated both Data Reliability & Compliance Policy",
                    "violation_severity": "CRITICAL",
                    "raw_record_json": raw_item,  # Full raw record
                    "lineage_hash": lineage,
                    "status": "QUARANTINED",
                    "quarantined_at": datetime.now(timezone.utc).isoformat(),
                    **{
                        **jurisdiction_metadata,
                        "applied_policy_ids": [
                            "POL-DATA-RELIABILITY",
                            *[item for item in jurisdiction_metadata["applied_policy_ids"] if item != "POL-DATA-RELIABILITY"],
                        ],
                        "policy_violations": [reliability_violation, *policy_violations],
                    },
                }
                result.quarantine_records.append(quar_rec)
                result.findings.append({
                    "finding_id": fnd_id,
                    "record_pk": pk_val,
                    "dataset_id": dataset_id,
                    "type": "COMPLIANCE_AND_RELIABILITY_BREACH",
                    "reasons": fail_reasons,
                    "subject_zone": normalized_zone,
                    "jurisdiction_chain": jurisdiction_chain,
                    "policy_violations": [reliability_violation, *policy_violations],
                })

            elif status_a == "FAIL" and status_b != "FAIL":
                # Quarantine (Data Reliability Defect)
                result.quarantine_count += 1
                lineage = self.compute_lineage_hash(run_id, eval_key, raw_item)
                fail_reasons = res_a.get("evidence", [])
                quar_id = str(uuid.uuid5(uuid.NAMESPACE_OID, f"quarantine:{run_id}:{dataset_id}:{eval_key}"))

                quar_rec = {
                    "quarantine_id": quar_id,
                    "run_id": run_id,
                    "dataset_id": dataset_id,
                    "source_table": f"bronze.{dataset_id}",
                    "source_row_pk": pk_val,
                    "failure_lane": "LANE_A",
                    "violation_column": lane_a_col,
                    "violation_rule_id": lane_a_rule,
                    "violation_reason": "; ".join(fail_reasons) or "Violated L1 physical or ledger constraints",
                    "violation_severity": "CRITICAL",
                    "raw_record_json": raw_item,
                    "lineage_hash": lineage,
                    "status": "QUARANTINED",
                    "quarantined_at": datetime.now(timezone.utc).isoformat(),
                    **{
                        **jurisdiction_metadata,
                        "policy_id": "POL-DATA-RELIABILITY",
                        "policy_name": "Data Reliability Control",
                        "law_ref": None,
                        "matched_policy_id": None,
                        "matched_policy_name": None,
                        "matched_law_ref": None,
                        "policy_snapshot": None,
                        "policy_violations": [reliability_violation],
                    },
                }
                result.quarantine_records.append(quar_rec)

            elif status_a != "FAIL" and status_b == "FAIL":
                # Policy Block (Quarantine)
                result.quarantine_count += 1
                lineage = self.compute_lineage_hash(run_id, eval_key, raw_item)
                b_fails = _v_get(verdict_b, "failure_reasons")
                fail_reasons = list(b_fails) if b_fails else ["Failed compliance check"]
                quar_id = str(uuid.uuid5(uuid.NAMESPACE_OID, f"quarantine:{run_id}:{dataset_id}:{eval_key}"))

                quar_rec = {
                    "quarantine_id": quar_id,
                    "run_id": run_id,
                    "dataset_id": dataset_id,
                    "source_table": f"bronze.{dataset_id}",
                    "source_row_pk": pk_val,
                    "failure_lane": "LANE_B",
                    "violation_column": primary_violation.get("column_name", "COMPLIANCE_GATE"),
                    "violation_rule_id": primary_violation.get("rule_id", "POLICY_BLOCK"),
                    "violation_reason": "; ".join(fail_reasons),
                    "violation_severity": "CRITICAL",
                    "raw_record_json": raw_item,
                    "lineage_hash": lineage,
                    "status": "QUARANTINED",
                    "quarantined_at": datetime.now(timezone.utc).isoformat(),
                    **jurisdiction_metadata,
                }
                result.quarantine_records.append(quar_rec)

            elif status_a == "WARNING" or status_b == "WARNING":
                # Warning Lane (Controlled PII Storage)
                result.warning_count += 1
                v_treated = _v_get(verdict_b, "treated_record")
                warning_source = (
                    v_treated
                    if v_treated is not None
                    else raw_item
                )
                redacted = self.redact_pii_for_warning(warning_source)
                lineage = self.compute_lineage_hash(run_id, eval_key, redacted)

                warn_signals = res_a.get("signals", [])
                first_sig = warn_signals[0] if warn_signals else None
                sig_layer = (first_sig.get("layer") if isinstance(first_sig, dict) else getattr(first_sig, "layer", "POLICY")) if first_sig else "POLICY"
                sig_type = (first_sig.get("signal_type") if isinstance(first_sig, dict) else getattr(first_sig, "signal_type", "ADVISORY_WARNING")) if first_sig else "ADVISORY_WARNING"
                score = (first_sig.get("score") if isinstance(first_sig, dict) else getattr(first_sig, "score", 1.0)) if first_sig else 1.0
                v_evidence = _v_get(verdict_b, "compliance_evidence") or []
                evidence_reasons = res_a.get("evidence", []) + list(v_evidence)
                warn_id = str(uuid.uuid5(uuid.NAMESPACE_OID, f"warning:{run_id}:{dataset_id}:{eval_key}"))

                warn_rec = {
                    "warning_id": warn_id,
                    "run_id": run_id,
                    "dataset_id": dataset_id,
                    "source_row_pk": pk_val,
                    "signal_lane": "LANE_A" if status_a == "WARNING" else "LANE_B",
                    "signal_layer": sig_layer,
                    "warning_type": sig_type,
                    "warning_reason": "; ".join(evidence_reasons) or "Statistical outlier or advisory rule warning",
                    "score_or_zvalue": score,
                    "evidence_json": {"evidence": evidence_reasons},
                    "redacted_record_json": redacted,  # Controlled PII snippet
                    "lineage_hash": lineage,
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                    "subject_zone": normalized_zone,
                    "jurisdiction_chain": jurisdiction_chain,
                    "applied_policy_ids": applied_ids,
                }
                result.warning_records.append(warn_rec)

            else:
                # Production Candidate (PASS -> Silver)
                result.silver_count += 1
                # Directly adopt treated_record from Lane B
                v_treated = _v_get(verdict_b, "treated_record")
                treated = dict(v_treated if v_treated is not None else raw_item)
                treated["_run_id"] = run_id
                treated["lineage_hash"] = self.compute_lineage_hash(run_id, eval_key, treated)
                result.silver_records.append(treated)

        routed_count = result.silver_count + result.quarantine_count + result.warning_count
        if routed_count != result.scanned_count:
            raise RuntimeError(
                "Batch reconciliation failed: "
                f"scanned={result.scanned_count}, routed={routed_count}"
            )
        return result
