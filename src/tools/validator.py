import re
from typing import Any, Dict, List, Literal, Optional

import pandas as pd
from pydantic import BaseModel

from src.models.schemas import Proposal, RuleFamily, RuleSpec, ValidationResult


class Validator:
    """
    Validator performs deterministic structural, semantic, and type-compatibility
    validation on RuleSpec objects, DataFrames, and Proposal packages.
    """

    ALLOWED_FAMILIES = {f.value for f in RuleFamily}

    def __init__(self, rules: Optional[List[RuleSpec]] = None):
        self.default_rules = rules or []

    def validate(
        self,
        rules_or_df: Any = None,
        rules: Optional[List[RuleSpec]] = None,
        target_columns: Optional[List[str]] = None,
    ) -> ValidationResult:
        if isinstance(rules_or_df, pd.DataFrame):
            df = rules_or_df
            target_rules = rules if rules is not None else self.default_rules
            invalid_indices_set = set()
            errors = []
            error_summary = {}

            for rule in target_rules:
                rule_invalid_indices = []
                target_col = rule.target_column or rule.target_field

                if rule.rule_type in ("not_null", "null") and target_col and target_col in df.columns:
                    null_mask = df[target_col].isnull()
                    rule_invalid_indices = list(df.index[null_mask])
                elif rule.rule_type == "range" and target_col and target_col in df.columns:
                    series = pd.to_numeric(df[target_col], errors="coerce")
                    min_v = rule.parameters.get("min")
                    max_v = rule.parameters.get("max")
                    mask = pd.Series(False, index=df.index)
                    if min_v is not None:
                        mask |= series < min_v
                    if max_v is not None:
                        mask |= series > max_v
                    rule_invalid_indices = list(df.index[mask])
                elif rule.rule_type == "unique" and target_col and target_col in df.columns:
                    dup_mask = df.duplicated(subset=[target_col], keep="first")
                    rule_invalid_indices = list(df.index[dup_mask])

                for idx in rule_invalid_indices:
                    invalid_indices_set.add(idx)
                    errors.append({
                        "row_idx": int(idx),
                        "rule_id": rule.rule_id,
                        "column": target_col,
                    })
                error_summary[rule.rule_id] = len(rule_invalid_indices)

            invalid_list = sorted(list(invalid_indices_set))
            return ValidationResult(
                is_valid=len(invalid_list) == 0,
                valid=len(invalid_list) == 0,
                total_rows=len(df),
                invalid_rows_count=len(invalid_list),
                invalid_indices=invalid_list,
                error_summary=error_summary,
                errors=errors,
            )
        else:
            target_rules = (
                rules_or_df
                if rules_or_df is not None
                else (rules if rules is not None else self.default_rules)
            )
            all_errors = []
            all_warnings = []
            for r in target_rules:
                res = self.validate_rule(r, target_columns=target_columns)
                all_errors.extend(res.errors)
                all_warnings.extend(res.warnings)
            return ValidationResult(
                is_valid=len(all_errors) == 0,
                valid=len(all_errors) == 0,
                errors=all_errors,
                warnings=all_warnings,
            )

    def validate_rule(
        self, rule: RuleSpec, target_columns: Optional[List[str]] = None
    ) -> ValidationResult:
        errors: List[str] = []
        warnings: List[str] = []

        family_str = rule.family.value if isinstance(rule.family, RuleFamily) else str(rule.family)
        if family_str not in self.ALLOWED_FAMILIES:
            errors.append(f"Invalid rule family '{family_str}'. Must be one of {self.ALLOWED_FAMILIES}")

        target_fld = rule.target_field or rule.target_column or rule.column
        if not target_fld and family_str not in ("unique", "duplicate"):
            errors.append("RuleSpec target_field cannot be empty.")
        elif target_columns and target_fld not in target_columns and family_str != "cross_field":
            warnings.append(f"Target field '{target_fld}' not found in known schema columns.")

        params = rule.parameters or rule.params or {}
        if family_str == "range":
            if "min" not in params and "max" not in params:
                errors.append("Range rule requires at least 'min' or 'max' in parameters.")
            else:
                if "min" in params and "max" in params:
                    try:
                        if float(params["min"]) > float(params["max"]):
                            errors.append(f"Range min ({params['min']}) cannot be greater than max ({params['max']}).")
                    except (ValueError, TypeError):
                        pass
        elif family_str == "format":
            if "pattern" not in params and "date_format" not in params and "regex" not in params:
                errors.append("Format rule requires 'pattern', 'regex', or 'date_format' parameter.")

        valid = len(errors) == 0
        return ValidationResult(is_valid=valid, valid=valid, errors=errors, warnings=warnings)

    def validate_proposal(
        self,
        proposal: Proposal,
        target_schema: Optional[Dict[str, Any]] = None,
        source_columns: Optional[List[str]] = None,
    ) -> ValidationResult:
        all_errors: List[str] = []
        all_warnings: List[str] = []

        if not proposal.proposal_id:
            all_errors.append("Proposal missing proposal_id.")

        target_cols = None
        if target_schema and "columns" in target_schema:
            target_cols = [c["name"] for c in target_schema["columns"] if "name" in c]
        elif source_columns:
            target_cols = source_columns

        for i, rule in enumerate(proposal.rules):
            res = self.validate_rule(rule, target_columns=target_cols)
            if not res.valid:
                for err in res.errors:
                    all_errors.append(f"Rule[{i}] ({rule.target_field}): {err}")
            for warn in res.warnings:
                all_warnings.append(f"Rule[{i}] ({rule.target_field}): {warn}")

        valid = len(all_errors) == 0
        return ValidationResult(is_valid=valid, valid=valid, errors=all_errors, warnings=all_warnings)


