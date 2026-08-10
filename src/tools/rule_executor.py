import hashlib
import json
import re
import uuid
from typing import Any, Dict, List, Literal, Union
from pydantic import BaseModel, Field

from src.db.connection import get_db
from src.tools.base import BaseTool


class RuleSpec(BaseModel):
    table: str
    column: str
    operator: Literal["gt", "lt", "gte", "lte", "eq", "neq", "between", "in", "not_null", "regex"]
    arguments: List[Union[int, float, str]] = Field(default_factory=list)
    severity: str = "error"


FORBIDDEN_SQL_PATTERNS = [
    r"--",
    r"/\*",
    r"\*/",
    r";",
    r"\bselect\b",
    r"\bunion\b",
    r"\binsert\b",
    r"\bupdate\b",
    r"\bdelete\b",
    r"\bdrop\b",
    r"\balter\b",
    r"\bexec\b",
    r"\bexecute\b",
    r"\bscript\b",
    r"\beval\b",
]


def _check_sql_safety(text: str) -> None:
    if not text:
        return
    text_lower = text.lower()
    for pattern in FORBIDDEN_SQL_PATTERNS:
        if re.search(pattern, text_lower):
            raise ValueError(f"Disallowed SQL pattern detected in expression: '{pattern}'")


def _validate_identifier(identifier: str) -> str:
    _check_sql_safety(identifier)
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", identifier):
        raise ValueError(f"Invalid SQL identifier: '{identifier}'")
    return identifier


def compile_rule_spec(spec: RuleSpec) -> str:
    """Compile a RuleSpec into a safe, parameterized SQL clause (e.g. 'WHERE NOT (col BETWEEN ? AND ?)')."""
    _validate_identifier(spec.table)
    col = _validate_identifier(spec.column)

    for arg in spec.arguments:
        if isinstance(arg, str):
            _check_sql_safety(arg)

    op = spec.operator
    args_count = len(spec.arguments)

    if op == "gt":
        if args_count != 1:
            raise ValueError("Operator 'gt' requires 1 argument")
        condition = f"{col} > ?"
    elif op == "lt":
        if args_count != 1:
            raise ValueError("Operator 'lt' requires 1 argument")
        condition = f"{col} < ?"
    elif op == "gte":
        if args_count != 1:
            raise ValueError("Operator 'gte' requires 1 argument")
        condition = f"{col} >= ?"
    elif op == "lte":
        if args_count != 1:
            raise ValueError("Operator 'lte' requires 1 argument")
        condition = f"{col} <= ?"
    elif op == "eq":
        if args_count != 1:
            raise ValueError("Operator 'eq' requires 1 argument")
        condition = f"{col} = ?"
    elif op == "neq":
        if args_count != 1:
            raise ValueError("Operator 'neq' requires 1 argument")
        condition = f"{col} != ?"
    elif op == "between":
        if args_count != 2:
            raise ValueError("Operator 'between' requires 2 arguments")
        condition = f"{col} BETWEEN ? AND ?"
    elif op == "in":
        if args_count < 1:
            raise ValueError("Operator 'in' requires at least 1 argument")
        placeholders = ", ".join(["?"] * args_count)
        condition = f"{col} IN ({placeholders})"
    elif op == "not_null":
        condition = f"{col} IS NOT NULL"
    elif op == "regex":
        if args_count != 1:
            raise ValueError("Operator 'regex' requires 1 argument")
        condition = f"regexp_matches({col}, ?)"
    else:
        raise ValueError(f"Unsupported operator: '{op}'")

    return f"WHERE NOT ({condition})"


def _parse_val(val_str: str) -> Union[int, float, str]:
    val_str = val_str.strip()
    if (val_str.startswith("'") and val_str.endswith("'")) or (val_str.startswith('"') and val_str.endswith('"')):
        return val_str[1:-1]
    try:
        if "." in val_str:
            return float(val_str)
        return int(val_str)
    except ValueError:
        return val_str


