"""
DataTrust OS: Operation Handlers
Implements transformation and validation functions corresponding to engine.operation_registry.
Covers all 5 Treatment Actions: REMOVE, PSEUDONYMIZE, KEEP_RESTRICTED, GENERALIZE, KEEP.
"""

import hashlib
import re
from typing import Any, Tuple, Optional, Dict


class OperationExecutionError(Exception):
    pass


# =============================================================================
# 1. ACTION: REMOVE
# =============================================================================

def handler_redact_null(val: Any, **kwargs) -> Tuple[Any, bool, Optional[str]]:
    """Gán giá trị thành None/NULL để giảm thiểu dữ liệu (Data Minimization)."""
    return None, True, None


def handler_drop_column(val: Any, **kwargs) -> Tuple[Any, bool, Optional[str]]:
    """Đánh dấu trường bị loại bỏ hoàn toàn."""
    return None, True, None


# =============================================================================
# 2. ACTION: PSEUDONYMIZE
# =============================================================================

def handler_mask_phone(val: Any, prefix_len: int = 3, suffix_len: int = 2, mask_char: str = "*", **kwargs) -> Tuple[Any, bool, Optional[str]]:
    """Che mờ số điện thoại, giữ lại prefix và suffix."""
    if val is None:
        return None, True, None
    s = str(val).strip()
    if len(s) <= (prefix_len + suffix_len):
        masked = mask_char * len(s)
        return masked, True, None
    
    prefix = s[:prefix_len]
    suffix = s[-suffix_len:] if suffix_len > 0 else ""
    middle = mask_char * (len(s) - prefix_len - suffix_len)
    return f"{prefix}{middle}{suffix}", True, None


def handler_mask_email(val: Any, keep_domain: bool = True, mask_char: str = "*", **kwargs) -> Tuple[Any, bool, Optional[str]]:
    """Che mờ email: name@domain -> n***@domain."""
    if val is None:
        return None, True, None
    s = str(val).strip()
    if "@" not in s:
        return mask_char * len(s), True, None
    
    parts = s.split("@", 1)
    local, domain = parts[0], parts[1]
    if len(local) <= 1:
        masked_local = mask_char * len(local)
    else:
        masked_local = local[0] + (mask_char * (len(local) - 1))
    
    if keep_domain:
        return f"{masked_local}@{domain}", True, None
    return f"{masked_local}@{mask_char * len(domain)}", True, None


def handler_hash_sha256(val: Any, salt: str = "gsm_global_salt_2026", **kwargs) -> Tuple[Any, bool, Optional[str]]:
    """Mã hóa băm 1 chiều Salted SHA-256."""
    if val is None:
        return None, True, None
    raw = f"{val}_{salt}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest(), True, None


def handler_mask_name(val: Any, keep_first: bool = True, mask_char: str = "*", **kwargs) -> Tuple[Any, bool, Optional[str]]:
    """Che mờ họ tên cá nhân: 'Nguyễn Quốc Bảo' -> 'Nguyễn *** Bảo'."""
    if val is None:
        return None, True, None
    tokens = str(val).strip().split()
    if len(tokens) <= 1:
        return mask_char * len(str(val)), True, None
    
    first = tokens[0]
    last = tokens[-1]
    masked_middle = mask_char * 3
    return f"{first} {masked_middle} {last}", True, None


# =============================================================================
# 3. ACTION: KEEP_RESTRICTED
# =============================================================================

def handler_encrypt_aes(val: Any, key_alias: str = "vault_finance_v1", **kwargs) -> Tuple[Any, bool, Optional[str]]:
    """Mô phỏng mã hóa đối xứng cấp cột AES-256."""
    if val is None:
        return None, True, None
    s = str(val).encode("utf-8")
    pseudo_cipher = hashlib.sha256(s + key_alias.encode("utf-8")).hexdigest()[:24]
    return f"ENC({key_alias}:{pseudo_cipher})", True, None


def handler_restricted_view(val: Any, allowed_roles: Optional[list] = None, current_role: str = "AUDITOR", **kwargs) -> Tuple[Any, bool, Optional[str]]:
    """Kiểm soát truy cập dựa trên vai trò (RBAC)."""
    allowed = allowed_roles or ["ADMIN"]
    if current_role in allowed:
        return val, True, None
    return "[RESTRICTED_ACCESS]", True, None


