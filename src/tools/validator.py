import re
from typing import Any, Dict, List, Optional
import pandas as pd

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
