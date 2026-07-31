import uuid
from typing import Any, Dict, List, Optional
from src.models.schemas import ColumnProfile, DataProfile, QualityRule, RuleProposal, ValidationResult


def profile_tool(table_name: str, sample_aggregates: Optional[Dict[str, Any]] = None) -> DataProfile:
    """Profiles a dataset to return structured column aggregates and statistics.
    
    CRITICAL: Returns metadata and aggregate statistics ONLY. No raw row data is returned.
    """
    sample_aggregates = sample_aggregates or {}
    
    default_columns = {
        "id": ColumnProfile(
            column_name="id",
            data_type="INTEGER",
            total_count=1000,
            null_count=0,
            null_percentage=0.0,
            distinct_count=1000,
            min_val=1,
            max_val=1000,
        ),
        "email": ColumnProfile(
            column_name="email",
            data_type="VARCHAR(255)",
            total_count=1000,
            null_count=15,
            null_percentage=1.5,
            distinct_count=985,
            stats={"domain_counts": {"gmail.com": 600, "yahoo.com": 385}},
        ),
        "age": ColumnProfile(
            column_name="age",
            data_type="INTEGER",
            total_count=1000,
            null_count=50,
            null_percentage=5.0,
            distinct_count=65,
            min_val=18,
            max_val=85,
            stats={"mean": 42.3, "std": 14.2},
        ),
        "status": ColumnProfile(
            column_name="status",
            data_type="VARCHAR(50)",
            total_count=1000,
            null_count=0,
            null_percentage=0.0,
            distinct_count=3,
            stats={"allowed_values": ["active", "inactive", "pending"]},
        ),
    }

    if sample_aggregates.get("columns"):
        columns = {}
        for col_name, col_info in sample_aggregates["columns"].items():
            if isinstance(col_info, ColumnProfile):
                columns[col_name] = col_info
            elif isinstance(col_info, dict):
                columns[col_name] = ColumnProfile(**col_info)
        total_rows = sample_aggregates.get("total_rows", 1000)
    else:
        columns = default_columns
        total_rows = 1000

    return DataProfile(
        table_name=table_name,
        total_rows=total_rows,
        columns=columns,
        schema_summary=f"Table '{table_name}' with {len(columns)} columns and {total_rows} total rows.",
    )


def validate_tool(rules: List[Dict[str, Any]], data_profile: Dict[str, Any]) -> ValidationResult:
    """Validates proposed data quality rules against data profile aggregates and syntax rules."""
    violations = []
    passed = []
    failed = []

    profile_cols = data_profile.get("columns", {})

    for idx, r in enumerate(rules):
        rule_id = r.get("rule_id", f"rule_{idx+1}")
        col = r.get("column") or r.get("target_column") or ""
        rule_type = r.get("rule_type", "")
        params = r.get("params") or r.get("parameters") or {}

        if col and col not in profile_cols:
            failed.append(rule_id)
            violations.append({
                "rule_id": rule_id,
                "column": col,
                "reason": f"Column '{col}' does not exist in dataset profile.",
            })
            continue

        col_profile = profile_cols.get(col, {})
        if isinstance(col_profile, dict):
            col_null_pct = col_profile.get("null_percentage") or col_profile.get("null_pct") or 0.0
            col_min = col_profile.get("min_val") if col_profile.get("min_val") is not None else col_profile.get("min")
            col_max = col_profile.get("max_val") if col_profile.get("max_val") is not None else col_profile.get("max")
        else:
            col_null_pct = getattr(col_profile, "null_percentage", getattr(col_profile, "null_pct", 0.0))
            col_min = getattr(col_profile, "min_val", getattr(col_profile, "min", None))
            col_max = getattr(col_profile, "max_val", getattr(col_profile, "max", None))

        if rule_type == "not_null" and col_null_pct > 10.0:
            failed.append(rule_id)
            violations.append({
                "rule_id": rule_id,
                "column": col,
                "reason": f"Rule 'not_null' fails because column '{col}' has high null rate ({col_null_pct}%).",
            })
            continue

        if rule_type == "range":
            min_param = params.get("min")
            max_param = params.get("max")
            if min_param is not None and col_min is not None and col_min < min_param:
                failed.append(rule_id)
                violations.append({
                    "rule_id": rule_id,
                    "column": col,
                    "reason": f"Range min bound ({min_param}) exceeds observed data min ({col_min}).",
                })
                continue
            if max_param is not None and col_max is not None and col_max > max_param:
                failed.append(rule_id)
                violations.append({
                    "rule_id": rule_id,
                    "column": col,
                    "reason": f"Range max bound ({max_param}) is less than observed data max ({col_max}).",
                })
                continue

        passed.append(rule_id)

    is_valid = len(failed) == 0
    error_msg = f"{len(failed)} rules failed validation." if not is_valid else ""

    return ValidationResult(
        is_valid=is_valid,
        rules_evaluated=len(rules),
        passed_rules=passed,
        failed_rules=failed,
        violations=violations,
        error_message=error_msg,
    )


