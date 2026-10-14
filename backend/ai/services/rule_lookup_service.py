"""
DataTrust OS: Centralized Rule Lookup Service
Unified rule lookup service across 3 rule families:
1. Compliance Rules (policy.compliance_rules - Lane B)
2. Data Treatment Rules (policy.data_treatment_rules)
3. Reliability Rules (engine.reliability_rules - Lane A)

Features:
- Telemetry-backed Run Execution Inspection (audit.record_policy_executions)
- Partitioning into 3 groups: evaluated_rules, triggered_rules, execution_unknown
- Hierarchical jurisdiction_chain resolution with local overrides over GLOBAL
- Strict versioning and temporal snapshot matching (effective_from <= as_of < effective_to)
- Categorical status: FOUND_ONE, FOUND_MANY, NOT_FOUND, INSUFFICIENT_SCOPE, DB_ERROR
- Zero hallucination on law_ref (never fabricates decrees or laws)
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple

from database.profiler_engine import get_db_connection
from psycopg2.extras import RealDictCursor

logger = logging.getLogger("DataTrust.RuleLookupService")


class RuleLookupStatus(str, Enum):
    FOUND_ONE = "FOUND_ONE"
    FOUND_MANY = "FOUND_MANY"
    NOT_FOUND = "NOT_FOUND"
    INSUFFICIENT_SCOPE = "INSUFFICIENT_SCOPE"
    DB_ERROR = "DB_ERROR"


class RuleFamily(str, Enum):
    COMPLIANCE = "COMPLIANCE"
    TREATMENT = "TREATMENT"
    RELIABILITY = "RELIABILITY"


@dataclass
class RuleLookupResult:
    status: RuleLookupStatus
    query: str
    family: Optional[RuleFamily] = None
    rule: Optional[Dict[str, Any]] = None
    rules: List[Dict[str, Any]] = field(default_factory=list)
    evaluated_rules: List[Dict[str, Any]] = field(default_factory=list)
    triggered_rules: List[Dict[str, Any]] = field(default_factory=list)
    execution_unknown: bool = False
    error_message: Optional[str] = None
    scope: Dict[str, Any] = field(default_factory=dict)


class RuleLookupService:
    """Centralized service for discovering, querying, and auditing rules."""

    @classmethod
    def resolve_jurisdiction_chain(
        cls,
        jurisdiction: Optional[str] = None,
        country: Optional[str] = None
    ) -> List[str]:
        """Resolves hierarchy chain: ['GLOBAL', '<ZONE>', '<COUNTRY>']."""
        chain = ["GLOBAL"]
        if jurisdiction and jurisdiction.strip().upper() not in chain and jurisdiction.strip().upper() != "UNSCOPED":
            chain.append(jurisdiction.strip().upper())
        if country and country.strip().upper() not in chain:
            chain.append(country.strip().upper())
        return chain

    @classmethod
    def get_executed_rules_for_run(cls, run_id: str) -> RuleLookupResult:
        """
        Retrieves rules executed during a pipeline run based on execution telemetry:
        - Primary source: audit.record_policy_executions (PASS, FAIL, SKIP)
        - Supplementary source: audit.findings, quarantine.records, warning.records
        - Tri-partition: evaluated_rules, triggered_rules, execution_unknown
        - Prioritizes rule_snapshot from ledger for exact versioned law_ref and expression.
        """
        if not run_id:
            return RuleLookupResult(
                status=RuleLookupStatus.INSUFFICIENT_SCOPE,
                query="",
                error_message="Cần cung cấp run_id để tra cứu các quy tắc đã thực thi.",
                scope={"run_id": None}
            )

        try:
            conn = get_db_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 1. Primary telemetry: audit.record_policy_executions
                cur.execute(
                    """
                    SELECT 
                        rule_id, 
                        rule_version, 
                        execution_type, 
                        phase,
                        rule_snapshot,
                        COUNT(*) as total_evaluations,
                        COUNT(*) FILTER (WHERE result = 'PASS') as pass_count,
                        COUNT(*) FILTER (WHERE result = 'FAIL') as fail_count,
                        COUNT(*) FILTER (WHERE result = 'SKIP') as skip_count
                    FROM audit.record_policy_executions
                    WHERE run_id = %s
                    GROUP BY rule_id, rule_version, execution_type, phase, rule_snapshot
                    ORDER BY rule_id, rule_version;
                    """,
                    (run_id,)
                )
                exec_rows = [dict(r) for r in cur.fetchall()]

                # 2. Supplementary telemetry: audit.findings
                cur.execute(
                    """
                    SELECT DISTINCT rule_id, column_name, dataset_id, severity, reason, law_ref, failed_record_count
                    FROM audit.findings
                    WHERE run_id = %s;
                    """,
                    (run_id,)
                )
                finding_rows = [dict(r) for r in cur.fetchall()]
                findings_by_rule = {f["rule_id"]: f for f in finding_rows if f.get("rule_id")}

                # 3. Supplementary telemetry: quarantine.records
                cur.execute(
                    """
                    SELECT violation_rule_id, COUNT(*) as quarantine_count, array_agg(DISTINCT violation_column) as columns
                    FROM quarantine.records
                    WHERE run_id = %s
                    GROUP BY violation_rule_id;
                    """,
                    (run_id,)
                )
                quarantine_rows = [dict(r) for r in cur.fetchall()]
                quarantine_by_rule = {q["violation_rule_id"]: q for q in quarantine_rows if q.get("violation_rule_id")}

                # 4. Supplementary telemetry: warning changepoints / signals
                cur.execute(
                    """
                    SELECT 
                        COALESCE(evidence_json->>'rule_id', warning_type) as signal_rule_id,
                        signal_lane, 
                        signal_layer, 
                        warning_type, 
                        COUNT(*) as warn_count
                    FROM warning.records
                    WHERE run_id = %s
                    GROUP BY 1, 2, 3, 4;
                    """,
                    (run_id,)
                )
                warn_rows = [dict(r) for r in cur.fetchall()]
                warn_by_rule = {w["signal_rule_id"]: w for w in warn_rows if w.get("signal_rule_id")}

            conn.close()

            # Partition logic
            evaluated_rules: List[Dict[str, Any]] = []
            triggered_rules: List[Dict[str, Any]] = []
            execution_unknown = False

            if not exec_rows:
                # If ledger has no records for this run, mark execution_unknown = True
                execution_unknown = True

                # Fallback to findings/warnings if any exist, but clearly mark telemetry limitation
                for r_id, f in findings_by_rule.items():
                    trig_entry = {
                        "rule_id": r_id,
                        "rule_version": None,
                        "source": "FINDING_INFERRED",
                        "severity": f.get("severity", "HIGH"),
                        "column_name": f.get("column_name"),
                        "law_ref": f.get("law_ref"),
                        "reason": f.get("reason"),
                        "failed_record_count": f.get("failed_record_count", 0),
                        "quarantine_count": quarantine_by_rule.get(r_id, {}).get("quarantine_count", 0)
                    }
                    triggered_rules.append(trig_entry)
                    evaluated_rules.append(trig_entry)

                for r_id, w in warn_by_rule.items():
                    if r_id not in findings_by_rule:
                        w_entry = {
                            "rule_id": r_id,
                            "rule_version": None,
                            "source": "WARNING_INFERRED",
                            "severity": "WARNING",
                            "signal_lane": w.get("signal_lane", "LANE_A"),
                            "warning_type": w.get("warning_type"),
                            "warning_count": w.get("warn_count", 0)
                        }
                        triggered_rules.append(w_entry)
                        evaluated_rules.append(w_entry)
            else:
                for row in exec_rows:
                    r_id = row["rule_id"]
                    r_ver = row["rule_version"]
                    snap = row.get("rule_snapshot") or {}
                    if isinstance(snap, str):
                        try:
                            snap = json.loads(snap)
                        except Exception:
                            snap = {}

                    eval_entry = {
                        "rule_id": r_id,
                        "rule_version": r_ver,
                        "rule_name": snap.get("rule_name") or r_id,
                        "expression": snap.get("expression") or snap.get("condition_expression"),
                        "law_ref": snap.get("law_ref"),
                        "execution_type": row.get("execution_type"),
                        "phase": row.get("phase"),
                        "total_evaluations": row.get("total_evaluations", 0),
                        "pass_count": row.get("pass_count", 0),
                        "fail_count": row.get("fail_count", 0),
                        "skip_count": row.get("skip_count", 0),
                        "rule_snapshot": snap
                    }
                    evaluated_rules.append(eval_entry)

                    # Triggered if fail_count > 0 or linked finding/quarantine exists
                    is_triggered = (
                        eval_entry["fail_count"] > 0
                        or r_id in findings_by_rule
                        or r_id in quarantine_by_rule
                        or r_id in warn_by_rule
                    )
                    if is_triggered:
                        trig_copy = dict(eval_entry)
                        trig_copy["finding"] = findings_by_rule.get(r_id)
                        trig_copy["quarantine_count"] = quarantine_by_rule.get(r_id, {}).get("quarantine_count", 0)
                        trig_copy["warning_info"] = warn_by_rule.get(r_id)
                        triggered_rules.append(trig_copy)

            status = RuleLookupStatus.FOUND_MANY if evaluated_rules else RuleLookupStatus.NOT_FOUND

            return RuleLookupResult(
                status=status,
                query=run_id,
                rules=evaluated_rules,
                evaluated_rules=evaluated_rules,
                triggered_rules=triggered_rules,
                execution_unknown=execution_unknown,
                scope={"run_id": run_id, "telemetry_records_count": len(exec_rows)}
            )

        except Exception as e:
            logger.error(f"Error in get_executed_rules_for_run({run_id}): {e}", exc_info=True)
            return RuleLookupResult(
                status=RuleLookupStatus.DB_ERROR,
                query=run_id,
                error_message=f"Lỗi truy vấn cơ sở dữ liệu khi tra cứu quy tắc thực thi: {str(e)}",
                scope={"run_id": run_id}
            )

    @classmethod
    def get_configured_rules_for_dataset(
        cls,
        dataset_id: str,
        jurisdiction: Optional[str] = None,
        country: Optional[str] = None,
        as_of: Optional[datetime] = None,
        status: str = "ACTIVE"
    ) -> RuleLookupResult:
        """
        Retrieves active configured rules for a dataset:
        - Resolves jurisdiction_chain: local overrides GLOBAL on same rule/target.
        - Respects temporal version window (effective_from <= as_of < effective_to).
        - Includes Compliance rules, Treatment rules, and Reliability rules.
        """
        if not dataset_id:
            return RuleLookupResult(
                status=RuleLookupStatus.INSUFFICIENT_SCOPE,
                query="",
                error_message="Cần cung cấp dataset_id để tra cứu cấu hình quy tắc.",
                scope={"dataset_id": None}
            )

        clean_ds = dataset_id.replace(".csv", "").replace("bronze.", "").strip()
        chain = cls.resolve_jurisdiction_chain(jurisdiction, country)
        as_of_ts = as_of or datetime.now(timezone.utc)

        try:
            conn = get_db_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 1. Compliance Rules (Lane B)
                cur.execute(
                    """
                    SELECT 
                        rule_id, version, dataset_id, column_name, rule_name, rule_code,
                        expression, description, policy_id, policy_name, law_ref,
                        jurisdiction, country, rule_domain, severity, on_fail_action,
                        status, condition_json, effective_from, effective_to, runtime_mode
                    FROM policy.compliance_rules
                    WHERE (dataset_id = %s OR dataset_id = %s OR dataset_id = %s)
                      AND status = %s
                      AND effective_from <= %s
                      AND (effective_to IS NULL OR effective_to > %s)
                      AND jurisdiction = ANY(%s)
                    ORDER BY dataset_id, rule_id, version DESC;
                    """,
                    (clean_ds, f"{clean_ds}.csv", f"bronze.{clean_ds}", status.upper(), as_of_ts, as_of_ts, chain)
                )
                comp_rows = [dict(r) for r in cur.fetchall()]

                # 2. Treatment Rules
                cur.execute(
                    """
                    SELECT 
                        rule_id, dataset_id, column_name, operation_id, treatment_name,
                        params_json, expression_display, description, law_ref,
                        jurisdiction, country, status, is_ai_proposed
                    FROM policy.data_treatment_rules
                    WHERE (dataset_id = %s OR dataset_id = %s OR dataset_id = %s)
                      AND status ILIKE %s
                      AND jurisdiction = ANY(%s)
                    ORDER BY rule_id;
                    """,
                    (clean_ds, f"{clean_ds}.csv", f"bronze.{clean_ds}", status, chain)
                )
                treat_rows = [dict(r) for r in cur.fetchall()]

                # 3. Reliability Rules (Lane A)
                cur.execute(
                    """
                    SELECT 
                        rule_id, version, dataset_id, layer, detector_id, target_fields,
                        params_json, severity, on_fail_action, status, runtime_mode, description
                    FROM engine.reliability_rules
                    WHERE (dataset_id = %s OR dataset_id = %s OR dataset_id = %s)
                      AND status = %s
                    ORDER BY layer, rule_id;
                    """,
                    (clean_ds, f"{clean_ds}.csv", f"bronze.{clean_ds}", status.upper())
                )
                rel_rows = [dict(r) for r in cur.fetchall()]

            conn.close()

            # Deduplication & Specificity Overrides for Compliance Rules:
            # Rule with higher index in chain overrides rule with lower index (e.g. VN index 1 overrides GLOBAL index 0)
            selected_compliance: Dict[str, Dict[str, Any]] = {}
            for r in comp_rows:
                r_id = r["rule_id"]
                rule_jur = (r.get("jurisdiction") or "GLOBAL").strip().upper()
                specificity = chain.index(rule_jur) if rule_jur in chain else -1

                if r_id not in selected_compliance:
                    r["_specificity"] = specificity
                    r["family"] = RuleFamily.COMPLIANCE.value
                    selected_compliance[r_id] = r
                else:
                    if specificity > selected_compliance[r_id]["_specificity"]:
                        r["_specificity"] = specificity
                        r["family"] = RuleFamily.COMPLIANCE.value
                        selected_compliance[r_id] = r

            compliance_list = list(selected_compliance.values())
            for t in treat_rows:
                t["family"] = RuleFamily.TREATMENT.value
            for rl in rel_rows:
                rl["family"] = RuleFamily.RELIABILITY.value

            all_rules = compliance_list + treat_rows + rel_rows
            lookup_status = RuleLookupStatus.FOUND_MANY if all_rules else RuleLookupStatus.NOT_FOUND

            return RuleLookupResult(
                status=lookup_status,
                query=dataset_id,
                rules=all_rules,
                scope={
                    "dataset_id": clean_ds,
                    "jurisdiction_chain": chain,
                    "as_of": as_of_ts.isoformat(),
                    "compliance_count": len(compliance_list),
                    "treatment_count": len(treat_rows),
                    "reliability_count": len(rel_rows)
                }
            )

        except Exception as e:
            logger.error(f"Error in get_configured_rules_for_dataset({dataset_id}): {e}", exc_info=True)
            return RuleLookupResult(
                status=RuleLookupStatus.DB_ERROR,
                query=dataset_id,
                error_message=f"Lỗi truy vấn cơ sở dữ liệu khi tra cứu cấu hình quy tắc dataset: {str(e)}",
                scope={"dataset_id": dataset_id}
            )

    @classmethod
    def lookup_by_identifier(
        cls,
        query: str,
        dataset_id: Optional[str] = None,
        jurisdiction: Optional[str] = None,
        as_of: Optional[datetime] = None
    ) -> RuleLookupResult:
        """
        Searches across all 3 rule families by rule_id, rule_code, operation_id, or treatment_name:
        - Exact identifier lookup
        - Returns FOUND_ONE if unique, FOUND_MANY if multiple matches (e.g. mask_phone across datasets),
          NOT_FOUND if absent, or DB_ERROR if connection fails.
        - Preserves strict law_ref authenticity: Never fabricates missing laws.
        """
        raw_q = query.strip()
        if not raw_q:
            return RuleLookupResult(
                status=RuleLookupStatus.INSUFFICIENT_SCOPE,
                query=query,
                error_message="Vui lòng cung cấp mã hoặc tên quy tắc cần tra cứu.",
                scope={}
            )

        # Normalize clean search tokens
        # e.g. "rule L1-01" -> "L1-01", "mask_phone" -> "mask_phone"
        clean_target = re.sub(r"^(rule|quy\s+tắc|tra\s+cứu|xem)\s+", "", raw_q, flags=re.IGNORECASE).strip()
        chain = cls.resolve_jurisdiction_chain(jurisdiction)
        as_of_ts = as_of or datetime.now(timezone.utc)

        try:
            conn = get_db_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 1. Search policy.compliance_rules
                comp_query = """
                    SELECT 
                        rule_id, version, dataset_id, column_name, rule_name, rule_code,
                        expression, description, policy_id, policy_name, law_ref,
                        jurisdiction, country, rule_domain, severity, on_fail_action,
                        status, condition_json, effective_from, effective_to, runtime_mode
                    FROM policy.compliance_rules
                    WHERE (rule_id ILIKE %s OR rule_code ILIKE %s OR rule_name ILIKE %s)
                      AND effective_from <= %s
                      AND (effective_to IS NULL OR effective_to > %s)
                """
                comp_params: List[Any] = [clean_target, clean_target, f"%{clean_target}%", as_of_ts, as_of_ts]
                if dataset_id:
                    comp_query += " AND (dataset_id = %s OR dataset_id = %s)"
                    comp_params.extend([dataset_id, f"bronze.{dataset_id}"])
                comp_query += " ORDER BY version DESC LIMIT 10;"
                cur.execute(comp_query, tuple(comp_params))
                found_compliance = [dict(r) for r in cur.fetchall()]

                # 2. Search policy.data_treatment_rules
                treat_query = """
                    SELECT 
                        rule_id, dataset_id, column_name, operation_id, treatment_name,
                        params_json, expression_display, description, law_ref,
                        jurisdiction, country, status, is_ai_proposed
                    FROM policy.data_treatment_rules
                    WHERE (rule_id ILIKE %s OR operation_id ILIKE %s OR treatment_name ILIKE %s)
                """
                treat_params: List[Any] = [clean_target, clean_target, f"%{clean_target}%"]
                if dataset_id:
                    treat_query += " AND (dataset_id = %s OR dataset_id = %s)"
                    treat_params.extend([dataset_id, f"bronze.{dataset_id}"])
                treat_query += " LIMIT 10;"
                cur.execute(treat_query, tuple(treat_params))
                found_treatment = [dict(r) for r in cur.fetchall()]

                # 3. Search engine.reliability_rules
                rel_query = """
                    SELECT 
                        rule_id, version, dataset_id, layer, detector_id, target_fields,
                        params_json, severity, on_fail_action, status, runtime_mode, description
                    FROM engine.reliability_rules
                    WHERE (rule_id ILIKE %s OR detector_id ILIKE %s OR description ILIKE %s)
                """
                rel_params: List[Any] = [clean_target, clean_target, f"%{clean_target}%"]
                if dataset_id:
                    rel_query += " AND (dataset_id = %s OR dataset_id = %s)"
                    rel_params.extend([dataset_id, f"bronze.{dataset_id}"])
                rel_query += " LIMIT 10;"
                cur.execute(rel_query, tuple(rel_params))
                found_reliability = [dict(r) for r in cur.fetchall()]

            conn.close()

            for c in found_compliance:
                c["family"] = RuleFamily.COMPLIANCE.value
            for t in found_treatment:
                t["family"] = RuleFamily.TREATMENT.value
            for r in found_reliability:
                r["family"] = RuleFamily.RELIABILITY.value

            all_matches = found_compliance + found_treatment + found_reliability

            if not all_matches:
                return RuleLookupResult(
                    status=RuleLookupStatus.NOT_FOUND,
                    query=clean_target,
                    error_message=f"Không tìm thấy quy tắc nào khớp với từ khóa '{clean_target}' trong hệ sinh thái DataTrust OS.",
                    scope={"query": clean_target, "dataset_id": dataset_id}
                )

            # Check if there is an exact single match
            exact_matches = [
                m for m in all_matches
                if m.get("rule_id", "").lower() == clean_target.lower()
                or m.get("rule_code", "").lower() == clean_target.lower()
                or m.get("operation_id", "").lower() == clean_target.lower()
            ]

            if len(exact_matches) == 1:
                match = exact_matches[0]
                fam = RuleFamily(match["family"])
                return RuleLookupResult(
                    status=RuleLookupStatus.FOUND_ONE,
                    query=clean_target,
                    family=fam,
                    rule=match,
                    rules=exact_matches,
                    scope={"query": clean_target, "dataset_id": dataset_id}
                )

            if len(all_matches) == 1:
                match = all_matches[0]
                fam = RuleFamily(match["family"])
                return RuleLookupResult(
                    status=RuleLookupStatus.FOUND_ONE,
                    query=clean_target,
                    family=fam,
                    rule=match,
                    rules=all_matches,
                    scope={"query": clean_target, "dataset_id": dataset_id}
                )

            # Multiple matches found
            return RuleLookupResult(
                status=RuleLookupStatus.FOUND_MANY,
                query=clean_target,
                rules=all_matches,
                scope={"query": clean_target, "total_matches": len(all_matches), "dataset_id": dataset_id}
            )

        except Exception as e:
            logger.error(f"Error in lookup_by_identifier({query}): {e}", exc_info=True)
            return RuleLookupResult(
                status=RuleLookupStatus.DB_ERROR,
                query=clean_target,
                error_message=f"Lỗi kết nối cơ sở dữ liệu khi tra cứu quy tắc: {str(e)}",
                scope={"query": clean_target}
            )
