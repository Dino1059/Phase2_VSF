"""
DataTrust OS x SoD Flow: Backend SoD RESTful API Router
Exposes endpoints for RACIX Matrix, Tickets, Sequential Approvals, Inbox, Delegations,
2-Person Rule Config, and SHA-256 Integrity Evidence.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, status

from database.profiler_engine import get_db_connection
from backend.api.auth_routes import UserContext, get_current_user, require_permission
from backend.sod.service import SodService

router = APIRouter()


class CreateTicketRequest(BaseModel):
    form: Dict[str, Any]


class DecideStepRequest(BaseModel):
    outcome: str  # 'APPROVE' | 'RETURN' | 'REJECT' | 'COMPLETE'
    comment: Optional[str] = ""
    reconciliation: Optional[Dict[str, Any]] = None


class CreateDelegationRequest(BaseModel):
    delegate_id: str
    role_code: str
    valid_from: str
    valid_to: str
    reason: str


class ProposeConfigRequest(BaseModel):
    config: Dict[str, Any]
    reason: str


class DecideConfigRequest(BaseModel):
    outcome: str  # 'ACTIVE' | 'REJECTED'
    decision_note: Optional[str] = ""


# 1. MA TRẬN RACIX (ACTIVE VERSION)
@router.get("/matrix")
def get_racix_matrix(
    current_user: UserContext = Depends(require_permission("sod_access")),
    conn = Depends(get_db_connection)
):
    """Lấy ma trận RACIX phiên bản ACTIVE trực tiếp từ CSDL (Fail-Closed)."""
    config_id, config_seq, matrix = SodService.get_active_matrix(conn)
    return {
        "config_version_id": config_id,
        "config_seq": config_seq,
        "matrix": matrix,
        "status": "ACTIVE",
    }


# 2. XEM TRƯỚC CHUỖI PHÊ DUYỆT (PREVIEW CHAIN)
@router.post("/tickets/preview")
def preview_chain(
    payload: CreateTicketRequest,
    current_user: UserContext = Depends(require_permission("sod_access")),
    conn = Depends(get_db_connection)
):
    """Sinh chuỗi duyệt tuần tự xem trước phía server theo phiên bản ma trận ACTIVE."""
    return SodService.preview_chain(payload.form, current_user.user_id, conn)


# 3. DANH SÁCH & TẠO PHIẾU YÊU CẦU
@router.get("/tickets")
def list_tickets(
    status: Optional[str] = Query(None),
    current_user: UserContext = Depends(require_permission("sod_access")),
    conn = Depends(get_db_connection)
):
    """Lấy danh sách phiếu yêu cầu."""
    return SodService.get_tickets(conn, status=status)


@router.post("/tickets")
def create_ticket(
    payload: CreateTicketRequest,
    current_user: UserContext = Depends(require_permission("sod_create_ticket")),
    conn = Depends(get_db_connection)
):
    """Khởi tạo phiếu đề nghị mới (Lưu snapshot ma trận và form_hash)."""
    return SodService.create_ticket(payload.form, current_user.user_id, conn)


@router.get("/tickets/{ticket_id}")
def get_ticket_detail(
    ticket_id: str,
    current_user: UserContext = Depends(require_permission("sod_access")),
    conn = Depends(get_db_connection)
):
    """Lấy thông tin chi tiết phiếu, tiến trình và các quyết định."""
    return SodService.get_ticket_detail(ticket_id, conn)


# 4. RA QUYẾT ĐỊNH DUYỆT BƯỚC (TRANSACTION & CONCURRENCY LOCKING)
@router.post("/tickets/{ticket_id}/steps/{step_id}/decide")
def decide_step(
    ticket_id: str,
    step_id: str,
    payload: DecideStepRequest,
    current_user: UserContext = Depends(require_permission("sod_access")),
    conn = Depends(get_db_connection)
):
    """
    Gửi quyết định duyệt / trả lại / từ chối trên một bước.
    Áp dụng SELECT FOR UPDATE để chống concurrent approval.
    Kích hoạt DB Trigger step_decision_guard để chống tự duyệt và xung đột SoD.
    """
    return SodService.decide_step(
        ticket_id=ticket_id,
        step_id=step_id,
        actor_id=current_user.user_id,
        outcome=payload.outcome,
        comment=payload.comment or "",
        reconciliation=payload.reconciliation,
        conn=conn
    )


# 5. HỘP VIỆC CHỜ XỬ LÝ (INBOX)
@router.get("/inbox")
def get_inbox(
    current_user: UserContext = Depends(require_permission("sod_access")),
    conn = Depends(get_db_connection)
):
    """Lấy danh sách nhiệm vụ đang chờ phê duyệt của user hoặc user được ủy quyền."""
    return SodService.get_inbox(current_user.user_id, current_user.active_role, conn)


# 6. BÁO CÁO BẰNG CHỨNG TOÀN VẸN (SHA-256 INTEGRITY EVIDENCE)
@router.get("/evidence/{ticket_id}")
def get_ticket_evidence(
    ticket_id: str,
    current_user: UserContext = Depends(require_permission("sod_read_evidence")),
    conn = Depends(get_db_connection)
):
    """Xuất chứng từ kiểm toán tính toàn vẹn SHA-256 của phiếu yêu cầu."""
    return SodService.generate_integrity_evidence(ticket_id, conn)


# 7. QUẢN TRỊ ỦY QUYỀN VẮNG MẶT (DELEGATIONS)
@router.get("/delegations")
def list_delegations(
    current_user: UserContext = Depends(require_permission("sod_access")),
    conn = Depends(get_db_connection)
):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT d.*, u1.full_name as delegator_name, u2.full_name as delegate_name
            FROM sod.delegations d
            JOIN sod.users u1 ON d.delegator_id = u1.id
            JOIN sod.users u2 ON d.delegate_id = u2.id
            ORDER BY d.created_at DESC;
        """)
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


