from typing import Dict, Any, List, Optional
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


class VerdictMergerAndRouter:
    """
    Lane C Engine: Merges Lane A & Lane B Verdicts via A/B Combination Matrix
    and enforces strict precedence (FAIL > WARNING > PASS).
    Routes to Silver, Quarantine, or Warning with PII Storage Controls.
    """

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

        # Index Lane B by record_id
        lane_b_map: Dict[str, LaneBVerdict] = {v.record_id: v for v in lane_b_verdicts}

        for raw_item in records:
            # Resolve PK
            resolved_pk = pk_col
            if not resolved_pk:
                for cand in ["trip_id", "record_id", "session_id", "customer_id", "driver_id", "feedback_id", "vehicle_vin", "vin", "id"]:
                    if cand in raw_item:
                        resolved_pk = cand
                        break
            pk_val = str(raw_item.get(resolved_pk, "unknown"))

            res_a = lane_a_results.get(pk_val, {})
            status_a = res_a.get("status", "PASS")
            verdict_b = lane_b_map.get(pk_val)
            status_b = verdict_b.status if verdict_b else "PASS"
            resolver = JurisdictionHierarchyConfig()
            jurisdiction_chain = (
                list(verdict_b.jurisdiction_chain)
                if verdict_b and verdict_b.jurisdiction_chain
                else resolver.resolve_chain(
                    raw_item.get("subject_zone") or raw_item.get("zone"),
                    raw_item.get("country") or raw_item.get("subject_jurisdiction"),
                )
            )
            normalized_zone = (
                verdict_b.normalized_zone
                if (
                    verdict_b
                    and verdict_b.normalized_zone
                    and not (
                        verdict_b.normalized_zone == "GLOBAL"
                        and len(jurisdiction_chain) > 1
                    )
                )
                else (jurisdiction_chain[1] if len(jurisdiction_chain) > 1 else "GLOBAL")
            )
            policy_violations = []
            if verdict_b:
                for violation in verdict_b.violations:
                    policy_violations.append(
                        violation.to_dict()
                        if isinstance(violation, PolicyViolation)
                        else dict(violation)
                    )

            primary_violation = policy_violations[0] if policy_violations else {}
            reliability_violation = {
                "rule_id": "DATA_RELIABILITY_ANOMALY",
                "column_name": "SENSOR_OR_LEDGER",
                "reason": "; ".join(res_a.get("evidence", []))
                or "Violated L1 physical or ledger constraints",
                "severity": "CRITICAL",
                "jurisdiction": "GLOBAL",
                "policy_id": "POL-DATA-RELIABILITY",
                "policy_name": "Data Reliability Control",
                "law_ref": None,
            }
            jurisdiction_metadata = {
                "subject_zone": normalized_zone,
                "country": jurisdiction_chain[-1] if len(jurisdiction_chain) > 2 else None,
                "jurisdiction_chain": jurisdiction_chain,
                "applied_policy_ids": list(verdict_b.applied_policy_ids) if verdict_b else [],
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
                lineage = self.compute_lineage_hash(run_id, pk_val, raw_item)
                fail_reasons = (res_a.get("evidence", []) + (verdict_b.failure_reasons if verdict_b else []))
                
                quar_rec = {
                    "quarantine_id": str(uuid.uuid4()),
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
                    "finding_id": f"FND-{uuid.uuid4().hex[:8]}",
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
                lineage = self.compute_lineage_hash(run_id, pk_val, raw_item)
                fail_reasons = res_a.get("evidence", [])

                quar_rec = {
                    "quarantine_id": str(uuid.uuid4()),
                    "run_id": run_id,
                    "dataset_id": dataset_id,
                    "source_table": f"bronze.{dataset_id}",
                    "source_row_pk": pk_val,
                    "failure_lane": "LANE_A",
                    "violation_column": "SENSOR_OR_LEDGER",
                    "violation_rule_id": "DATA_RELIABILITY_ANOMALY",
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
                lineage = self.compute_lineage_hash(run_id, pk_val, raw_item)
                fail_reasons = verdict_b.failure_reasons if verdict_b else ["Failed compliance check"]

                quar_rec = {
                    "quarantine_id": str(uuid.uuid4()),
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
                redacted = self.redact_pii_for_warning(raw_item)
                lineage = self.compute_lineage_hash(run_id, pk_val, redacted)

                warn_signals = res_a.get("signals", [])
                first_sig = warn_signals[0] if warn_signals else None
                sig_layer = (first_sig.get("layer") if isinstance(first_sig, dict) else getattr(first_sig, "layer", "POLICY")) if first_sig else "POLICY"
                sig_type = (first_sig.get("signal_type") if isinstance(first_sig, dict) else getattr(first_sig, "signal_type", "ADVISORY_WARNING")) if first_sig else "ADVISORY_WARNING"
                score = (first_sig.get("score") if isinstance(first_sig, dict) else getattr(first_sig, "score", 1.0)) if first_sig else 1.0
                evidence_reasons = res_a.get("evidence", []) + (verdict_b.compliance_evidence if verdict_b else [])

                warn_rec = {
                    "warning_id": str(uuid.uuid4()),
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
                    "applied_policy_ids": list(verdict_b.applied_policy_ids) if verdict_b else [],
                }
                result.warning_records.append(warn_rec)

            else:
                # Production Candidate (PASS -> Silver)
                result.silver_count += 1
                # Directly adopt treated_record from Lane B
                treated = dict(verdict_b.treated_record if (verdict_b and verdict_b.treated_record) else raw_item)
                treated["_run_id"] = run_id
                treated["lineage_hash"] = self.compute_lineage_hash(run_id, pk_val, treated)
                result.silver_records.append(treated)

        return result
