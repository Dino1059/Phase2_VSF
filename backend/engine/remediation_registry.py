"""
DataTrust OS: Remediation Registry & Policy Allowlist
Enforces:
1. Registered active mappings between Lane A detectors, datasets/columns, and OperationRegistry operations.
2. Classification of proposals into EXECUTABLE vs ADVISORY_ONLY.
3. Strict parameter schema allowlisting (prevents unauthorized code/parameter injections).
4. Automated post-remediation compliance verification (Post-Checks).
"""

from typing import Any, Dict, List, Optional, Tuple
from backend.database.models import RemediationRiskLevel


class RemediationRegistry:
    """
    Catalog of approved remediation handlers, parameter schemas, and post-check rules.
    """

    APPROVED_MAPPINGS: List[Dict[str, Any]] = [
        {
            "mapping_id": "MAP-PHONE-MASK",
            "operation_id": "MASK_PHONE",
            "columns": ["customer_contact", "customer_phone", "phone_number", "phone"],
            "datasets": ["ride_hailing_xanh_sm_trips", "trips_clean", "dim_customers", "dim_drivers", "customers_clean"],
            "risk_level": RemediationRiskLevel.LOW,
            "requires_human_input": False,
            "post_check_rules": ["POST_MASK_VERIFIED", "NO_RAW_PHONE_EXPOSURE"],
            "allowed_params": {
                "prefix_len": {"type": int, "min": 0, "max": 10, "default": 3},
                "suffix_len": {"type": int, "min": 0, "max": 10, "default": 2},
                "mask_char": {"type": str, "allowed": ["*", "#", "x"], "default": "*"},
            },
            "status": "ACTIVE",
            "description": "Che mờ số điện thoại cá nhân bảo vệ quyền riêng tư theo NĐ 13/2023/NĐ-CP."
        },
        {
            "mapping_id": "MAP-EMAIL-MASK",
            "operation_id": "MASK_EMAIL",
            "columns": ["customer_email", "email"],
            "datasets": ["dim_customers", "dim_drivers", "customers_clean"],
            "risk_level": RemediationRiskLevel.LOW,
            "requires_human_input": False,
            "post_check_rules": ["POST_EMAIL_MASK_VERIFIED"],
            "allowed_params": {
                "mask_char": {"type": str, "allowed": ["*", "x"], "default": "*"},
                "keep_domain": {"type": bool, "default": True},
            },
            "status": "ACTIVE",
            "description": "Che mờ hòm thư điện tử giữ nguyên tên miền."
        },
        {
            "mapping_id": "MAP-NAME-MASK",
            "operation_id": "MASK_NAME",
            "columns": ["customer_name", "first_name", "last_name"],
            "datasets": ["dim_customers", "dim_drivers", "trips_clean", "customers_clean"],
            "risk_level": RemediationRiskLevel.LOW,
            "requires_human_input": False,
            "post_check_rules": ["POST_NAME_MASK_VERIFIED"],
            "allowed_params": {
                "mask_char": {"type": str, "allowed": ["*"], "default": "*"},
                "keep_initials": {"type": bool, "default": True},
            },
            "status": "ACTIVE",
            "description": "Che mờ họ tên khách hàng/tài xế giữ lại ký tự đầu."
        },
        {
            "mapping_id": "MAP-COORDINATES-ROUND",
            "operation_id": "ROUND_DECIMAL",
            "columns": ["pickup_latitude", "pickup_longitude", "latitude", "longitude"],
            "datasets": ["ride_hailing_xanh_sm_trips", "synthetic_ev_telemetry_ved_ref", "trips_clean"],
            "risk_level": RemediationRiskLevel.LOW,
            "requires_human_input": False,
            "post_check_rules": ["POST_GEO_BOUNDS_VERIFIED", "POST_PRECISION_LIMIT"],
            "allowed_params": {
                "decimals": {"type": int, "min": 0, "max": 6, "default": 4},
            },
            "status": "ACTIVE",
            "description": "Làm tròn tọa độ GPS nhằm chống lộ vết di chuyển chi tiết của khách hàng."
        },
        {
            "mapping_id": "MAP-FARE-RECONCILE",
            "operation_id": "MANUAL_RECONCILIATION",
            "columns": ["fare_amount", "tip_amount", "total_fare"],
            "datasets": ["ride_hailing_xanh_sm_trips", "trips_clean"],
            "risk_level": RemediationRiskLevel.HIGH,
            "requires_human_input": True,
            "post_check_rules": ["POST_FINANCIAL_NON_NEGATIVE", "POST_RECONCILIATION_EVIDENCE_ATTACHED"],
            "allowed_params": {
                "action_type": {"type": str, "allowed": ["FLAG_DISCREPANCY", "VERIFY_VOUCHER", "REFUND_AUDIT", "ADJUST_FARE", "REJECT_RECORD"], "default": "ADJUST_FARE"},
                "corrected_value": {"type": (int, float, str), "default": None},
                "currency": {"type": str, "allowed": ["VND", "USD"], "default": "VND"},
                "reason": {"type": str, "default": ""},
                "evidence_doc_ref": {"type": str, "default": ""},
            },
            "status": "ACTIVE",
            "description": "Quy trình đối soát kế toán thủ công (IFRS 15 / SOX-404). Yêu cầu SO nhập số tiền đã kiểm định."
        },
    ]

    @classmethod
    def find_mapping(
        cls,
        dataset_id: str,
        column: str,
        rule_id: Optional[str] = None,
        reason: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Tra cứu mapping đã được phê duyệt trong Registry.
        Trả về mapping dict nếu tìm thấy, hoặc None nếu không có handler tự động nào được hỗ trợ.
        """
        ds_norm = (dataset_id or "").strip().lower()
        col_norm = (column or "").strip().lower()

        # Check special unexecutable types: Legal Basis B15, Driver changepoint/trend F16
        if col_norm == "legal_basis" or "b15" in (rule_id or "").lower() or "gdpr-006" in (reason or "").lower():
            return None

        if "f16" in (rule_id or "").lower() or "changepoint" in (reason or "").lower() or "trend" in (reason or "").lower():
            return None

        for m in cls.APPROVED_MAPPINGS:
            if m["status"] != "ACTIVE":
                continue

            # Check column match
            col_match = any(c == col_norm or c in col_norm for c in m["columns"])
            if not col_match:
                continue

            # Check dataset match (if specified)
            ds_match = any(d == ds_norm or d in ds_norm or ds_norm in d for d in m["datasets"])
            if ds_match or not m["datasets"]:
                return m

        return None

    @classmethod
    def validate_parameters(cls, operation_id: str, params: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Xác thực tham số đề xuất chống tấn công chèn mã hoặc ngoài giới hạn cho phép.
        """
        op_norm = operation_id.strip().upper()
        matching = [m for m in cls.APPROVED_MAPPINGS if m["operation_id"] == op_norm]
        if not matching:
            return False, f"Thao tác '{operation_id}' chưa được đăng ký trong RemediationRegistry"

        schema = matching[0].get("allowed_params", {})
        for param_key, param_val in params.items():
            if param_key not in schema:
                return False, f"Tham số '{param_key}' không nằm trong allowlist của thao tác '{operation_id}'"
            rule = schema[param_key]
            # Check type
            expected_type = rule.get("type")
            if expected_type and not isinstance(param_val, expected_type):
                return False, f"Tham số '{param_key}' không đúng kiểu {expected_type}"
            # Check bounds for numbers
            if "min" in rule and param_val < rule["min"]:
                return False, f"Tham số '{param_key}' nhỏ hơn giá trị tối thiểu {rule['min']}"
            if "max" in rule and param_val > rule["max"]:
                return False, f"Tham số '{param_key}' vượt quá giá trị tối đa {rule['max']}"
            # Check allowed enum values
            if "allowed" in rule and param_val not in rule["allowed"]:
                return False, f"Tham số '{param_key}' có giá trị '{param_val}' không nằm trong danh sách cho phép {rule['allowed']}"

        return True, None

    @classmethod
    def run_post_check(
        cls,
        dataset_id: str,
        column: str,
        before_val: Any,
        cleaned_val: Any,
        rule_id: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Kiểm tra tuân thủ sau xử lý (Post-Check).
        Bản ghi chỉ được ghi nhận vào Silver khi vượt qua toàn bộ Post-Check.
        """
        col_norm = column.strip().lower()

        # 1. Post-check cho số tiền / cước phí tài chính
        if "fare" in col_norm or "amount" in col_norm or "total" in col_norm:
            try:
                num = float(cleaned_val)
                if num <= 0:
                    return False, f"Post-check thất bại: Giá trị sau xử lý '{cleaned_val}' phải là số dương (> 0)."
            except (ValueError, TypeError):
                return False, f"Post-check thất bại: Giá trị cước phí '{cleaned_val}' không phải là số hợp lệ."

        # 2. Post-check cho số điện thoại / liên hệ
        if "phone" in col_norm or "contact" in col_norm:
            s = str(cleaned_val or "").strip()
            if not s or "*" not in s:
                return False, f"Post-check thất bại: Số điện thoại sau che mờ '{cleaned_val}' không đạt chuẩn mặt nạ bảo mật."

        # 3. Post-check cho tọa độ địa lý
        if "lat" in col_norm:
            try:
                lat = float(cleaned_val)
                if not (8.0 <= lat <= 24.0):
                    return False, f"Post-check thất bại: Vĩ độ '{lat}' nằm ngoài lãnh thổ Việt Nam (8.0 - 24.0)."
            except (ValueError, TypeError):
                return False, f"Post-check thất bại: Tọa độ vĩ độ '{cleaned_val}' không hợp lệ."

        if "lon" in col_norm:
            try:
                lon = float(cleaned_val)
                if not (102.0 <= lon <= 110.0):
                    return False, f"Post-check thất bại: Kinh độ '{lon}' nằm ngoài lãnh thổ Việt Nam (102.0 - 110.0)."
            except (ValueError, TypeError):
                return False, f"Post-check thất bại: Tọa độ kinh độ '{cleaned_val}' không hợp lệ."

        return True, "PASSED"
