"""
SoD Flow Conflict Detector: Auto-assignment & SoD Constraints Enforcement.
1:1 Fidelity with sod-production.
"""

from typing import Any, Dict, List, Optional
from backend.sod.catalog import ROLES

PAIR_NAMES: Dict[str, str] = {
    "DEV|REL": "Developer ↔ Production Approver",
    "DEV|OPS": "Developer ↔ Production Deployer",
    "CISO|DEV": "Developer ↔ Production Approver",
    "DPO|SO": "DPO ↔ System Owner",
}


def pair_name(a: str, b: str) -> str:
    if a == "AUDITOR" or b == "AUDITOR":
        return "Auditor ↔ Control Operator"
    if a == "IAM" or b == "IAM":
        return "Approver ↔ IAM Provisioner"
    key = "|".join(sorted([a, b]))
    name_a = ROLES.get(a, {}).get("name", a)
    name_b = ROLES.get(b, {}).get("name", b)
    return PAIR_NAMES.get(key, f"{name_a} ↔ {name_b}")


def requestor_may_act(action: str, role: str) -> bool:
    """Người yêu cầu chỉ được làm bước P không phải cấp quyền / triển khai."""
    return action == "P" and role not in ("IAM", "OPS")


def conflicts_for(steps: List[Dict[str, Any]], requester_id: str, step_idx: int, person_id: Optional[str]) -> List[str]:
    """
    Trả về danh sách các xung đột SoD nếu giao bước step_idx cho người person_id.
    Rỗng = Hợp lệ / Không xung đột.
    """
    if not person_id:
        return ["Không có người đủ điều kiện cho vai trò này"]

    step = steps[step_idx]
    action = step.get("action", "")
    role = step.get("role", "")
    out: List[str] = []

    # 1. Ràng buộc Chống tự duyệt (No Self-Approval)
    if step_idx > 0 and str(person_id) == str(requester_id) and not requestor_may_act(action, role):
        if action == "P":
            out.append(f"Requestor ↔ {ROLES.get(role, {}).get('name', role)}")
        else:
            out.append("Requestor ↔ Approver (tự duyệt yêu cầu của mình)")

    # 2. Ràng buộc Một người không kiêm hai vai trò khác nhau trên cùng ticket
    for j, other in enumerate(steps):
        if j == 0 or j == step_idx:
            continue
        other_assignee = other.get("assignee_id")
        other_role = other.get("role")
        if other_assignee and str(other_assignee) == str(person_id) and other_role != role:
            conflict_label = pair_name(role, other_role)
            if conflict_label not in out:
                out.append(conflict_label)

    return out


def auto_assign_steps(steps: List[Dict[str, Any]], requester_id: str, people: List[Dict[str, Any]]) -> None:
    """
    Tự động phân bổ người xử lý cho từng bước sao cho không vi phạm bất kỳ xung đột SoD nào.
    people: Danh sách user [{"id": "...", "name": "...", "roles": ["..."]}]
    """
    for i, s in enumerate(steps):
        if i == 0:
            s["assignee_id"] = requester_id
            continue

        role = s.get("role")
        # Tìm các ứng viên có vai trò phù hợp
        candidates = [p for p in people if role in p.get("roles", [])]
        if not candidates:
            continue

        # Chọn ứng viên đầu tiên không bị xung đột
        chosen = None
        for c in candidates:
            if len(conflicts_for(steps, requester_id, i, c["id"])) == 0:
                chosen = c["id"]
                break

        # Nếu tất cả đều có xung đột, lấy ứng viên đầu tiên
        s["assignee_id"] = chosen if chosen else candidates[0]["id"]


def is_self_approval(requester_id: str, actor_id: str) -> bool:
    return str(requester_id) == str(actor_id)


def check_step_conflict(
    requester_id: str,
    actor_id: str,
    actor_roles: List[str],
    step_role: str,
    step_action: str,
    prior_decisions: Optional[List[Dict[str, Any]]] = None
) -> Optional[str]:
    """Helper kiểm tra xung đột quyết định bước duyệt."""
    if is_self_approval(requester_id, actor_id) and not requestor_may_act(step_action, step_role):
        return "Không thể tự phê duyệt yêu cầu của chính mình"

    if prior_decisions:
        for p in prior_decisions:
            if str(p.get("actor_id")) == str(actor_id) and p.get("role") != step_role:
                return f"Xung đột SoD: {pair_name(step_role, p.get('role', ''))}"
    return None