@router.post("/delegations")
def create_delegation(
    payload: CreateDelegationRequest,
    current_user: UserContext = Depends(require_permission("sod_access")),
    conn = Depends(get_db_connection)
):
    with conn.cursor() as cur:
        # Kiểm tra người ủy quyền và người nhận cùng vai trò
        cur.execute("""
            SELECT 1 FROM sod.user_roles WHERE user_id = %s AND role_code = %s;
        """, (payload.delegate_id, payload.role_code))
        if not cur.fetchone():
            raise HTTPException(status_code=400, detail="Người nhận ủy quyền không có vai trò này.")

        cur.execute("""
            INSERT INTO sod.delegations (delegator_id, delegate_id, role_code, valid_from, valid_to, reason)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id;
        """, (current_user.user_id, payload.delegate_id, payload.role_code, payload.valid_from, payload.valid_to, payload.reason))
        conn.commit()
        return {"status": "SUCCESS", "id": str(cur.fetchone()[0])}


@router.delete("/delegations/{delegation_id}")
def revoke_delegation(
    delegation_id: str,
    current_user: UserContext = Depends(require_permission("sod_access")),
    conn = Depends(get_db_connection)
):
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE sod.delegations SET revoked_at = now()
            WHERE id = %s AND delegator_id = %s;
        """, (delegation_id, current_user.user_id))
        conn.commit()
        return {"status": "SUCCESS", "message": "Đã thu hồi ủy quyền."}


# 8. QUẢN TRỊ CẤU HÌNH MA TRẬN RACIX (QUY TẮC 2 NGƯỜI: ADMIN ĐỀ XUẤT ≠ CISO DUYỆT)
@router.get("/config")
def list_configs(
    current_user: UserContext = Depends(require_permission("sod_access")),
    conn = Depends(get_db_connection)
):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT c.*, u1.full_name as proposer_name, u2.full_name as decider_name
            FROM sod.config_versions c
            LEFT JOIN sod.users u1 ON c.proposed_by = u1.id
            LEFT JOIN sod.users u2 ON c.decided_by = u2.id
            ORDER BY c.seq DESC;
        """)
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


@router.post("/config/propose")
def propose_config(
    payload: ProposeConfigRequest,
    current_user: UserContext = Depends(require_permission("sod_propose_config")),
    conn = Depends(get_db_connection)
):
    """Admin tạo đề xuất cấu hình ma trận phiên bản mới."""
    with conn.cursor() as cur:
        cur.execute("SELECT seq FROM sod.config_versions WHERE status = 'ACTIVE' ORDER BY seq DESC LIMIT 1;")
        base = cur.fetchone()
        base_seq = base[0] if base else 1

        import json
        cur.execute("""
            INSERT INTO sod.config_versions (config, status, reason, base_seq, proposed_by)
            VALUES (%s, 'PROPOSED', %s, %s, %s)
            RETURNING id, seq;
        """, (json.dumps(payload.config), payload.reason, base_seq, current_user.user_id))
        res = cur.fetchone()
        conn.commit()
        return {"status": "SUCCESS", "id": str(res[0]), "seq": res[1]}


