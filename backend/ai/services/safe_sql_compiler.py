"""
Safe SQL Compiler for AI Structured Proposals.
Enforces the Evidence-or-Abstain and Strict Parameterization Policy:
1. AI Agent never generates or executes arbitrary free-form SQL.
2. AI Agent only emits structured remediation proposals (dataset, column, operation, params).
3. Backend validates operations against OperationRegistry and column names against strict identifier rules.
4. Generates fully parameterized queries and safe expression strings for policy.data_treatment_rules.
"""

import json
import re
import uuid
from typing import Any, Dict, Optional, Tuple

from backend.engine.operation_registry import OperationRegistry

IDENTIFIER_REGEX = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,62}$")

ALLOWED_OPERATIONS = {
    "ROUND", "ROUND_DECIMAL",
    "MASK", "MASK_PHONE", "MASK_EMAIL", "MASK_NAME", "MASK_CONTACT",
    "HASH", "HASH_SHA256", "HMAC_SHA256",
    "GENERALIZE", "BUCKETIZE",
    "REMOVE", "REDACT", "REDACT_PII_TEXT"
}


class SafeSQLCompiler:
    """
    Validates and safely compiles structured AI remediation proposals
    into parameterized SQL statements and database payloads.
    """

    @classmethod
    def validate_identifier(cls, name: str, field_desc: str = "identifier") -> str:
        """Kiểm tra và khử khuẩn tên bảng/cột chống SQL Injection."""
        if not name or not isinstance(name, str):
            raise ValueError(f"{field_desc} không được để trống hoặc sai kiểu dữ liệu.")
        cleaned = name.strip()
        if not IDENTIFIER_REGEX.match(cleaned):
            raise ValueError(
                f"Giá trị '{cleaned}' không phải là một {field_desc} hợp lệ (chỉ cho phép chữ, số, dấu gạch dưới)."
            )
        return cleaned

    @classmethod
    def validate_proposal(cls, proposal: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Kiểm tra tính hợp lệ của đề xuất cấu trúc từ AI Agent.
        Trả về (True, None) nếu hợp lệ hoặc (False, error_message).
        """
        if not isinstance(proposal, dict):
            return False, "Đề xuất phải là một dictionary có cấu trúc."

        dataset_id = proposal.get("dataset_id")
        column_name = proposal.get("column_name")
        operation_id = proposal.get("operation_id")
        params = proposal.get("params", {})

        if not dataset_id or not column_name or not operation_id:
            return False, "Thiếu trường bắt buộc: 'dataset_id', 'column_name', hoặc 'operation_id'."

        try:
            cls.validate_identifier(dataset_id, "dataset_id")
            cls.validate_identifier(column_name, "column_name")
        except ValueError as e:
            return False, str(e)

        norm_op = operation_id.strip().upper()
        if norm_op not in ALLOWED_OPERATIONS:
            return False, f"Thao tác '{operation_id}' không nằm trong danh mục OperationRegistry cho phép."

        try:
            OperationRegistry.get_handler(norm_op)
        except Exception as e:
            return False, f"Lỗi OperationRegistry: {str(e)}"

        # Validate params
        if not isinstance(params, dict):
            return False, "Tham số 'params' phải là một dictionary."

        if norm_op in ("ROUND", "ROUND_DECIMAL"):
            decimals = params.get("decimals", 2)
            if not isinstance(decimals, int) or decimals < 0 or decimals > 10:
                return False, "Tham số 'decimals' của ROUND phải là số nguyên từ 0 đến 10."

        elif norm_op in ("MASK", "MASK_PHONE"):
            prefix_len = params.get("prefix_len", 3)
            suffix_len = params.get("suffix_len", 2)
            mask_char = params.get("mask_char", "*")
            if not isinstance(prefix_len, int) or prefix_len < 0 or prefix_len > 20:
                return False, "Tham số 'prefix_len' phải là số nguyên từ 0 đến 20."
            if not isinstance(suffix_len, int) or suffix_len < 0 or suffix_len > 20:
                return False, "Tham số 'suffix_len' phải là số nguyên từ 0 đến 20."
            if not isinstance(mask_char, str) or len(mask_char) != 1:
                return False, "Tham số 'mask_char' phải là một ký tự duy nhất."

        elif norm_op in ("HASH", "HASH_SHA256"):
            algo = params.get("algorithm", "sha256").lower()
            if algo not in ("sha256", "sha512", "md5"):
                return False, f"Thuật toán hash '{algo}' không được hỗ trợ."

        elif norm_op in ("GENERALIZE", "BUCKETIZE"):
            level = params.get("level", 10)
            if not isinstance(level, (int, float)) or level <= 0:
                return False, "Tham số 'level' phải là số dương."

        return True, None

    @classmethod
    def compile_sql_expression(cls, operation_id: str, column_name: str, params: Dict[str, Any]) -> str:
        """
        Biên dịch biểu thức hiển thị SQL an toàn (expression_display).
        Identifiers luôn được trích dẫn an toàn trong dấu ngoặc kép.
        """
        clean_col = cls.validate_identifier(column_name, "column_name")
        norm_op = operation_id.strip().upper()

        if norm_op in ("ROUND", "ROUND_DECIMAL"):
            decimals = int(params.get("decimals", 2))
            return f'ROUND(CAST("{clean_col}" AS NUMERIC), {decimals})'

        elif norm_op in ("MASK", "MASK_PHONE"):
            prefix = int(params.get("prefix_len", 3))
            suffix = int(params.get("suffix_len", 2))
            mask_char = str(params.get("mask_char", "*"))
            mask_fill = mask_char * 4
            return f'CONCAT(SUBSTRING("{clean_col}", 1, {prefix}), \'{mask_fill}\', RIGHT("{clean_col}", {suffix}))'

        elif norm_op == "MASK_EMAIL":
            return f'CONCAT(SUBSTRING("{clean_col}", 1, 1), \'***@\', SPLIT_PART("{clean_col}", \'@\', 2))'

        elif norm_op == "MASK_NAME":
            return f'REGEXP_REPLACE("{clean_col}", \'(\\w)\\w+\', \'\\1***\', \'g\')'

        elif norm_op in ("HASH", "HASH_SHA256"):
            return f'ENCODE(DIGEST("{clean_col}" || \':salt\', \'sha256\'), \'hex\')'

        elif norm_op == "HMAC_SHA256":
            return f'HMAC("{clean_col}", \':secret\', \'sha256\')'

        elif norm_op in ("GENERALIZE", "BUCKETIZE"):
            lvl = int(params.get("level", 10))
            return f'CONCAT(FLOOR(CAST("{clean_col}" AS NUMERIC) / {lvl}) * {lvl}, \'-\', (FLOOR(CAST("{clean_col}" AS NUMERIC) / {lvl}) + 1) * {lvl} - 1)'

        elif norm_op in ("REMOVE", "REDACT"):
            return "NULL"

        return f'{norm_op}("{clean_col}")'

    @classmethod
    def compile_treatment_rule_insert(
        cls,
        proposal: Dict[str, Any],
        rule_id: Optional[str] = None,
        rationale: str = "",
        policy_id: Optional[str] = None,
        law_ref: Optional[str] = None,
        author: str = "AI_AGENT"
    ) -> Tuple[str, tuple]:
        """
        Biên dịch đề xuất thành câu lệnh Parameterized SQL INSERT vào bảng policy.data_treatment_rules.
        Tuyệt đối không nối chuỗi (no string interpolation) để ngăn chặn hoàn toàn SQL Injection.
        """
        valid, err = cls.validate_proposal(proposal)
        if not valid:
            raise ValueError(f"Không thể biên dịch đề xuất không hợp lệ: {err}")

        dataset_id = cls.validate_identifier(proposal["dataset_id"], "dataset_id")
        column_name = cls.validate_identifier(proposal["column_name"], "column_name")
        operation_id = proposal["operation_id"].strip().upper()
        params = proposal.get("params", {})

        generated_rule_id = rule_id or f"TREAT_{dataset_id.upper()}_{column_name.upper()}_{uuid.uuid4().hex[:6]}"
        expr_display = cls.compile_sql_expression(operation_id, column_name, params)
        treatment_name = f"Chuẩn hóa {column_name} qua {operation_id}"
        description = f"Quy tắc chuẩn hóa/bảo mật AI đề xuất cho cột {column_name} thuộc dataset {dataset_id}"
        params_json_str = json.dumps(params, ensure_ascii=False)

        sql = """
            INSERT INTO policy.data_treatment_rules (
                rule_id, dataset_id, column_name, operation_id,
                treatment_name, params_json, expression_display, description,
                policy_id, law_ref, jurisdiction, country,
                is_ai_proposed, ai_rationale, status, enforced_by,
                version, effective_from
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, CURRENT_TIMESTAMP
            )
            ON CONFLICT (rule_id, version) DO NOTHING;
        """.strip()

        params_tuple = (
            generated_rule_id,
            dataset_id,
            column_name,
            operation_id,
            treatment_name,
            params_json_str,
            expr_display,
            description,
            policy_id or "AI_AUTO_POLICY",
            law_ref or "Nghị định 13/2023/NĐ-CP",
            "VN",
            "VN",
            True,
            rationale or "Đề xuất khắc phục tự động từ AI Agent qua cơ chế HITL",
            "DRAFT",
            author,
            1
        )

        return sql, params_tuple