# ---------------------------------------------------------------------------
# Proposal gate (Wave 2 Task 2.1) — validate before HITL queue
# ---------------------------------------------------------------------------


class RuleValidation(BaseModel):
    status: Literal["VALIDATED", "NEEDS_REVIEW"]
    reasons: list[str]
    sql_compiles: bool
    column_exists: bool
    sandbox_ran: bool
    always_true: bool | None = None
    always_false: bool | None = None
    duplicate_of: str | None = None
    quarantine_rate_preview: float | None = None


_IDENT_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\b")
_SQL_KEYWORDS = {
    "and", "or", "not", "between", "in", "is", "null", "like", "case", "when",
    "then", "else", "end", "true", "false", "as", "cast", "coalesce", "abs",
    "lower", "upper", "trim", "length", "round", "where", "select", "from",
}


def _extract_idents(expr: str) -> list[str]:
    out: list[str] = []
    for m in _IDENT_RE.finditer(expr or ""):
        tok = m.group(1)
        if tok.lower() in _SQL_KEYWORDS:
            continue
        if tok.replace(".", "", 1).isdigit():
            continue
        out.append(tok)
    return out


def _row_satisfies(spec, row: dict) -> bool | None:
    """Evaluate a compiled RuleSpec against one sample row. None if unevaluable."""
    col = getattr(spec, "column", None)
    if not col:
        return None
    if col not in row:
        return None
    val = row.get(col)
    op = getattr(spec, "operator", None)
    args = list(getattr(spec, "arguments", []) or [])
    try:
        if op == "not_null":
            return val is not None and str(val).strip() != ""
        if val is None:
            return False
        num = float(val) if not isinstance(val, (int, float)) else float(val)
        if op == "gt":
            return num > float(args[0])
        if op == "lt":
            return num < float(args[0])
        if op == "gte":
            return num >= float(args[0])
        if op == "lte":
            return num <= float(args[0])
        if op == "eq":
            return val == args[0] or num == float(args[0])
        if op == "neq":
            return val != args[0]
        if op == "between":
            return float(args[0]) <= num <= float(args[1])
        if op == "in":
            return val in args or num in [float(a) for a in args if isinstance(a, (int, float))]
    except (TypeError, ValueError, IndexError):
        return None
    return None


