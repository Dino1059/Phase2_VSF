"""Safe, data-driven compliance rule evaluation.

The evaluator deliberately implements a small allow-list of operators.  Rule
documents are data, never Python expressions, and are therefore never passed
to ``eval`` or imported dynamically.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


ALLOWED_OPERATORS = {
    "required", "range", "compare", "enum", "arithmetic",
    "relative_delta", "regex", "masked", "hashed", "geofence",
    "redacted", "precision", "generalized",
    "all", "any", "not", "context_equals", "date_age_days", "is_null",
}
BLOCKING_ACTIONS = {"BLOCK", "QUARANTINE", "QUARANTINE_HITL"}

MAX_NESTING_DEPTH = 4
MAX_CHILD_CONDITIONS = 10
MAX_REFERENCED_FIELDS = 20
MAX_SERIALIZED_RULE_SIZE = 8192


@dataclass(frozen=True)
class RuleFinding:
    rule_id: str
    rule_version: str
    column_name: str
    reason: str
    severity: str
    action: str
    phase: str
    jurisdiction: str
    policy_id: Optional[str]
    policy_name: Optional[str]
    law_ref: Optional[str]
    input_field_hash: str
    observed_value: Any

    @property
    def blocking(self) -> bool:
        return self.action in BLOCKING_ACTIONS


@dataclass(frozen=True)
class EvaluationResult:
    findings: List[RuleFinding]
    executed_rule_keys: List[str]
    skipped_rule_keys: List[str]


class RuleConfigurationError(ValueError):
    """Raised for an unsafe or malformed active rule snapshot."""


class ComplianceRuleEvaluator:
    def __init__(self, rules: Sequence[Dict[str, Any]]):
        self.rules = [self._normalize_rule(rule) for rule in rules]
        self._validate_snapshot(self.rules)

    @staticmethod
    def snapshot_hash(rules: Sequence[Dict[str, Any]]) -> str:
        encoded = json.dumps(list(rules), sort_keys=True, default=str, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def applicable_rules(
        self, dataset_id: str, jurisdiction_chain: Sequence[str], as_of: Optional[datetime] = None
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        instant = as_of or datetime.now(timezone.utc)
        if instant.tzinfo is None:
            instant = instant.replace(tzinfo=timezone.utc)
        applicable, skipped = [], []
        for rule in self.rules:
            key = self.rule_key(rule)
            if rule["status"] != "ACTIVE":
                skipped.append(key)
                continue
            if rule.get("dataset_id") not in (None, "", "*", dataset_id):
                skipped.append(key)
                continue
            jurisdiction = rule["jurisdiction"]
            if jurisdiction not in jurisdiction_chain:
                skipped.append(key)
                continue
            country = str(rule.get("country") or "").strip().upper()
            if country and country not in {str(item).strip().upper() for item in jurisdiction_chain}:
                skipped.append(key)
                continue
            start = self._parse_time(rule.get("effective_from"))
            end = self._parse_time(rule.get("effective_to"))
            if (start and instant < start) or (end and instant >= end):
                skipped.append(key)
                continue
            applicable.append(rule)
        return applicable, skipped

    def evaluate(
        self,
        rules: Iterable[Dict[str, Any]],
        record: Dict[str, Any],
        raw_record: Dict[str, Any],
        phase: str,
        context: Optional[Dict[str, Any]] = None,
        as_of: Optional[datetime] = None,
    ) -> EvaluationResult:
        findings, executed, skipped = [], [], []
        normalized_phase = phase.upper()
        for rule in rules:
            key = self.rule_key(rule)
            if rule["evaluation_phase"] != normalized_phase:
                continue
            executed.append(key)
            finding = self._evaluate_one(rule, record, raw_record, context=context, as_of=as_of)
            if finding:
                findings.append(finding)
        return EvaluationResult(findings, executed, skipped)

    def _evaluate_one(
        self,
        rule: Dict[str, Any],
        record: Dict[str, Any],
        raw_record: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        as_of: Optional[datetime] = None,
    ) -> Optional[RuleFinding]:
        condition = rule["condition_json"]
        operator = condition["operator"]
        fields = self._fields(condition)
        if operator not in {"required", "is_null", "all", "any", "not", "context_equals"}:
            missing = [name for name in fields if name not in record or record.get(name) in (None, "")]
            if missing:
                behavior = rule["missing_behavior"]
                if behavior == "SKIP":
                    return None
                severity = "WARNING" if behavior == "WARNING" else rule.get("severity", "CRITICAL")
                return self._finding(rule, missing[0], f"required input is missing: {missing[0]}", severity, None)

        try:
            passed, column, observed, detail = self._dispatch(
                operator, condition, record, raw_record, context=context, as_of=as_of, depth=0
            )
        except (KeyError, TypeError, ValueError, ArithmeticError) as exc:
            behavior = rule["invalid_type_behavior"]
            # Exception strings from parsers commonly embed the rejected value.
            # Evidence must describe the failure without copying raw PII/secrets.
            severity = "WARNING" if behavior == "WARNING" else rule.get("severity", "CRITICAL")
            return self._finding(rule, fields[0] if fields else "*", "invalid input type", severity, None)
        if passed:
            return None
        return self._finding(rule, column, detail, rule.get("severity", "CRITICAL"), observed)

    def _dispatch(
        self,
        operator: str,
        c: Dict[str, Any],
        record: Dict[str, Any],
        raw: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        as_of: Optional[datetime] = None,
        depth: int = 0,
    ) -> Tuple[bool, str, Any, str]:
        if depth > MAX_NESTING_DEPTH:
            raise RuleConfigurationError(f"runtime condition nesting depth exceeds {MAX_NESTING_DEPTH}")

        field = str(c.get("field") or c.get("column") or "*")
        if operator == "all":
            children = c.get("conditions") or c.get("rules") or []
            if not children:
                return True, field, None, ""
            for child in children:
                child_op = str(child.get("operator", child.get("type", ""))).lower()
                ok, col, obs, det = self._dispatch(
                    child_op, child, record, raw, context=context, as_of=as_of, depth=depth + 1
                )
                if not ok:
                    return False, col, obs, det
            return True, field, None, ""
        if operator == "any":
            children = c.get("conditions") or c.get("rules") or []
            if not children:
                return True, field, None, ""
            last_col, last_obs, last_det = field, None, "all alternative conditions failed"
            for child in children:
                child_op = str(child.get("operator", child.get("type", ""))).lower()
                ok, col, obs, det = self._dispatch(
                    child_op, child, record, raw, context=context, as_of=as_of, depth=depth + 1
                )
                if ok:
                    return True, col, obs, ""
                last_col, last_obs, last_det = col, obs, det
            return False, last_col, last_obs, f"none of {len(children)} conditions met: {last_det}"
        if operator == "not":
            child = c.get("condition")
            if child is None:
                children = c.get("conditions") or c.get("rules") or []
                if len(children) != 1:
                    raise RuleConfigurationError("operator 'not' requires exactly one child condition")
                child = children[0]
            child_op = str(child.get("operator", child.get("type", ""))).lower()
            ok, col, obs, det = self._dispatch(
                child_op, child, record, raw, context=context, as_of=as_of, depth=depth + 1
            )
            if ok:
                return False, col, obs, f"negated condition unexpectedly satisfied ({child_op})"
            return True, col, obs, ""
        if operator == "is_null":
            val = record.get(field)
            is_none_or_empty = val is None or val == ""
            if not is_none_or_empty and isinstance(val, float) and math.isnan(val):
                is_none_or_empty = True
            if is_none_or_empty:
                return True, field, None, ""
            return False, field, val, f"{field} is expected to be null or empty, observed {val!r}"
        if operator == "context_equals":
            ctx = context or {}
            key = str(c.get("key") or c.get("field") or field)
            expected = c.get("value")
            observed = ctx.get(key)
            comparator = c.get("comparator", "==")
            if comparator == "==":
                matched = (observed == expected)
            elif comparator == "!=":
                matched = (observed != expected)
            elif comparator in ("in", "IN"):
                matched = observed in (expected or [])
            elif comparator in ("not_in", "NOT_IN"):
                matched = observed not in (expected or [])
            else:
                raise ValueError(f"unsupported context comparator: {comparator}")
            if matched:
                return True, key, observed, ""
            return False, key, observed, f"context key '{key}' ({observed!r}) does not satisfy {comparator} {expected!r}"
        if operator == "date_age_days":
            val = record.get(field)
            if val is None or val == "" or (isinstance(val, float) and math.isnan(val)):
                return False, field, None, f"{field} date is missing or null"
            if isinstance(val, datetime):
                dt_rec = val
            else:
                try:
                    dt_rec = datetime.fromisoformat(str(val).replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    dt_rec = datetime.strptime(str(val)[:10], "%Y-%m-%d")
            if dt_rec.tzinfo is None:
                dt_rec = dt_rec.replace(tzinfo=timezone.utc)
            else:
                dt_rec = dt_rec.astimezone(timezone.utc)

            run_as_of = as_of
            if run_as_of is None and context and "as_of" in context:
                ctx_as_of = context["as_of"]
                if isinstance(ctx_as_of, datetime):
                    run_as_of = ctx_as_of
                elif isinstance(ctx_as_of, str):
                    try:
                        run_as_of = datetime.fromisoformat(ctx_as_of.replace("Z", "+00:00"))
                    except ValueError:
                        run_as_of = datetime.strptime(ctx_as_of[:10], "%Y-%m-%d")
            if run_as_of is None and "as_of" in c:
                c_as_of = c["as_of"]
                if isinstance(c_as_of, datetime):
                    run_as_of = c_as_of
                elif isinstance(c_as_of, str):
                    try:
                        run_as_of = datetime.fromisoformat(c_as_of.replace("Z", "+00:00"))
                    except ValueError:
                        run_as_of = datetime.strptime(c_as_of[:10], "%Y-%m-%d")
            if run_as_of is None:
                run_as_of = datetime.now(timezone.utc)
            elif run_as_of.tzinfo is None:
                run_as_of = run_as_of.replace(tzinfo=timezone.utc)
            else:
                run_as_of = run_as_of.astimezone(timezone.utc)

            delta = run_as_of - dt_rec
            age_days = delta.total_seconds() / 86400.0

            max_days = c.get("max_days", c.get("days", c.get("threshold")))
            min_days = c.get("min_days")
            comparator = c.get("comparator")
            if comparator:
                thresh = float(max_days if max_days is not None else 0.0)
                funcs = {"<=": age_days <= thresh, "<": age_days < thresh,
                         ">=": age_days >= thresh, ">": age_days > thresh,
                         "==": abs(age_days - thresh) < 1e-5, "!=": abs(age_days - thresh) >= 1e-5}
                if comparator not in funcs:
                    raise ValueError(f"unsupported comparator {comparator}")
                ok = funcs[comparator]
            else:
                ok = True
                if max_days is not None:
                    ok = ok and (age_days <= float(max_days))
                if min_days is not None:
                    ok = ok and (age_days >= float(min_days))

            if ok:
                return True, field, round(age_days, 2), ""
            return False, field, round(age_days, 2), f"{field} age ({age_days:.1f} days) exceeds permitted range"
        if operator == "required":
            required = c.get("fields") or [field]
            missing = [f for f in required if f not in record or record.get(f) in (None, "")]
            return not missing, missing[0] if missing else field, None, f"required input is missing: {missing[0] if missing else field}"
        if operator == "range":
            value = self._number(record[field])
            minimum, maximum = c.get("min"), c.get("max")
            ok = (minimum is None or value >= float(minimum)) and (maximum is None or value <= float(maximum))
            return ok, field, value, f"{field} is outside permitted range [{minimum}, {maximum}]"
        if operator == "compare":
            left = record[field]
            right = record.get(c["right_field"]) if c.get("right_field") else c.get("value")
            comparator = c.get("comparator", c.get("op", "=="))
            funcs = {"==": lambda a,b:a==b, "!=": lambda a,b:a!=b, ">": lambda a,b:a>b,
                     ">=": lambda a,b:a>=b, "<": lambda a,b:a<b, "<=": lambda a,b:a<=b}
            if comparator not in funcs:
                raise ValueError(f"unsupported comparator {comparator}")
            return funcs[comparator](left, right), field, left, f"{field} does not satisfy {comparator} comparison"
        if operator == "enum":
            value = record[field]
            allowed = c.get("values", c.get("allowed", []))
            if value in allowed:
                return True, field, value, ""
            if isinstance(value, str):
                trimmed_value = value.strip()
                trimmed_allowed = [str(x).strip() for x in allowed]
                if trimmed_value in trimmed_allowed:
                    return True, field, trimmed_value, ""
            return False, field, value, f"{field} is not in the allowed value set"
        if operator == "arithmetic":
            target = self._number(record[field])
            components = c.get("fields") or c.get("components") or []
            values = [self._number(record[name]) for name in components]
            operation = c.get("operation", "sum")
            if operation == "sum": expected = sum(values)
            elif operation == "difference": expected = values[0] - sum(values[1:])
            elif operation == "product": expected = math.prod(values)
            else: raise ValueError(f"unsupported arithmetic operation {operation}")
            tolerance = float(c.get("tolerance", 0))
            return abs(target - expected) <= tolerance, field, target, f"{field} differs from computed {operation} by more than {tolerance}"
        if operator == "relative_delta":
            left_field = str(c.get("left_field") or field)
            right_field = str(c["right_field"])
            left, right = self._number(record[left_field]), self._number(record[right_field])
            denominator_mode = c.get("denominator", "left")
            denominator = {"left": abs(left), "right": abs(right), "mean": (abs(left)+abs(right))/2}.get(denominator_mode)
            if denominator is None: raise ValueError(f"unsupported denominator {denominator_mode}")
            if denominator == 0: raise ValueError("relative delta denominator is zero")
            delta = abs(left-right)/denominator
            limit = float(c.get("max", c.get("tolerance", 0)))
            return delta <= limit, left_field, delta, f"relative delta {delta:.6g} exceeds {limit}"
        if operator == "regex":
            value = str(record[field])
            matched = re.fullmatch(str(c["pattern"]), value) is not None
            if c.get("negate"): matched = not matched
            return matched, field, "[REDACTED]", f"{field} does not satisfy the required pattern"
        if operator == "masked":
            value, original = str(record[field]), str(raw.get(field, ""))
            mask_pattern = str(c.get("pattern", r".*\*+.*"))
            ok = value != original and re.fullmatch(mask_pattern, value) is not None
            return ok, field, "[REDACTED]", f"{field} was not masked according to policy"
        if operator == "hashed":
            value, original = str(record[field]), str(raw.get(field, ""))
            algorithm = c.get("algorithm", "sha256").lower()
            lengths = {"sha256": 64, "sha384": 96, "sha512": 128}
            expected_length = int(c.get("length", lengths.get(algorithm, 64)))
            ok = value != original and re.fullmatch(rf"[0-9a-fA-F]{{{expected_length}}}", value) is not None
            return ok, field, "[HASHED]", f"{field} was not hashed according to policy"
        if operator == "redacted":
            value, original = str(record[field]), str(raw.get(field, ""))
            patterns = c.get("patterns") or [
                r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
                r"(?:\+?\d[\d .()-]{6,}\d)",
            ]
            ok = value != original and all(re.search(str(pattern), value) is None for pattern in patterns)
            return ok, field, "[REDACTED]", f"{field} still contains disallowed personal data"
        if operator in {"precision", "generalized"}:
            max_decimals = int(c.get("max_decimals", c.get("decimals", 2)))
            raw_value = raw.get(field)
            val_str = str(record[field]).strip()
            try:
                dec_val = Decimal(val_str)
                exponent = abs(dec_val.as_tuple().exponent) if dec_val.as_tuple().exponent < 0 else 0
                val_num = float(dec_val)
                is_rounded = exponent <= max_decimals or abs(val_num - round(val_num, max_decimals)) < 1e-7
            except (InvalidOperation, TypeError, ValueError):
                val_num = self._number(record[field])
                is_rounded = abs(val_num - round(val_num, max_decimals)) < 1e-7

            changed = str(record[field]) != str(raw_value)
            if raw_value not in (None, ""):
                try:
                    changed = changed or val_num != self._number(raw_value)
                except (ValueError, TypeError):
                    pass
            ok = is_rounded and (changed or not c.get("require_changed", False))
            return ok, field, "[LOCATION]", f"{field} exceeds permitted coordinate precision ({max_decimals} decimals)"
        if operator == "geofence":
            lat_field, lon_field = str(c.get("latitude_field", "latitude")), str(c.get("longitude_field", "longitude"))
            lat, lon = self._number(record[lat_field]), self._number(record[lon_field])
            if c.get("polygon"):
                ok = self._point_in_polygon(lon, lat, c["polygon"])
            else:
                bounds = c.get("bounds", c)
                ok = float(bounds["min_lat"]) <= lat <= float(bounds["max_lat"]) and float(bounds["min_lon"]) <= lon <= float(bounds["max_lon"])
            return ok, f"{lat_field},{lon_field}", "[LOCATION]", "coordinates are outside the permitted geofence"
        raise RuleConfigurationError(f"unsupported operator: {operator}")

    def _finding(self, rule: Dict[str, Any], column: str, reason: str, severity: str, observed: Any) -> RuleFinding:
        action = rule["on_fail_action"]
        if severity == "WARNING" and action in BLOCKING_ACTIONS and reason.startswith(("required input", "invalid input")):
            action = "WARNING"
        field_hash = hashlib.sha256(f"{column}:{observed!r}".encode("utf-8")).hexdigest()
        safe_observed = observed if isinstance(observed, (int, float, bool)) else (observed if observed in (None, "[REDACTED]", "[HASHED]", "[LOCATION]") else "[REDACTED]")
        return RuleFinding(
            str(rule["rule_id"]), str(rule["version"]), column, reason,
            severity, action, rule["evaluation_phase"], rule["jurisdiction"],
            rule.get("policy_id"), rule.get("policy_name"), rule.get("law_ref"),
            field_hash, safe_observed,
        )

    @classmethod
    def _validate_condition_ast(
        cls,
        condition: Dict[str, Any],
        depth: int = 0,
        visited_fields: Optional[set] = None,
    ) -> set:
        if depth > MAX_NESTING_DEPTH:
            raise RuleConfigurationError(
                f"condition nesting depth {depth} exceeds maximum permitted depth {MAX_NESTING_DEPTH}"
            )
        if visited_fields is None:
            visited_fields = set()

        if not isinstance(condition, dict):
            raise RuleConfigurationError("condition must be a JSON object")

        operator = str(condition.get("operator", condition.get("type", ""))).lower()
        if not operator or operator not in ALLOWED_OPERATORS:
            raise RuleConfigurationError(f"unsupported operator: {operator}")

        for key in ("field", "column", "left_field", "right_field", "latitude_field", "longitude_field"):
            if condition.get(key) and condition[key] != "*":
                visited_fields.add(str(condition[key]))
        for f in (condition.get("fields") or condition.get("components") or []):
            if f and f != "*":
                visited_fields.add(str(f))

        if len(visited_fields) > MAX_REFERENCED_FIELDS:
            raise RuleConfigurationError(
                f"referenced fields count {len(visited_fields)} exceeds maximum permitted {MAX_REFERENCED_FIELDS}"
            )

        if operator in {"all", "any"}:
            children = condition.get("conditions") or condition.get("rules")
            if not isinstance(children, list):
                raise RuleConfigurationError(f"operator '{operator}' conditions must be a list")
            if not (1 <= len(children) <= MAX_CHILD_CONDITIONS):
                raise RuleConfigurationError(
                    f"operator '{operator}' has {len(children)} child conditions; must be between 1 and {MAX_CHILD_CONDITIONS}"
                )
            for child in children:
                cls._validate_condition_ast(child, depth + 1, visited_fields)

        elif operator == "not":
            child = condition.get("condition")
            if child is None:
                children = condition.get("conditions") or condition.get("rules")
                if isinstance(children, list) and len(children) == 1:
                    child = children[0]
                else:
                    raise RuleConfigurationError("operator 'not' requires exactly one child condition")
            if not isinstance(child, dict):
                raise RuleConfigurationError("operator 'not' child condition must be an object")
            cls._validate_condition_ast(child, depth + 1, visited_fields)

        return visited_fields

    @classmethod
    def _normalize_rule(cls, source: Dict[str, Any]) -> Dict[str, Any]:
        rule = dict(source)
        condition = rule.get("condition_json", rule.get("condition"))
        if isinstance(condition, str):
            try: condition = json.loads(condition)
            except json.JSONDecodeError as exc: raise RuleConfigurationError("condition_json must be valid JSON") from exc
        if not isinstance(condition, dict): raise RuleConfigurationError("condition_json must be an object")
        serialized = json.dumps(condition)
        if len(serialized.encode("utf-8")) > MAX_SERIALIZED_RULE_SIZE:
            raise RuleConfigurationError(
                f"condition serialized size {len(serialized.encode('utf-8'))} bytes exceeds maximum permitted {MAX_SERIALIZED_RULE_SIZE} bytes"
            )
        cls._validate_condition_ast(condition, depth=0)
        operator = str(condition.get("operator", condition.get("type", ""))).lower()
        condition["operator"] = operator
        rule["condition_json"] = condition
        for required in ("rule_id", "version"):
            if rule.get(required) in (None, ""): raise RuleConfigurationError(f"missing {required}")
        rule["status"] = str(rule.get("status", "ACTIVE")).upper()
        if rule["status"] not in {"DRAFT", "PENDING_APPROVAL", "ACTIVE", "RETIRED"}: raise RuleConfigurationError("invalid rule status")
        rule["evaluation_phase"] = str(rule.get("evaluation_phase", "PRE_CHECK")).upper()
        if rule["evaluation_phase"] not in {"PRE_CHECK", "POST_CHECK"}: raise RuleConfigurationError("invalid evaluation_phase")
        rule["missing_behavior"] = str(rule.get("missing_behavior", "FAIL")).upper()
        rule["invalid_type_behavior"] = str(rule.get("invalid_type_behavior", "FAIL")).upper()
        rule["on_fail_action"] = str(rule.get("on_fail_action", "BLOCK")).upper()
        if rule["missing_behavior"] not in {"FAIL", "WARNING", "SKIP"}: raise RuleConfigurationError("invalid missing_behavior")
        if rule["invalid_type_behavior"] not in {"FAIL", "WARNING"}: raise RuleConfigurationError("invalid invalid_type_behavior")
        if rule["on_fail_action"] not in BLOCKING_ACTIONS | {"WARNING", "FINDING_ONLY"}: raise RuleConfigurationError("invalid on_fail_action")
        jurisdiction = rule.get("jurisdiction", rule.get("zone"))
        rule["jurisdiction"] = str(jurisdiction or "UNSCOPED").strip().upper()
        rule["runtime_mode"] = str(rule.get("runtime_mode", "ENFORCED")).upper()
        if rule["runtime_mode"] not in {"ENFORCED", "SHADOW"}: raise RuleConfigurationError("invalid runtime_mode")
        return rule

    @classmethod
    def _validate_snapshot(cls, rules: Sequence[Dict[str, Any]]) -> None:
        active = [r for r in rules if r["status"] == "ACTIVE"]
        for index, left in enumerate(active):
            for right in active[index + 1:]:
                scope_l = (left["rule_id"], left["jurisdiction"], left.get("dataset_id", "*"), left.get("country") or "")
                scope_r = (right["rule_id"], right["jurisdiction"], right.get("dataset_id", "*"), right.get("country") or "")
                if scope_l == scope_r and cls._overlap(left, right):
                    raise RuleConfigurationError(f"overlapping active versions for {left['rule_id']}")

    @classmethod
    def _overlap(cls, a: Dict[str, Any], b: Dict[str, Any]) -> bool:
        low_a, low_b = cls._parse_time(a.get("effective_from")), cls._parse_time(b.get("effective_from"))
        high_a, high_b = cls._parse_time(a.get("effective_to")), cls._parse_time(b.get("effective_to"))
        floor = datetime.min.replace(tzinfo=timezone.utc); ceiling = datetime.max.replace(tzinfo=timezone.utc)
        return max(low_a or floor, low_b or floor) < min(high_a or ceiling, high_b or ceiling)

    @staticmethod
    def _parse_time(value: Any) -> Optional[datetime]:
        if value in (None, ""): return None
        if isinstance(value, datetime): parsed = value
        else: parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    @classmethod
    def _fields(cls, c: Dict[str, Any]) -> List[str]:
        names = []
        for key in ("field", "column", "left_field", "right_field", "latitude_field", "longitude_field"):
            if c.get(key): names.append(str(c[key]))
        names.extend(str(x) for x in (c.get("fields") or c.get("components") or []))
        op = str(c.get("operator", c.get("type", ""))).lower()
        if op in {"all", "any"}:
            for child in (c.get("conditions") or c.get("rules") or []):
                names.extend(cls._fields(child))
        elif op == "not":
            child = c.get("condition")
            if child is None:
                children = c.get("conditions") or c.get("rules") or []
                if children:
                    child = children[0]
            if child:
                names.extend(cls._fields(child))
        return list(dict.fromkeys(n for n in names if n != "*"))

    @staticmethod
    def _number(value: Any) -> float:
        if isinstance(value, bool): raise TypeError("boolean is not numeric")
        result = float(value)
        if not math.isfinite(result): raise ValueError("number must be finite")
        return result

    @staticmethod
    def _point_in_polygon(x: float, y: float, polygon: Sequence[Sequence[float]]) -> bool:
        if len(polygon) < 3: raise ValueError("polygon requires at least three points")
        inside = False
        j = len(polygon) - 1
        for i in range(len(polygon)):
            xi, yi = float(polygon[i][0]), float(polygon[i][1]); xj, yj = float(polygon[j][0]), float(polygon[j][1])
            intersects = (yi > y) != (yj > y) and x <= (xj-xi)*(y-yi)/(yj-yi) + xi
            if intersects: inside = not inside
            j = i
        return inside

    @staticmethod
    def rule_key(rule: Dict[str, Any]) -> str:
        return f"{rule['rule_id']}@{rule['version']}"