def compile_tool(rules: List[Dict[str, Any]], dialect: str = "ansi") -> Dict[str, Any]:
    """Compiles rules into SQL WHERE clauses or executable expressions."""
    compiled_sqls = []
    for r in rules:
        col = r.get("column") or r.get("target_column") or ""
        rule_type = r.get("rule_type", "")
        params = r.get("params") or r.get("parameters") or {}
        
        if rule_type == "not_null":
            sql = f'"{col}" IS NOT NULL'
        elif rule_type == "range":
            min_v = params.get("min", "-INF")
            max_v = params.get("max", "+INF")
            sql = f'"{col}" BETWEEN {min_v} AND {max_v}'
        elif rule_type == "allowed_values":
            vals = ", ".join([f"'{v}'" if isinstance(v, str) else str(v) for v in params.get("values", [])])
            sql = f'"{col}" IN ({vals})'
        elif rule_type == "unique":
            sql = f'COUNT("{col}") = COUNT(DISTINCT "{col}")'
        else:
            sql = f'"{col}" IS NOT NULL -- custom rule {rule_type}'
            
        compiled_sqls.append({"rule_id": r.get("rule_id", ""), "column": col, "sql_expression": sql})

    return {"status": "success", "dialect": dialect, "compiled_rules": compiled_sqls}


def test_tool(rules: List[Dict[str, Any]], data_profile: Dict[str, Any]) -> Dict[str, Any]:
    """Tests compiled rules against data profile statistics to estimate pass/fail rates."""
    val_res = validate_tool(rules, data_profile)
    return {
        "status": "tested",
        "passed_count": len(val_res.passed_rules),
        "failed_count": len(val_res.failed_rules),
        "estimated_pass_rate": 1.0 if val_res.is_valid else len(val_res.passed_rules) / max(1, val_res.rules_evaluated),
        "details": val_res.model_dump(),
    }


test_tool.__test__ = False  # Prevent pytest from collecting this function as a test fixture


def request_context_tool(target_schema_name: str) -> Dict[str, Any]:
    """Fetches schema definitions, target metadata, and domain constraints."""
    return {
        "target_schema": target_schema_name,
        "constraints": {
            "primary_key": "id",
            "required_columns": ["id", "status"],
            "business_rules": "All active users must have valid email addresses.",
        },
        "description": "Standard production user table schema specifications.",
    }


def submit_review_tool(proposal_id: str, rules: List[Dict[str, Any]], reasoning: str) -> Dict[str, Any]:
    """Submits rule proposal for human-in-the-loop (HITL) review."""
    p_id = proposal_id or f"prop_{uuid.uuid4().hex[:8]}"
    parsed_rules = []
    for idx, r in enumerate(rules):
        if isinstance(r, QualityRule):
            parsed_rules.append(r)
        elif isinstance(r, dict):
            if "rule_id" not in r:
                r["rule_id"] = f"rule_{idx+1}"
            parsed_rules.append(QualityRule(**r))
            
    proposal = RuleProposal(
        proposal_id=p_id,
        rules=parsed_rules,
        reasoning=reasoning,
        confidence=1.0,
    )
    return {
        "status": "READY_FOR_REVIEW",
        "proposal_id": p_id,
        "proposal": proposal.model_dump(),
    }


def abstain_tool(reason: str) -> Dict[str, Any]:
    """Abstains from proposing rules due to low confidence or repeated failure."""
    return {
        "status": "ABSTAINED",
        "reason": reason,
    }


TOOL_WHITELIST = {
    "profile": profile_tool,
    "validate": validate_tool,
    "compile": compile_tool,
    "test": test_tool,
    "request_context": request_context_tool,
    "submit_review": submit_review_tool,
    "abstain": abstain_tool,
}
