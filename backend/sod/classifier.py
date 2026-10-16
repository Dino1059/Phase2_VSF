"""
SoD Flow Classifier: Classification of Access Requests into RACIX Control Activities.
1:1 Fidelity with sod-production.
"""

from typing import Any, Dict, List, Optional
from backend.sod.catalog import (
    ACTIVITIES,
    DEFAULT_MATRIX,
    ROLES,
    SOD_CONFIG,
    VERB,
    act_name,
    letter,
    ticket_type,
)

LOAI_PHIEU_MAP = {
    "new": "Cấp mới",
    "adjust": "Điều chỉnh",
    "extend": "Gia hạn",
    "revoke": "Thu hồi",
    "bg": "Break-glass",
    "remediation": "Khắc phục vi phạm (Remediation)",
    "rule_change": "Thay đổi quy tắc (Rule Change)",
}


def form_level(d: Dict[str, Any]) -> int:
    rows = d.get("rows") or []
    levels = []
    for r in rows:
        try:
            levels.append(int(r.get("tang") or 0))
        except (ValueError, TypeError):
            pass
    return max([1] + levels)


def form_pii(d: Dict[str, Any]) -> bool:
    dlcn = str(d.get("dlcn") or "").lower()
    return dlcn in ("basic", "sensitive", "co", "true")


def form_priority(d: Dict[str, Any]) -> str:
    khan = str(d.get("khan") or "").lower()
    return "urgent" if khan == "urgent" else "normal"


def classify_ticket(form: Dict[str, Any], matrix: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Phân loại form phiếu yêu cầu thành tập các hoạt động kiểm soát ITGC và nâng vai trò (mods).
    """
    m = matrix if matrix is not None else DEFAULT_MATRIX
    loai_phieu = form.get("loaiPhieu") or "new"
    revoke = loai_phieu == "revoke"
    if loai_phieu in ("remediation", "rule_change", "offboard", "incident", "pii_export", "pii_query", "exception", "pricing", "change", "rbac", "review"):
        ttype = ticket_type(loai_phieu)
    else:
        ttype = ticket_type("offboard" if revoke else "access")
    acts: List[int] = list(ttype["acts"])
    level = form_level(form)
    pii = form_pii(form)
    break_glass = loai_phieu == "bg"
    loai_label = LOAI_PHIEU_MAP.get(loai_phieu, loai_phieu)

    reasons = [
        f"Loại phiếu “{loai_label}” → {'Thu hồi quyền' if revoke else 'Cấp quyền / Khắc phục dữ liệu'}"
    ]
    mods: Dict[int, Dict[str, str]] = {}

    if not revoke and pii:
        # Chèn hoạt động 2 (PII) sau hoạt động 1
        try:
            pos = acts.index(1) + 1
        except ValueError:
            pos = len(acts)
        acts.insert(pos, 2)
        reasons.append("Có DLCN → thêm “Phê duyệt quyền có truy cập PII”")

    if not revoke and level == 3:
        # Chèn hoạt động 3 (Đặc quyền / DB) trước hoạt động 4
        try:
            pos = acts.index(4)
        except ValueError:
            pos = len(acts)
        acts.insert(pos, 3)
        reasons.append("Tầng dữ liệu 3 → thêm “Phê duyệt quyền đặc quyền hoặc quyền DB”")

    if form.get("exception"):
        # Chèn hoạt động 15 (Ngoại lệ)
        try:
            pos = acts.index(0) + 1
        except ValueError:
            pos = 0
        acts.insert(pos, 15)
        reasons.append("Xin ngoại lệ SoD → thêm “Phê duyệt ngoại lệ kiểm soát” trước khi thực thi")

    # QT 5.4: Level 2 hoặc PII cần DPO rà soát; Level 3 cần CISO phê duyệt
    def ensure_role(role: str, need: str, why: str):
        if any(letter(a, role, m) in need or (mods.get(a, {}).get(role, "-") in need) for a in acts):
            return
        target = None
        for a in acts:
            if ACTIVITIES[a]["kind"] == "approval" and letter(a, role, m) not in "XP":
                target = a
                break
        if target is None:
            for a in acts:
                if letter(a, role, m) not in "XP":
                    target = a
                    break
        if target is None:
            return

        if target not in mods:
            mods[target] = {}
        mods[target][role] = need[0]
        action_verb = VERB.get(need[0], need[0]).lower()
        role_name = ROLES.get(role, {}).get("name", role)
        target_name = act_name(target)
        reasons.append(f"{why} → {role_name} {action_verb} ở “{target_name}”")

    if pii or level >= 2:
        ensure_role("DPO", "RA", "QT 5.4: Tầng 2 / DLCN cần DPO rà soát")
    if level == 3:
        ensure_role("CISO", "A", "QT 5.4: Tầng 3 cần CISO phê duyệt")
    if form.get("dlcn") == "sensitive":
        reasons.append("DLCN nhạy cảm → bắt buộc lý do nghiệp vụ và ý kiến DPO")
    if break_glass:
        reasons.append(f"Break-glass → ghi log, giám sát phiên, Auditor hậu kiểm trong {SOD_CONFIG['breakGlassHours']}h")

    return {
        "type": ttype,
        "acts": acts,
        "mods": mods,
        "reasons": reasons,
        "level": level,
        "pii": pii,
        "break_glass": break_glass,
    }
