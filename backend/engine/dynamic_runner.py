"""
DataTrust OS: Generic Dynamic Rule Runner (Airflow Runner Core)
Demonstrates Zero-Code Adaptation:
Reads field process configurations directly from PostgreSQL / metadata models
and dynamically executes treatments and validations across Bronze -> Silver / Quarantine.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import uuid

from backend.database.models import (
    FieldProcessConfigModel,
    ExecutionPhase,
    OnFailAction,
    QuarantineRecordModel,
    QuarantineStatus
)
from backend.engine.operation_handlers import execute_operation
from backend.engine.quarantine_manager import QuarantineManager, compute_lineage_hash


class PipelineRunResult:
    def __init__(self, run_id: str, dataset_id: str):
        self.run_id = run_id
        self.dataset_id = dataset_id
        self.scanned_count: int = 0
        self.silver_count: int = 0
        self.quarantine_count: int = 0
        self.silver_records: List[Dict[str, Any]] = []
        self.quarantine_records: List[QuarantineRecordModel] = []
        self.started_at: datetime = datetime.now(timezone.utc)
        self.ended_at: Optional[datetime] = None

    def finish(self):
        self.ended_at = datetime.now(timezone.utc)


class DynamicRuleRunner:
    def __init__(self, quarantine_manager: Optional[QuarantineManager] = None):
        self.active_rules: Dict[str, List[FieldProcessConfigModel]] = {}  # dataset_id -> List[rules]
        self.quarantine_manager = quarantine_manager or QuarantineManager()

    def register_rule(self, rule: FieldProcessConfigModel):
        """Đăng ký/Nạp cấu hình rule động mới vào runner."""
        if not rule.is_active:
            return
        if rule.dataset_id not in self.active_rules:
            self.active_rules[rule.dataset_id] = []
        # Replace if existing config_id
        self.active_rules[rule.dataset_id] = [r for r in self.active_rules[rule.dataset_id] if r.config_id != rule.config_id]
        self.active_rules[rule.dataset_id].append(rule)
        # Sắp xếp thứ tự thực thi theo execution_order
        self.active_rules[rule.dataset_id].sort(key=lambda r: (r.execution_phase.value, r.execution_order))

    def load_rules(self, rules: List[FieldProcessConfigModel]):
        """Nạp danh sách rule từ database."""
        for r in rules:
            self.register_rule(r)

    def run_pipeline(
        self,
        dataset_id: str,
        bronze_records: List[Dict[str, Any]],
        run_id: Optional[str] = None
    ) -> PipelineRunResult:
        """
        Điều phối xử lý một batch dữ liệu Bronze theo danh sách dynamic rules đã nạp.
        Phân tách bản ghi sạch vào Silver và bản ghi vi phạm vào Quarantine.
        """
        run_id = run_id or f"run_{uuid.uuid4().hex[:12]}"
        result = PipelineRunResult(run_id=run_id, dataset_id=dataset_id)
        rules = self.active_rules.get(dataset_id, [])

        pre_rules = [r for r in rules if r.execution_phase == ExecutionPhase.PRE_CHECK]
        treatment_rules = [r for r in rules if r.execution_phase == ExecutionPhase.TREATMENT]
        post_rules = [r for r in rules if r.execution_phase == ExecutionPhase.POST_CHECK]

        for raw_item in bronze_records:
            result.scanned_count += 1
            # Copy nguyên bản raw record để chuyển đổi mà không làm hỏng raw payload gốc
            current_record = dict(raw_item)
            item_failed = False
            fail_reason = ""
            fail_column = ""
            fail_rule_id = ""
            fail_severity = None
            pk_val = str(current_record.get(f"{dataset_id[:-1]}_id") or current_record.get("id") or current_record.get("trip_id") or uuid.uuid4())

            # --- PHASE 1: PRE-CHECK ---
            for rule in pre_rules:
                val = current_record.get(rule.column_name)
                trans_val, is_valid, err = execute_operation(rule.operation_id, val, rule.params_json)
                if not is_valid:
                    item_failed = True
                    fail_reason = f"Pre-check failed ({rule.expression_display or rule.config_id}): {err}"
                    fail_column = rule.column_name
                    fail_rule_id = rule.config_id
                    fail_severity = rule.severity
                    break

            # --- PHASE 2: TREATMENT (Masking, Redacting, Generalizing) ---
            if not item_failed:
                for rule in treatment_rules:
                    if rule.column_name in current_record:
                        val = current_record.get(rule.column_name)
                        trans_val, is_valid, err = execute_operation(rule.operation_id, val, rule.params_json)
                        if not is_valid:
                            item_failed = True
                            fail_reason = f"Treatment failed ({rule.config_id}): {err}"
                            fail_column = rule.column_name
                            fail_rule_id = rule.config_id
                            fail_severity = rule.severity
                            break
                        # Gán giá trị sau khi đã xử lý theo treatment action
                        current_record[rule.column_name] = trans_val

            # --- PHASE 3: POST-CHECK (Deterministic Quality & Boundaries) ---
            if not item_failed:
                for rule in post_rules:
                    val = current_record.get(rule.column_name)
                    trans_val, is_valid, err = execute_operation(rule.operation_id, val, rule.params_json)
                    if not is_valid:
                        item_failed = True
                        fail_reason = f"Post-check quality failed ({rule.expression_display or rule.config_id}): {err}"
                        fail_column = rule.column_name
                        fail_rule_id = rule.config_id
                        fail_severity = rule.severity
                        break

            # --- ROUTING: SILVER VS QUARANTINE ---
            if item_failed:
                result.quarantine_count += 1
                q_rec = self.quarantine_manager.record_quarantine(
                    run_id=run_id,
                    dataset_id=dataset_id,
                    source_table=f"bronze.{dataset_id}_raw",
                    source_row_pk=pk_val,
                    raw_record=raw_item,
                    violation_column=fail_column,
                    violation_rule_id=fail_rule_id,
                    violation_reason=fail_reason,
                    severity=fail_severity
                )
                result.quarantine_records.append(q_rec)
            else:
                result.silver_count += 1
                current_record["_run_id"] = run_id
                current_record["lineage_hash"] = compute_lineage_hash(current_record)
                result.silver_records.append(current_record)

        result.finish()
        return result