@router.post("/config/{config_id}/decide")
def decide_config(
    config_id: str,
    payload: DecideConfigRequest,
    current_user: UserContext = Depends(require_permission("sod_decide_config")),
    conn = Depends(get_db_connection)
):
    """CISO duyệt hoặc từ chối cấu hình đề xuất (Kích hoạt Trigger config_version_guard)."""
    decision = payload.outcome.upper()
    if decision not in ("ACTIVE", "REJECTED"):
        raise HTTPException(status_code=400, detail="Quyết định cấu hình phải là ACTIVE hoặc REJECTED.")

    with conn.cursor() as cur:
        cur.execute("""
            UPDATE sod.config_versions
            SET status = %s, decided_by = %s, decision_note = %s, decided_at = now()
            WHERE id = %s;
        """, (decision, current_user.user_id, payload.decision_note, config_id))
        conn.commit()
        return {"status": "SUCCESS", "message": f"Đã cập nhật cấu hình sang {decision}."}


# 7. PHASE 3: CROSS-SYSTEM INTEGRATION (FINDING -> SOD TICKET & STATUS)
class CreateTicketFromFindingRequest(BaseModel):
    finding_id: str
    proposal_id: str
    reason: Optional[str] = ""


@router.post("/tickets/from-finding")
def create_ticket_from_finding_endpoint(
    payload: CreateTicketFromFindingRequest,
    current_user: UserContext = Depends(require_permission("sod_create_ticket")),
    conn = Depends(get_db_connection)
):
    """Khởi tạo phiếu SoD từ Finding & Proposal trong DataTrust (Phase 3)."""
    from backend.sod.integration_service import create_governed_remediation_ticket, GovernanceException
    try:
        return create_governed_remediation_ticket(
            finding_id=payload.finding_id,
            proposal_id=payload.proposal_id,
            requester_user_id=current_user.user_id,
            reason=payload.reason or "",
            conn=conn
        )
    except GovernanceException as ge:
        raise HTTPException(
            status_code=409 if ge.error_code in ("TICKET_ALREADY_ACTIVE", "PROPOSAL_STATE_INVALID") else 404,
            detail={"error_code": ge.error_code, "message": ge.message, "details": ge.details}
        )
    except KeyError as ke:
        raise HTTPException(status_code=404, detail={"error_code": "NOT_FOUND", "message": str(ke)})
    except Exception as e:
        raise HTTPException(status_code=400, detail={"error_code": "BAD_REQUEST", "message": str(e)})


@router.get("/tickets/for-finding/{finding_id}")
def get_sod_ticket_for_finding(
    finding_id: str,
    current_user: UserContext = Depends(require_permission("sod_access")),
    conn = Depends(get_db_connection)
):
    """Tra cứu trạng thái phiếu SoD gắn với Finding."""
    from psycopg2.extras import RealDictCursor
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT t.id as ticket_id, t.code as ticket_code, t.status as ticket_status,
                   t.current_step_idx, t.total_steps, ts.subject_version, ts.subject_hash,
                   s.role_code as current_role
            FROM sod.ticket_subjects ts
            JOIN sod.tickets t ON ts.ticket_id = t.id
            LEFT JOIN sod.ticket_steps s ON t.active_step_id = s.id
            WHERE ts.subject_type = 'REMEDIATION_PROPOSAL'
              AND ts.metadata->>'finding_id' = %s
            ORDER BY t.created_at DESC LIMIT 1;
        """, (finding_id,))
        row = cur.fetchone()
        if not row:
            return {"has_ticket": False, "ticket": None}

        ticket_detail = SodService.get_ticket_detail(str(row["ticket_id"]), conn)
        ticket_detail["subject_version"] = row["subject_version"]
        ticket_detail["subject_hash"] = row["subject_hash"]
        ticket_detail["ticket_id"] = str(row["ticket_id"])
        ticket_detail["ticket_code"] = row["ticket_code"]
        ticket_detail["ticket_status"] = row["ticket_status"]
        ticket_detail["is_done"] = (row["ticket_status"] == "DONE")

        res = dict(ticket_detail)
        res["has_ticket"] = True
        res["ticket"] = ticket_detail
        return res