def validate_proposed_rule(
    rule: dict,
    *,
    columns: list[str],
    sample_rows: list[dict],
    approved: list[dict],
) -> RuleValidation:
    """Gate proposed rules before HITL. Marks NEEDS_REVIEW on soft failures."""
    reasons: list[str] = []
    expr = str(rule.get("rule_expression") or rule.get("expression") or "").strip()
    col_set = {c.lower(): c for c in (columns or [])}

    # --- column existence for rule_expression ---
    idents = _extract_idents(expr)
    missing_cols = [i for i in idents if i.lower() not in col_set]
    # Prefer primary target (first ident) when present
    column_exists = len(missing_cols) == 0 and bool(idents) if columns else True
    if columns and missing_cols:
        column_exists = False
        reasons.append(f"referenced column(s) not in schema: {', '.join(missing_cols)}")
    elif columns and not idents and expr:
        column_exists = False
        reasons.append("no column identifier found in rule_expression")

    # --- compile via compiler.py → rule_executor dialect ---
    from src.tools.compiler import try_compile_rule_expression

    sql_compiles, spec, compile_err = try_compile_rule_expression(expr)
    if not sql_compiles:
        reasons.append(f"expression does not compile: {compile_err or 'unknown'}")

    # --- remediation column ---
    remed = str(rule.get("remediation_sql_expr") or "").strip()
    remed_action = str(rule.get("remediation_action") or "NO_OP").strip().upper()
    if remed and columns:
        remed_idents = _extract_idents(remed)
        remed_missing = [i for i in remed_idents if i.lower() not in col_set]
        if remed_missing:
            reasons.append(f"remediation column missing: {', '.join(remed_missing)}")
    elif remed_action and remed_action not in ("NO_OP", "", "NONE") and not remed:
        reasons.append("remediation column missing: remediation_sql_expr empty")

    # --- duplicate of approved expression ---
    duplicate_of = None
    expr_norm = " ".join(expr.lower().split())
    for a in approved or []:
        a_expr = str(a.get("rule_expression") or a.get("expression") or "").strip()
        if a_expr and " ".join(a_expr.lower().split()) == expr_norm:
            duplicate_of = str(a.get("id") or a.get("rule_id") or a.get("rule_name") or a_expr)
            reasons.append(f"duplicate of approved expression: {duplicate_of}")
            break

    # --- sandbox on sample_rows ---
    always_true = None
    always_false = None
    quarantine_rate_preview = None
    sandbox_ran = False
    if sample_rows and sql_compiles and spec is not None:
        results = []
        for row in sample_rows:
            sat = _row_satisfies(spec, row)
            if sat is not None:
                results.append(sat)
        if results:
            sandbox_ran = True
            always_true = all(results)
            always_false = not any(results)
            fail_count = sum(1 for r in results if not r)
            quarantine_rate_preview = fail_count / len(results)
            if always_true:
                reasons.append("expression always true on sample_rows")
            if always_false:
                reasons.append("expression always false on sample_rows")

    # explicit quarantine_rate_preview on rule dict wins if provided
    if rule.get("quarantine_rate_preview") is not None:
        try:
            quarantine_rate_preview = float(rule["quarantine_rate_preview"])
        except (TypeError, ValueError):
            pass

    rationale = str(
        rule.get("rationale")
        or rule.get("why_proposed")
        or rule.get("problem_discovered")
        or ""
    ).strip()
    if quarantine_rate_preview is not None and quarantine_rate_preview > 0.35 and not rationale:
        reasons.append(
            f"quarantine_rate_preview {quarantine_rate_preview:.2f} > 0.35 without rationale"
        )

    status = "NEEDS_REVIEW" if reasons else "VALIDATED"
    return RuleValidation(
        status=status,
        reasons=reasons,
        sql_compiles=sql_compiles,
        column_exists=column_exists,
        sandbox_ran=sandbox_ran,
        always_true=always_true,
        always_false=always_false,
        duplicate_of=duplicate_of,
        quarantine_rate_preview=quarantine_rate_preview,
    )

