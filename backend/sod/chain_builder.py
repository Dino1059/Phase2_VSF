"""
SoD Flow Chain Builder: Sequential Approval Chain Generation ($R \\to A \\to P$).
1:1 Fidelity with sod-production.
"""

from typing import Any, Dict, List, Optional, Tuple
from backend.sod.catalog import (
    ACTIVITIES,
    DEFAULT_MATRIX,
    ROLE_KEYS,
    SOD_CONFIG,
    act_name,
    letter,
)
from backend.sod.classifier import classify_ticket


def phase_steps(act_id: int, mods: Optional[Dict[str, str]] = None, matrix: Optional[List[str]] = None) -> Dict[str, Any]:
    m = matrix if matrix is not None else DEFAULT_MATRIX
    mods = mods or {}

    def L(r: str) -> str:
        return mods.get(r, letter(act_id, r, m))

    def by_rank(r: str) -> int:
        return SOD_CONFIG["rank"].get(r, 99)

    def pick(l_val: str) -> List[str]:
        roles = [
            r for r in ROLE_KEYS
            if r != "AUDITOR" and L(r) == l_val and not (l_val == "P" and r == "REQ")
        ]
        roles.sort(key=by_rank)
        return roles

    P = pick("P")
    R = pick("R")
    A = pick("A")

    aud_l = L("AUDITOR")
    aud: List[Tuple[str, str]] = [("AUDITOR", aud_l)] if aud_l in "RA" else []

    kind = ACTIVITIES[act_id]["kind"]
    if kind == "approval":
        # approval: R → A → AUD (R) → P
        seq = [(r, "R") for r in R] + [(r, "A") for r in A] + aud + [(r, "P") for r in P]
    else:
        # work: AUD → P → R → A
        seq = aud + [(r, "P") for r in P] + [(r, "R") for r in R] + [(r, "A") for r in A]

    return {
        "seq": seq,
        "C": [r for r in ROLE_KEYS if L(r) == "C"],
        "I": [r for r in ROLE_KEYS if L(r) == "I"],
    }


def build_approval_chain(
    classification: Dict[str, Any],
    requester_id: str,
    matrix: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Sinh chuỗi phê duyệt tuần tự các bước từ kết quả phân loại.
    """
    m = matrix if matrix is not None else DEFAULT_MATRIX
    steps: List[Dict[str, Any]] = [
        {
            "idx": 0,
            "key": "init",
            "role": "REQ",
            "action": "P",
            "acts": ["init"],
            "phase": 0,
            "assignee_id": requester_id,
            "status": "DONE",
        }
    ]
    phases: List[Dict[str, Any]] = [
        {"act": "init", "name": act_name("init"), "C": [], "I": []}
    ]

    prev: List[Dict[str, Any]] = []
    prev_kind: Optional[str] = None
    step_idx = 1

    for a in classification.get("acts", []):
        kind = ACTIVITIES[a]["kind"]
        mods_a = classification.get("mods", {}).get(a, {})
        ps = phase_steps(a, mods_a, m)

        phase_idx = len(phases)
        phases.append({
            "act": a,
            "name": act_name(a),
            "C": ps["C"],
            "I": ps["I"],
        })

        cur: List[Dict[str, Any]] = []
        for role, action in ps["seq"]:
            # Gộp với bước liền trước nếu cùng vai trò và hành động
            can_merge = action != "A" or (kind == "approval" and prev_kind == "approval")
            dup = None
            if can_merge:
                for s in prev:
                    if s["role"] == role and s["action"] == action:
                        dup = s
                        break

            if dup:
                dup["acts"].append(a)
                continue

            # Mặc định bước đầu tiên chờ xử lý là CURRENT, các bước sau WAITING
            step = {
                "idx": step_idx,
                "key": f"{role.lower()}_{action.lower()}",
                "role": role,
                "action": action,
                "acts": [a],
                "phase": phase_idx,
                "assignee_id": None,
                "status": "CURRENT" if step_idx == 1 else "WAITING",
                "sla_hours": SOD_CONFIG["sla"].get(action, 24),
            }
            steps.append(step)
            cur.append(step)
            step_idx += 1

        prev = cur
        prev_kind = kind

    return {
        "requester_id": requester_id,
        "steps": steps,
        "phases": phases,
        "classification": classification,
        "total_steps": len(steps),
    }