# =============================================================================
# 4. ACTION: GENERALIZE
# =============================================================================

def handler_round_decimal(val: Any, decimals: int = 2, **kwargs) -> Tuple[Any, bool, Optional[str]]:
    """Làm tròn số thập phân (ví dụ làm tròn tọa độ GPS để giảm độ phân giải vị trí)."""
    if val is None:
        return None, True, None
    try:
        f = float(val)
        return round(f, decimals), True, None
    except (ValueError, TypeError):
        return val, False, f"Giá trị không thể ép kiểu sang float: {val}"


def handler_bucketize(val: Any, step: int = 10, **kwargs) -> Tuple[Any, bool, Optional[str]]:
    """Gom nhóm giá trị số thành khoảng (ví dụ: tuổi 27 -> '20-29')."""
    if val is None:
        return None, True, None
    try:
        n = int(val)
        low = (n // step) * step
        high = low + step - 1
        return f"{low}-{high}", True, None
    except (ValueError, TypeError):
        return val, False, f"Giá trị không thể ép kiểu sang int: {val}"


# =============================================================================
# 5. ACTION: KEEP
# =============================================================================

def handler_passthrough(val: Any, **kwargs) -> Tuple[Any, bool, Optional[str]]:
    """Chuyển giao nguyên vẹn khi đã pass."""
    return val, True, None


def handler_range_check(val: Any, min_val: Optional[float] = None, max_val: Optional[float] = None, allow_zero: bool = True, **kwargs) -> Tuple[Any, bool, Optional[str]]:
    """Kiểm tra giá trị số nằm trong khoảng hợp lệ."""
    if val is None:
        return None, False, "Giá trị là NULL"
    try:
        v = float(val)
        if not allow_zero and v == 0.0:
            return v, False, "Giá trị bằng 0 (yêu cầu khác 0)"
        if min_val is not None and v < min_val:
            return v, False, f"Giá trị {v} nhỏ hơn ngưỡng tối thiểu {min_val}"
        if max_val is not None and v > max_val:
            return v, False, f"Giá trị {v} lớn hơn ngưỡng tối đa {max_val}"
        return v, True, None
    except (ValueError, TypeError):
        return val, False, f"Giá trị không phải kiểu số: {val}"


def handler_not_null(val: Any, **kwargs) -> Tuple[Any, bool, Optional[str]]:
    """Kiểm tra không được rỗng hoặc NULL."""
    if val is None or str(val).strip() == "":
        return val, False, "Trường bắt buộc bị để trống (NULL hoặc rỗng)"
    return val, True, None


def handler_regex_match(val: Any, pattern: str = ".*", **kwargs) -> Tuple[Any, bool, Optional[str]]:
    """Kiểm tra chuỗi khớp với mẫu biểu thức chính quy."""
    if val is None:
        return None, False, "Giá trị là NULL"
    s = str(val).strip()
    if not re.match(pattern, s):
        return s, False, f"Giá trị '{s}' không khớp regex pattern '{pattern}'"
    return s, True, None


# =============================================================================
# REGISTRY MAP
# =============================================================================

OPERATION_HANDLERS = {
    # REMOVE
    "redact_null": handler_redact_null,
    "drop_column": handler_drop_column,
    # PSEUDONYMIZE
    "mask_phone": handler_mask_phone,
    "mask_email": handler_mask_email,
    "hash_sha256": handler_hash_sha256,
    "mask_name": handler_mask_name,
    # KEEP_RESTRICTED
    "column_encrypt_aes": handler_encrypt_aes,
    "access_restricted_view": handler_restricted_view,
    # GENERALIZE
    "round_decimal": handler_round_decimal,
    "bucketize_range": handler_bucketize,
    # KEEP
    "passthrough_check": handler_passthrough,
    "range_check": handler_range_check,
    "not_null": handler_not_null,
    "regex_match": handler_regex_match,
}


def execute_operation(operation_id: str, val: Any, params: Optional[Dict[str, Any]] = None) -> Tuple[Any, bool, Optional[str]]:
    """
    Thực thi operation tương ứng với operation_id.
    Trả về: (transformed_val, is_valid, error_reason)
    """
    handler = OPERATION_HANDLERS.get(operation_id)
    if not handler:
        raise OperationExecutionError(f"Operation '{operation_id}' chưa được đăng ký trong hệ thống!")
    params = params or {}
    return handler(val, **params)
