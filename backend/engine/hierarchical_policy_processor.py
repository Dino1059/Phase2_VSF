from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.engine.compliance_rule_evaluator import (
    BLOCKING_ACTIONS,
    ComplianceRuleEvaluator,
    RuleFinding,
)
from backend.engine.jurisdiction_config import JurisdictionHierarchyConfig
from backend.engine.operation_registry import OperationRegistry


@dataclass
class PolicyViolation:
    rule_id: str
    column_name: str
    reason: str
    severity: str = "CRITICAL"
    jurisdiction: str = "GLOBAL"
    policy_id: Optional[str] = None
    policy_name: Optional[str] = None
    law_ref: Optional[str] = None
    rule_version: Optional[str] = None
    action: Optional[str] = None
    evaluation_phase: Optional[str] = None
    input_field_hash: Optional[str] = None
    observed_value: Any = None
    runtime_state: str = "executed"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LaneBVerdict:
    record_id: str
    status: str
    treated_record: Optional[Dict[str, Any]]
    raw_record: Dict[str, Any]
    compliance_evidence: List[str] = field(default_factory=list)
    required_treatments: List[Dict[str, Any]] = field(default_factory=list)
    failure_reasons: List[str] = field(default_factory=list)
    jurisdiction_chain: List[str] = field(default_factory=list)
    normalized_zone: str = "GLOBAL"
    applied_policy_ids: List[str] = field(default_factory=list)
    violations: List[PolicyViolation] = field(default_factory=list)
    rule_snapshot_hash: Optional[str] = None
    rule_snapshot: List[Dict[str, Any]] = field(default_factory=list)
    executed_rule_keys: List[str] = field(default_factory=list)
    skipped_rule_keys: List[str] = field(default_factory=list)
    rule_executions: List[Dict[str, Any]] = field(default_factory=list)
    treatment_executions: List[Dict[str, Any]] = field(default_factory=list)
    shadow_mode: bool = False