class RuleExecutorTool(BaseTool):
    name = "rule_executor"
    description = "Execute an approved quality rule against its target table. Violations are quarantined. Supports dry_run mode for preview."
    input_schema = {
        "type": "object",
        "properties": {
            "rule_id": {"type": "string", "description": "ID of the approved quality rule to execute"},
            "dry_run": {"type": "boolean", "description": "If true, only count violations without quarantining", "default": True},
            "snapshot_id": {"type": "string", "description": "Snapshot ID for quarantine lineage"},
            "rule_version_id": {"type": "string", "description": "Rule version ID for quarantine lineage"}
        },
        "required": ["rule_id"]
    }

    def execute(self, input_data: dict) -> dict:
        rule_id = input_data["rule_id"]
        dry_run = input_data.get("dry_run", True)
        snapshot_id = input_data.get("snapshot_id")
        rule_version_id = input_data.get("rule_version_id")
        db = get_db()
        conn = db.get_connection()

        # Execute rule, quarantine insertion, and audit logging inside a single transaction boundary
        conn.execute("BEGIN TRANSACTION")

        try:
            rules = conn.execute("SELECT id, rule_name, rule_type, rule_expression, status, snapshot_id FROM quality_rules WHERE id = ?", [rule_id]).fetchall()
            if not rules:
                conn.execute("ROLLBACK")
                return {"error": f"Rule '{rule_id}' not found", "records_checked": 0, "violations_found": 0, "quarantined_count": 0, "clean_count": 0}

            rule = rules[0]
            rule_id_val, rule_name, rule_type, expression, status = rule[0], rule[1], rule[2], rule[3], rule[4]
            rule_snapshot_id = rule[5] if len(rule) > 5 else None

            if status != "approved" and not dry_run:
                conn.execute("ROLLBACK")
                return {"error": f"Rule '{rule_id}' status is '{status}', must be 'approved' to execute", "records_checked": 0, "violations_found": 0, "quarantined_count": 0, "clean_count": 0}

            spec = self._parse_rule_spec(expression)
            where_clause = compile_rule_spec(spec)
            target_table = spec.table

            effective_snapshot_id = snapshot_id or rule_snapshot_id or "snap_001"
            effective_rule_version_id = rule_version_id or f"{rule_id}_v1"

            # Count total records
            total = conn.execute(f"SELECT COUNT(*) FROM {target_table}").fetchall()[0][0]
            # Count violations
            violation_query = f"SELECT COUNT(*) FROM {target_table} {where_clause}"
            violations = conn.execute(violation_query, spec.arguments).fetchall()[0][0]
            clean = total - violations

            quarantined = 0
            if not dry_run and violations > 0:
                violation_rows = conn.execute(f"SELECT * FROM {target_table} {where_clause} LIMIT 1000", spec.arguments).fetchall()
                cols = [desc[0] for desc in conn.description] if conn.description else []

                quarantine_records = []
                for row in violation_rows:
                    row_dict = dict(zip(cols, row)) if cols else {}
                    source_row_id = row_dict.get("id") or row_dict.get("row_id") or row[0]
                    q_id = str(uuid.uuid4())[:8]
                    orig_data_json = json.dumps(row_dict, default=str)
                    lineage_str = f"{effective_snapshot_id}:{effective_rule_version_id}:{source_row_id}"
                    lineage_hash = hashlib.sha256(lineage_str.encode("utf-8")).hexdigest()[:16]

                    quarantine_records.append((
                        q_id,
                        effective_snapshot_id,
                        target_table,
                        source_row_id,
                        rule_id,
                        effective_rule_version_id,
                        f"Violated rule: {rule_name} ({expression})",
                        orig_data_json,
                        lineage_hash
                    ))

                # Process batch insertions in chunks of 500 rows per batch
                CHUNK_SIZE = 500
                for i in range(0, len(quarantine_records), CHUNK_SIZE):
                    chunk = quarantine_records[i : i + CHUNK_SIZE]
                    conn.executemany(
                        """
                        INSERT INTO quarantine (
                            id, snapshot_id, source_table, source_row_id, rule_id, rule_version_id, reason, original_data, lineage_hash
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT (snapshot_id, rule_version_id, source_row_id) DO NOTHING
                        """,
                        chunk
                    )
                quarantined = len(quarantine_records)

            conn.execute("COMMIT")

            # Log audit event after transaction commit
            from src.services.audit import AuditService
            try:
                AuditService.log(
                    action="EXECUTE_RULE",
                    actor="agent",
                    target_table=target_table,
                    target_id=rule_id,
                    details={"violations": violations, "quarantined": quarantined, "snapshot_id": effective_snapshot_id, "rule_version_id": effective_rule_version_id},
                    db=db
                )
            except Exception:
                pass

            return {
                "records_checked": total,
                "violations_found": violations,
                "quarantined_count": quarantined,
                "clean_count": clean,
                "rule_name": rule_name,
                "dry_run": dry_run,
                "snapshot_id": effective_snapshot_id,
                "rule_version_id": effective_rule_version_id
            }
        except Exception as e:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            return {"error": str(e), "records_checked": 0, "violations_found": 0, "quarantined_count": 0, "clean_count": 0}

    def _parse_rule_spec(self, expression: str) -> RuleSpec:
        expr = expression.strip()
        _check_sql_safety(expr)

        if expr.startswith("{"):
            data = json.loads(expr)
            if "table" not in data or not data["table"]:
                data["table"] = self._infer_table(expr)
            return RuleSpec(**data)

        # Try regex parsing of raw expressions
        m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s+BETWEEN\s+(.+?)\s+AND\s+(.+)$", expr, re.IGNORECASE)
        if m:
            col, v1, v2 = m.group(1), _parse_val(m.group(2)), _parse_val(m.group(3))
            table = self._infer_table(col)
            return RuleSpec(table=table, column=col, operator="between", arguments=[v1, v2])

        m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s+IS\s+NOT\s+NULL$", expr, re.IGNORECASE)
        if m:
            col = m.group(1)
            table = self._infer_table(col)
            return RuleSpec(table=table, column=col, operator="not_null", arguments=[])

        m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*(>=|<=|>|<|=|!=|<>)\s*(.+)$", expr)
        if m:
            col, op_str, val_str = m.group(1), m.group(2), m.group(3)
            op_map = {">": "gt", "<": "lt", ">=": "gte", "<=": "lte", "=": "eq", "!=": "neq", "<>": "neq"}
            v = _parse_val(val_str)
            table = self._infer_table(col)
            return RuleSpec(table=table, column=col, operator=op_map[op_str], arguments=[v])

        m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s+IN\s*\((.+)\)$", expr, re.IGNORECASE)
        if m:
            col, raw_args = m.group(1), m.group(2)
            args = [_parse_val(a.strip()) for a in raw_args.split(",")]
            table = self._infer_table(col)
            return RuleSpec(table=table, column=col, operator="in", arguments=args)

        raise ValueError(f"Unparseable or unsafe rule expression: '{expression}'")

    def _infer_table(self, expression: str) -> str:
        """Infer target table from rule expression column names."""
        expr_lower = expression.lower()
        if any(k in expr_lower for k in ["temperature", "voltage", "duty_cycle", "station_id", "current_amps"]):
            return "vgreen_telemetry"
        elif any(k in expr_lower for k in ["battery_soc", "cell_temp", "bms_fault", "vehicle_id"]):
            return "vinfast_bms"
        elif any(k in expr_lower for k in ["review_text", "rating", "source"]):
            return "xanhsm_feedback"
        elif any(k in expr_lower for k in ["distance_km", "fare_vnd", "duration_minutes", "trip_id"]):
            return "xanhsm_trips"
        return "xanhsm_feedback"  # default fallback
