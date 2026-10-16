"""
SoD Flow Catalog: 19 Control Activities, 10 Roles, RACIX Symbols & SLA Rules
Direct 1:1 fidelity with sod-production.
"""

from typing import Dict, List, Literal, Tuple, Union

ROLE_KEYS = ["REQ", "LM", "DPO", "SO", "CISO", "IAM", "DEV", "REL", "OPS", "AUD"]
RoleKey = Literal["REQ", "LM", "DPO", "SO", "CISO", "IAM", "DEV", "REL", "OPS", "AUD"]

ROLES: Dict[str, Dict[str, str]] = {
    "REQ": {"name": "Requestor", "short": "Req."},
    "LM": {"name": "Line Manager", "short": "Line Mgr"},
    "DPO": {"name": "DPO/Compliance", "short": "DPO"},
    "SO": {"name": "System Owner", "short": "Sys Owner"},
    "CISO": {"name": "CISO/Security", "short": "CISO"},
    "IAM": {"name": "IAM Administrator", "short": "IAM"},
    "DEV": {"name": "Developer", "short": "Dev"},
    "REL": {"name": "Release Manager", "short": "Rel. Mgr"},
    "OPS": {"name": "Production Operator", "short": "Prod. Op."},
    "AUD": {"name": "Auditor", "short": "Auditor"},
}

Letter = Literal["P", "A", "R", "C", "I", "X"]
StepAction = Literal["P", "R", "A"]

LETTERS: Dict[str, str] = {
    "P": "Được phép thực hiện",
    "A": "Phê duyệt / chịu trách nhiệm cuối cùng",
    "R": "Rà soát / xác nhận",
    "C": "Được tham vấn",
    "I": "Được thông báo",
    "X": "Cấm kết hợp",
}

VERB: Dict[str, str] = {"P": "Thực hiện", "R": "Rà soát", "A": "Phê duyệt"}

# 19 Control Activities (0..18)
ACTIVITIES: List[Dict[str, Union[int, str]]] = [
    {"id": 0, "name": "Khởi tạo yêu cầu cấp quyền", "kind": "work", "m": "PXIIIXIIXI"},
    {"id": 1, "name": "Xác nhận nhu cầu nghiệp vụ", "kind": "approval", "m": "XACRIXXXXI"},
    {"id": 2, "name": "Phê duyệt quyền có truy cập PII", "kind": "approval", "m": "XAARCXXXXI"},
    {"id": 3, "name": "Phê duyệt quyền đặc quyền hoặc quyền DB", "kind": "approval", "m": "XCCAAXXXXI"},
    {"id": 4, "name": "Cấp quyền qua IAM/PAM", "kind": "work", "m": "XXXXRPXXXI"},
    {"id": 5, "name": "Thu hồi quyền khi nhân sự nghỉ việc", "kind": "approval", "m": "IAIRCPXXXR"},
    {"id": 6, "name": "Điều chuyển hoặc thay đổi vai trò", "kind": "approval", "m": "IACRIPXXXR"},
    {"id": 7, "name": "Tạo hoặc sửa RBAC role", "kind": "approval", "m": "XXCAAPXRXI"},
    {"id": 8, "name": "Phát triển mã nguồn", "kind": "work", "m": "XXXIRXPXXI"},
    {"id": 9, "name": "Kiểm thử và xác nhận kết quả", "kind": "work", "m": "XXCRRXPAXI"},
    {"id": 10, "name": "Phê duyệt phát hành Production", "kind": "approval", "m": "XXCRAXXAXI"},
    {"id": 11, "name": "Triển khai Production", "kind": "work", "m": "XXXIRXXXPI"},
    {"id": 12, "name": "Thay đổi giá, khuyến mại hoặc chính sách vận hành", "kind": "approval", "m": "PACARXXRII"},
    {"id": 13, "name": "Truy vấn dữ liệu PII nghiệp vụ (khách hàng) trực tiếp", "kind": "approval", "m": "PXAARXXXXI"},
    {"id": 14, "name": "Xuất dữ liệu PII nghiệp vụ (khách hàng)", "kind": "approval", "m": "PAARRXXXXI"},
    {"id": 15, "name": "Phê duyệt ngoại lệ kiểm soát", "kind": "approval", "m": "XCAAAXXXXI"},
    {"id": 16, "name": "Điều tra sự cố bảo mật", "kind": "work", "m": "CICRACCCPI"},
    {"id": 17, "name": "Đóng sự cố và xác nhận khắc phục", "kind": "approval", "m": "IICRAXXRRR"},
    {"id": 18, "name": "Rà soát quyền định kỳ", "kind": "work", "m": "IACPRIXXXR"},
]