class HierarchicalPolicyProcessor:
    """Resolve jurisdiction, apply eligible treatments, and emit structured violations."""

    ZONE_POLICIES: Dict[str, Dict[str, str]] = {
        "VN": {
            "policy_id": "POL-VN-LAW91",
            "policy_name": "Vietnam Personal Data Protection",
            "law_ref": "Luật 91/2025/QH15 & NĐ 356/2025/NĐ-CP",
        },
        "EU": {
            "policy_id": "POL-EU-GDPR",
            "policy_name": "EU GDPR",
            "law_ref": "GDPR Art. 5(1)(c) & Art. 25",
        },
        "US": {
            "policy_id": "POL-US-CCPA",
            "policy_name": "US CCPA/CPRA",
            "law_ref": "CCPA/CPRA § 1798.100 et seq.",
        },
    }

    def __init__(
        self,
        hierarchy_config: Optional[JurisdictionHierarchyConfig] = None,
        active_treatments: Optional[List[Dict[str, Any]]] = None,
        active_compliance_rules: Optional[List[Dict[str, Any]]] = None,
        shadow_mode: bool = False,
        compliance_mode: Optional[str] = None,
        rule_snapshot_hash: Optional[str] = None,
    ):
        self.hierarchy_config = hierarchy_config or JurisdictionHierarchyConfig()
        self.active_treatments = active_treatments or []
        self.active_compliance_rules = active_compliance_rules
        self.shadow_mode = (
            str(compliance_mode).upper() == "SHADOW"
            if compliance_mode is not None else shadow_mode
        )
        self.provided_rule_snapshot_hash = rule_snapshot_hash
        # ``None`` is reserved for the explicitly-invoked legacy compatibility
        # path used by older callers/tests.  An empty snapshot is still a valid
        # data-driven snapshot and must never reactivate hard-coded rules.
        self.rule_evaluator = (
            ComplianceRuleEvaluator(active_compliance_rules)
            if active_compliance_rules is not None else None
        )
        if self.rule_evaluator is not None:
            self._cached_snapshot = [self._public_rule_snapshot(r) for r in self.rule_evaluator.rules]
            self._cached_snapshot_hash = self.provided_rule_snapshot_hash or ComplianceRuleEvaluator.snapshot_hash(self._cached_snapshot)
            self._cached_rule_by_key = {
                self.rule_evaluator.rule_key(r): r for r in self.rule_evaluator.rules
            }
        else:
            self._cached_snapshot = []
            self._cached_snapshot_hash = self.provided_rule_snapshot_hash
            self._cached_rule_by_key = {}

    def process_records(
        self, dataset_id: str, records: List[Dict[str, Any]], pk_col: Optional[str] = None
    ) -> List[LaneBVerdict]:
        return [self.process_single_record(dataset_id, item, pk_col) for item in records]

    def process_single_record(
        self, dataset_id: str, raw_record: Dict[str, Any], pk_col: Optional[str] = None
    ) -> LaneBVerdict:
        if self.rule_evaluator is not None:
            return self._process_versioned_record(dataset_id, raw_record, pk_col)
        raw_item = dict(raw_record)
        resolved_pk = pk_col
        if not resolved_pk:
            for candidate in (
                "trip_id", "record_id", "session_id", "customer_id", "driver_id",
                "feedback_id", "vehicle_vin", "vin", "id",
            ):
                if candidate in raw_item:
                    resolved_pk = candidate
                    break
        pk_val = str(raw_item.get(resolved_pk, "unknown"))

        zone = raw_item.get("subject_zone") or raw_item.get("zone")
        country = raw_item.get("country") or raw_item.get("subject_jurisdiction")
        jurisdiction_chain = self.hierarchy_config.resolve_chain(zone, country)
        normalized_zone = jurisdiction_chain[1] if len(jurisdiction_chain) > 1 else "GLOBAL"
        evidence = [f"Jurisdiction chain resolved: {' -> '.join(jurisdiction_chain)}"]
        failure_reasons: List[str] = []
        violations: List[PolicyViolation] = []
        applied_policy_ids: List[str] = []
        is_warning = False

        if not zone or normalized_zone not in self.hierarchy_config.mapping:
            is_warning = True
            applied_policy_ids.append("NO_ACTIVE_PACK")
            evidence.append(
                f"NO_ACTIVE_PACK: no active zone policy pack for {normalized_zone}; only GLOBAL controls may apply"
            )

        def add_policy(policy_id: Optional[str]) -> None:
            if policy_id and policy_id not in applied_policy_ids:
                applied_policy_ids.append(policy_id)

        def fail(
            rule_id: str,
            column_name: str,
            reason: str,
            *,
            jurisdiction: str,
            policy_id: str,
            policy_name: str,
            law_ref: str,
            severity: str = "CRITICAL",
        ) -> None:
            failure_reasons.append(reason)
            evidence.append(reason)
            violations.append(PolicyViolation(
                rule_id=rule_id,
                column_name=column_name,
                reason=reason,
                severity=severity,
                jurisdiction=jurisdiction,
                policy_id=policy_id,
                policy_name=policy_name,
                law_ref=law_ref,
            ))
            add_policy(policy_id)

        # Zone-specific geographic controls.
        if "trips" in dataset_id or "pickup_latitude" in raw_item:
            lat = self._safe_float(raw_item.get("pickup_latitude"))
            if normalized_zone == "VN" and lat is not None and not 8.0 <= lat <= 24.0:
                fail(
                    "COMP-TRIP-GEO-VN", "pickup_latitude",
                    f"Pre-check failed: Tọa độ điểm đón ({lat}) nằm ngoài lãnh thổ cấp phép VN (Luật 91/2025/QH15 & NĐ 356/2025)",
                    jurisdiction="VN", policy_id="POL-VN-LAW91",
                    policy_name="Vietnam Personal Data Protection",
                    law_ref="Luật 91/2025/QH15 & NĐ 356/2025/NĐ-CP",
                )
            elif normalized_zone == "EU" and lat is not None and not 52.0 <= lat <= 53.5:
                fail(
                    "COMP-TRIP-GEO-EU", "pickup_latitude",
                    f"Pre-check failed: Tọa độ ({lat}) nằm ngoài phạm vi cấp phép đội xe Berlin EU (GDPR Art. 5)",
                    jurisdiction="EU", policy_id="POL-EU-GDPR", policy_name="EU GDPR",
                    law_ref="GDPR Art. 5",
                )

        if raw_item.get("currency_unverified") in (True, "true", "TRUE", 1, "1"):
            is_warning = True
            evidence.append("Pre-check warning: Đơn vị tiền tệ chưa xác thực đối soát liên ngân hàng")

        eligible_treatments: List[Dict[str, Any]] = []
        for treatment in self.active_treatments:
            column = treatment.get("column") or treatment.get("column_name")
            declared = (
                treatment.get("country")
                or treatment.get("jurisdiction")
                or treatment.get("subject_zone")
                or treatment.get("zone")
            )
            # Fail closed for legacy unscoped rules: assuming GLOBAL here would
            # reintroduce cross-zone policy leakage.
            if not declared:
                continue
            rule_jurisdiction = self.hierarchy_config.normalize_zone(declared)
            if (
                rule_jurisdiction in jurisdiction_chain
                and column in raw_item
                and raw_item[column] is not None
            ):
                selected = dict(treatment)
                selected["column"] = column
                selected["jurisdiction"] = rule_jurisdiction
                selected["_specificity"] = jurisdiction_chain.index(rule_jurisdiction)
                eligible_treatments.append(selected)

        # A more-specific country/zone rule replaces a global rule for the same
        # field and operation. This prevents sequential cross-scope treatment.
        selected_by_target: Dict[str, tuple] = {}
        for selected in eligible_treatments:
            key = (selected.get("column"), selected.get("operation_id"))
            current = selected_by_target.get(key)
            if current is None or selected["_specificity"] > current["_specificity"]:
                selected_by_target[key] = selected
        required_treatments = []
        for selected in selected_by_target.values():
            selected.pop("_specificity", None)
            required_treatments.append(selected)
            add_policy(selected.get("policy_id"))

        configured_columns = {item.get("column") for item in required_treatments}
        zone_policy = self.ZONE_POLICIES.get(normalized_zone)

        def add_compatibility_treatment(
            column: str, operation_id: str, params: Dict[str, Any]
        ) -> None:
            if not zone_policy:
                return
            required_treatments.append({
                "column": column,
                "operation_id": operation_id,
                "params": params,
                "jurisdiction": normalized_zone,
                **zone_policy,
            })
            add_policy(zone_policy["policy_id"])

        # Backward-compatible defaults are strictly scoped to the record zone.
        for key in ("customer_phone", "phone_number", "customer_contact"):
            if key in raw_item and raw_item[key] and key not in configured_columns:
                add_compatibility_treatment(key, "MASK", {"prefix_len": 3, "suffix_len": 2})
        for key in ("customer_email", "email"):
            if key in raw_item and raw_item[key] and key not in configured_columns:
                add_compatibility_treatment(key, "MASK", {"prefix_len": 2, "suffix_len": 4})
        if raw_item.get("driver_id") and "driver_id" not in configured_columns:
            add_compatibility_treatment(
                "driver_id", "HASH",
                {"algorithm": "sha256", "salt_ref": "gsm_driver_salt_2026"},
            )
        for key in ("pickup_latitude", "latitude", "pickup_longitude", "longitude"):
            if key in raw_item and raw_item[key] is not None and key not in configured_columns:
                add_compatibility_treatment(key, "ROUND", {"decimals": 2})

        treated_item = dict(raw_item)
        if not violations:
            for treatment in required_treatments:
                column = treatment["column"]
                if column in treated_item:
                    treated_item[column] = OperationRegistry.execute(
                        treatment["operation_id"],
                        treated_item[column],
                        treatment.get("params", {}),
                    )

        # Global operational/financial controls are valid for every zone.
        if not violations and "fare_amount" in treated_item:
            fare = self._safe_float(treated_item.get("fare_amount"))
            distance = self._safe_float(treated_item.get("trip_distance_km"))
            if fare is not None and fare <= 0.0:
                fail(
                    "COMP-TRIP-REV-01", "fare_amount",
                    f"Post-check failed: Cước chuyến đi ({fare}) <= 0 vi phạm chuẩn IFRS 15 / SOX 404",
                    jurisdiction="GLOBAL", policy_id="POL-IFRS-15",
                    policy_name="IFRS 15 / SOX 404 Revenue Control",
                    law_ref="IFRS 15 / SOX 404",
                )
            elif distance is not None and distance < 0.1:
                fail(
                    "COMP-TRIP-REV-01", "trip_distance_km",
                    f"Post-check failed: Cự ly ({distance} km) < 0.1km vi phạm chuẩn ghi nhận cuốc xe IFRS 15",
                    jurisdiction="GLOBAL", policy_id="POL-IFRS-15",
                    policy_name="IFRS 15 / SOX 404 Revenue Control",
                    law_ref="IFRS 15 / SOX 404",
                )

        if not violations and "battery_temp_c" in treated_item:
            temperature = self._safe_float(treated_item.get("battery_temp_c"))
            if temperature is not None and temperature > 65.0:
                fail(
                    "COMP-TEL-BMS-05", "battery_temp_c",
                    f"Post-check failed: Nhiệt độ pack pin ({temperature}°C) vượt ngưỡng an toàn 65°C IEC 62660-1",
                    jurisdiction="GLOBAL", policy_id="POL-EV-SAFETY",
                    policy_name="EV Battery Safety", law_ref="IEC 62660-1 / UN ECE R100",
                )

        if not violations and {"meter_kwh_delta", "bms_kwh_delta"} <= treated_item.keys():
            meter = self._safe_float(treated_item.get("meter_kwh_delta"))
            bms = self._safe_float(treated_item.get("bms_kwh_delta"))
            if meter is not None and bms is not None and meter > 0 and abs(meter - bms) > 0.03 * meter:
                fail(
                    "COMP-CHG-KW-06", "meter_kwh_delta",
                    f"Post-check failed: Sai lệch công tơ trụ sạc ({abs(meter-bms):.2f} kWh) vượt 3%",
                    jurisdiction="GLOBAL", policy_id="POL-CHARGING-METER",
                    policy_name="Charging Meter Control",
                    law_ref="SOX 404 & V-GREEN Metering Standard",
                )

        if not violations:
            for key in ("customer_phone", "customer_contact", "phone_number"):
                if key in treated_item and treated_item[key]:
                    value = str(treated_item[key])
                    if "*" not in value and len(value) >= 6:
                        policy = zone_policy or {
                            "policy_id": "POL-DATA-PROTECTION-GLOBAL",
                            "policy_name": "Global Data Protection Control",
                            "law_ref": "Internal Data Protection Standard",
                        }
                        fail(
                            "COMP-PII-PHONE-MASK", key,
                            "Post-check failed: phone number was not masked by the applicable zone policy",
                            jurisdiction=normalized_zone, **policy,
                        )

        status = "FAIL" if violations else ("WARNING" if is_warning else "PASS")
        return LaneBVerdict(
            record_id=pk_val,
            status=status,
            treated_record=treated_item if status in {"PASS", "WARNING"} else None,
            raw_record=raw_item,
            compliance_evidence=evidence,
            required_treatments=required_treatments,
            failure_reasons=failure_reasons,
            jurisdiction_chain=jurisdiction_chain,
            normalized_zone=normalized_zone,
            applied_policy_ids=applied_policy_ids,
            violations=violations,
        )

    def _process_versioned_record(
        self, dataset_id: str, raw_record: Dict[str, Any], pk_col: Optional[str]
    ) -> LaneBVerdict:
        """Evaluate a DB rule snapshot without executing rule-authored code."""
        raw_item = dict(raw_record)
        resolved_pk = pk_col or next((c for c in (
            "trip_id", "record_id", "session_id", "customer_id", "driver_id",
            "feedback_id", "vehicle_vin", "vin", "id",
        ) if c in raw_item), None)
        pk_val = str(raw_item.get(resolved_pk, "unknown"))
        zone = raw_item.get("subject_zone") or raw_item.get("zone")
        country = raw_item.get("country") or raw_item.get("subject_jurisdiction")
        chain = self.hierarchy_config.resolve_chain(zone, country)
        normalized_zone = chain[1] if len(chain) > 1 else "GLOBAL"
        evidence = [f"Jurisdiction chain resolved: {' -> '.join(chain)}"]
        violations: List[PolicyViolation] = []
        applied_policy_ids: List[str] = []
        executed: List[str] = []

        applicable, skipped = self.rule_evaluator.applicable_rules(dataset_id, chain)
        snapshot = self._cached_snapshot
        snapshot_hash = self._cached_snapshot_hash
        runtime_by_key = {
            self.rule_evaluator.rule_key(rule): str(rule.get("runtime_mode", "ENFORCED")).upper()
            for rule in applicable
        }
        rule_by_key = self._cached_rule_by_key

        def append_finding(finding: RuleFinding, *, invariant: bool = False) -> None:
            evidence.append(f"{finding.rule_id}@{finding.rule_version}: {finding.reason}")
            if finding.policy_id and finding.policy_id not in applied_policy_ids:
                applied_policy_ids.append(finding.policy_id)
            rule_key = f"{finding.rule_id}@{finding.rule_version}"
            # Routing/pack invariants are fail-closed and cannot be neutralized
            # by a rollout mode intended only for policy rules.
            is_shadowed = False if invariant else (
                self.shadow_mode or runtime_by_key.get(rule_key) == "SHADOW"
            )
            violations.append(PolicyViolation(
                rule_id=finding.rule_id, rule_version=finding.rule_version,
                column_name=finding.column_name, reason=finding.reason,
                severity=finding.severity, jurisdiction=finding.jurisdiction,
                policy_id=finding.policy_id, policy_name=finding.policy_name,
                law_ref=finding.law_ref, action=finding.action,
                evaluation_phase=finding.phase, input_field_hash=finding.input_field_hash,
                observed_value=finding.observed_value,
                runtime_state="shadowed" if is_shadowed else "executed",
            ))

        # Jurisdiction routing controls are engine invariants, not mutable legal rules.
        if not zone:
            append_finding(RuleFinding(
                "ZONE_MISSING", "1", "subject_zone", "subject jurisdiction is required",
                "CRITICAL", "BLOCK", "PRE_CHECK", "GLOBAL", "POLICY-ROUTING",
                "Policy routing control", None, self._value_hash("subject_zone", None), None,
            ), invariant=True)
        elif normalized_zone not in self.hierarchy_config.mapping:
            append_finding(RuleFinding(
                "NO_ACTIVE_PACK", "1", "subject_zone",
                f"no active policy pack for {normalized_zone}",
                "CRITICAL", "QUARANTINE", "PRE_CHECK", normalized_zone, None, None,
                None, self._value_hash("subject_zone", normalized_zone), "[REDACTED]",
            ), invariant=True)
        elif not any(rule["jurisdiction"] != "GLOBAL" for rule in applicable):
            append_finding(RuleFinding(
                "NO_ACTIVE_PACK", "1", "subject_zone",
                f"no active zone-specific policy pack for {normalized_zone}",
                "CRITICAL", "QUARANTINE", "PRE_CHECK", normalized_zone, None, None,
                None, self._value_hash("subject_zone", normalized_zone), "[REDACTED]",
            ), invariant=True)

        pre = self.rule_evaluator.evaluate(applicable, raw_item, raw_item, "PRE_CHECK")
        executed.extend(pre.executed_rule_keys)
        for finding in pre.findings:
            append_finding(finding)

        pre_blocked = any(
            item.action in BLOCKING_ACTIONS and item.evaluation_phase == "PRE_CHECK"
            and item.runtime_state == "executed"
            for item in violations
        )
        required_treatments = self._select_treatments(raw_item, chain)
        treatment_executions: List[Dict[str, Any]] = []
        for treatment in required_treatments:
            policy_id = treatment.get("policy_id")
            if policy_id and policy_id not in applied_policy_ids:
                applied_policy_ids.append(policy_id)

        treated_item = dict(raw_item)
        if not pre_blocked:
            for treatment in required_treatments:
                column = treatment["column"]
                if column in treated_item:
                    before_hash = self._value_hash(column, treated_item[column])
                    try:
                        treated_item[column] = OperationRegistry.execute(
                            treatment["operation_id"], treated_item[column], treatment.get("params", {})
                        )
                        treatment_executions.append(self._treatment_execution(
                            treatment, "APPLIED", before_hash,
                            self._value_hash(column, treated_item[column]),
                        ))
                    except (ValueError, RuntimeError) as exc:
                        treatment_executions.append(self._treatment_execution(
                            treatment, "FAILED", before_hash, None,
                        ))
                        append_finding(RuleFinding(
                            str(treatment.get("rule_id") or treatment.get("treatment_id") or "TREATMENT_FAILED"),
                            str(treatment.get("version") or "1"), column,
                            f"data treatment failed: {exc}", "CRITICAL", "QUARANTINE",
                            "POST_CHECK", str(treatment.get("jurisdiction") or normalized_zone),
                            treatment.get("policy_id"), treatment.get("policy_name"),
                            treatment.get("law_ref"), self._value_hash(column, raw_item.get(column)),
                            "[REDACTED]",
                        ), invariant=True)
                        break
            post = self.rule_evaluator.evaluate(applicable, treated_item, raw_item, "POST_CHECK")
            executed.extend(post.executed_rule_keys)
            for finding in post.findings:
                append_finding(finding)
        else:
            treatment_executions.extend(
                self._treatment_execution(treatment, "SKIPPED", self._value_hash(
                    treatment["column"], raw_item.get(treatment["column"])
                ), None)
                for treatment in required_treatments
            )
            # A blocking pre-check prevents mutation, but independent post rules
            # still run read-only so the audit contains every applicable finding.
            post = self.rule_evaluator.evaluate(applicable, raw_item, raw_item, "POST_CHECK")
            executed.extend(post.executed_rule_keys)
            for finding in post.findings:
                append_finding(finding)

        blocking = any(item.action in BLOCKING_ACTIONS and item.runtime_state == "executed" for item in violations)
        warning = any(item.action == "WARNING" for item in violations)
        status = "FAIL" if blocking else ("WARNING" if warning or any(
            item.action != "FINDING_ONLY" for item in violations
        ) else "PASS")
        failure_reasons = [
            item.reason for item in violations
            if item.action in BLOCKING_ACTIONS and item.runtime_state == "executed"
        ]
        return LaneBVerdict(
            record_id=pk_val, status=status,
            treated_record=treated_item if status != "FAIL" else None,
            raw_record=raw_item, compliance_evidence=evidence,
            required_treatments=required_treatments, failure_reasons=failure_reasons,
            jurisdiction_chain=chain, normalized_zone=normalized_zone,
            applied_policy_ids=applied_policy_ids, violations=violations,
            rule_snapshot_hash=snapshot_hash, rule_snapshot=snapshot,
            executed_rule_keys=list(dict.fromkeys(executed)),
            skipped_rule_keys=list(dict.fromkeys(skipped)),
            shadow_mode=self.shadow_mode or any(mode == "SHADOW" for mode in runtime_by_key.values()),
            rule_executions=[
                {
                    "rule_key": key,
                    "rule_id": rule_by_key[key]["rule_id"],
                    "version": str(rule_by_key[key]["version"]),
                    "pack_id": rule_by_key[key].get("pack_id"),
                    "clause_id": rule_by_key[key].get("clause_id"),
                    "jurisdiction": rule_by_key[key].get("jurisdiction"),
                    "runtime_state": "shadowed" if self.shadow_mode or runtime_by_key.get(key) == "SHADOW" else "executed",
                    "result": "FAIL" if any(
                        violation.rule_id == key.rsplit("@", 1)[0]
                        and str(violation.rule_version) == key.rsplit("@", 1)[1]
                        for violation in violations
                    ) else "PASS",
                }
                for key in dict.fromkeys(executed)
            ] + [
                {
                    "rule_key": key,
                    "rule_id": rule_by_key[key]["rule_id"],
                    "version": str(rule_by_key[key]["version"]),
                    "pack_id": rule_by_key[key].get("pack_id"),
                    "clause_id": rule_by_key[key].get("clause_id"),
                    "jurisdiction": rule_by_key[key].get("jurisdiction"),
                    "runtime_state": "skipped",
                    "result": "SKIP",
                }
                for key in dict.fromkeys(skipped)
            ],
            treatment_executions=treatment_executions,
        )

    def _select_treatments(
        self, raw_item: Dict[str, Any], jurisdiction_chain: List[str]
    ) -> List[Dict[str, Any]]:
        selected_by_target: Dict[tuple, Dict[str, Any]] = {}
        instant = datetime.now(timezone.utc)
        for treatment in self.active_treatments:
            status = str(treatment.get("status", "ACTIVE")).upper()
            runtime_mode = str(treatment.get("runtime_mode", "ENFORCED")).upper()
            if status != "ACTIVE" or runtime_mode != "ENFORCED":
                continue
            start = ComplianceRuleEvaluator._parse_time(treatment.get("effective_from"))
            end = ComplianceRuleEvaluator._parse_time(treatment.get("effective_to"))
            if (start and instant < start) or (end and instant >= end):
                continue
            column = treatment.get("column") or treatment.get("column_name")
            declared = treatment.get("country") or treatment.get("jurisdiction") or treatment.get("subject_zone") or treatment.get("zone")
            if not declared or column not in raw_item or raw_item[column] is None:
                continue
            jurisdiction = self.hierarchy_config.normalize_zone(declared)
            if jurisdiction not in jurisdiction_chain:
                continue
            selected = dict(treatment)
            selected["column"] = column
            selected["jurisdiction"] = jurisdiction
            if "params" not in selected and selected.get("params_json") is not None:
                selected["params"] = selected["params_json"]
            specificity = jurisdiction_chain.index(jurisdiction)
            # A target receives one treatment. A country rule replaces its zone
            # rule, which replaces GLOBAL, even when the operation differs.
            key = column
            current = selected_by_target.get(key)
            if current is None or specificity > current[0]:
                selected_by_target[key] = (specificity, selected)
        return [pair[1] for pair in selected_by_target.values()]

    @staticmethod
    def _public_rule_snapshot(rule: Dict[str, Any]) -> Dict[str, Any]:
        return {key: value for key, value in rule.items() if not str(key).startswith("_")}

    @classmethod
    def _treatment_execution(
        cls,
        treatment: Dict[str, Any],
        result: str,
        before_hash: Optional[str],
        after_hash: Optional[str],
    ) -> Dict[str, Any]:
        """Return audit-safe treatment evidence; values are never included."""
        return {
            "rule_id": treatment.get("rule_id") or treatment.get("treatment_id"),
            "version": str(treatment.get("version") or "1"),
            "pack_id": treatment.get("pack_id"),
            "clause_id": treatment.get("clause_id"),
            "jurisdiction": treatment.get("jurisdiction"),
            "column": treatment.get("column"),
            "operation": treatment.get("operation_id"),
            "result": result,
            "before_hash": before_hash,
            "after_hash": after_hash,
        }

    @staticmethod
    def _value_hash(column: str, value: Any) -> str:
        import hashlib
        return hashlib.sha256(f"{column}:{value!r}".encode("utf-8")).hexdigest()

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