DEFAULT_MATRIX: List[str] = [str(a["m"]) for a in ACTIVITIES]

SOD_CONFIG = {
    "sla": {"P": 8, "R": 24, "A": 24},
    "breakGlassHours": 24,
    "priority": {"urgent": 0.25, "high": 0.5, "normal": 1, "low": 2},
    "remindPct": 75,
    "escalatePct": 100,
    "criticalPct": 200,
    "retentionDays": 1825,
    "delegationMaxDays": 30,
    "staleCloseDays": 7,
    "rank": {"REQ": 0, "DEV": 1, "OPS": 1, "IAM": 2, "LM": 3, "REL": 3, "SO": 4, "DPO": 5, "CISO": 6, "AUD": 9},
}

TICKET_TYPES = [
    {"id": "offboard", "name": "Thu hồi quyền (nghỉ việc)", "acts": [5]},
    {"id": "incident", "name": "Sự cố bảo mật", "acts": [16, 17]},
    {"id": "pii_export", "name": "Xuất dữ liệu PII nghiệp vụ (khách hàng)", "acts": [14, 4]},
    {"id": "pii_query", "name": "Truy vấn dữ liệu PII nghiệp vụ (khách hàng) trực tiếp", "acts": [13, 4]},
    {"id": "exception", "name": "Ngoại lệ kiểm soát", "acts": [15]},
    {"id": "pricing", "name": "Thay đổi giá / khuyến mại / chính sách", "acts": [12]},
    {"id": "change", "name": "Thay đổi mã nguồn → Production", "acts": [8, 9, 10, 11]},
    {"id": "rbac", "name": "Tạo / sửa RBAC role", "acts": [7]},
    {"id": "transfer", "name": "Điều chuyển / thay đổi vai trò", "acts": [6]},
    {"id": "review", "name": "Rà soát quyền định kỳ", "acts": [18]},
    {"id": "remediation", "name": "Khắc phục vi phạm dữ liệu (Quarantine Remediation)", "acts": [0, 1, 4]},
    {"id": "rule_change", "name": "Thay đổi quy tắc chất lượng (Quality Rule Change)", "acts": [0, 7, 10]},
    {"id": "access", "name": "Cấp quyền truy cập", "acts": [0, 1, 4]},
]


def ticket_type(type_id: str) -> Dict[str, Union[str, List[int]]]:
    for t in TICKET_TYPES:
        if t["id"] == type_id:
            return t
    return TICKET_TYPES[-1]  # default to access


def letter(act_id: int, role: str, matrix: List[str] = None) -> str:
    m = matrix if matrix is not None else DEFAULT_MATRIX
    role_idx = ROLE_KEYS.index(role)
    return m[act_id][role_idx]


def act_name(a: Union[int, str]) -> str:
    if a == "bg":
        return "Hậu kiểm break-glass"
    if a == "init":
        return "Khởi tạo ticket"
    try:
        return str(ACTIVITIES[int(a)]["name"])
    except (ValueError, IndexError):
        return f"Hoạt động {a}"


def role_name(r: str) -> str:
    return ROLES.get(r, {}).get("name", r)
