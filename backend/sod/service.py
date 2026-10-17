"""
SoD Flow Service: Core Business Operations with Transaction Concurrency & Fail-Closed Security.
1:1 Fidelity with sod-production.
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException
from psycopg2.extras import RealDictCursor

from backend.sod.catalog import DEFAULT_MATRIX, ROLES, act_name
from backend.sod.classifier import classify_ticket, form_priority
from backend.sod.chain_builder import build_approval_chain
from backend.sod.conflict_detector import auto_assign_steps

logger = logging.getLogger("DataTrust.SoDService")


class SodConfigurationUnavailableException(HTTPException):
    def __init__(self, detail: str = "Hệ thống SoD tạm dừng xử lý: Không tìm thấy phiên bản ma trận RACIX hợp lệ trong CSDL."):
        super().__init__(status_code=503, detail=detail)


class SodService:
    @staticmethod
    def get_active_matrix(conn) -> Tuple[str, int, List[str]]:
        """
        FAIL-CLOSED SECURITY: Bắt buộc đọc từ sod.config_versions WHERE status = 'ACTIVE'.
        Tuyệt đối không dùng hardcode fallback trong runtime.
        """
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, seq, config
                FROM sod.config_versions
                WHERE status = 'ACTIVE'
                ORDER BY seq DESC
                LIMIT 1;
            """)
            row = cur.fetchone()
            if not row or not row.get("config"):
                logger.critical("FAIL-CLOSED: Không có bản ghi ma trận RACIX ACTIVE trong CSDL!")
                raise SodConfigurationUnavailableException()

            config = row["config"]
            matrix = config.get("matrix")
            if not matrix or not isinstance(matrix, list):
                logger.critical("FAIL-CLOSED: Ma trận ACTIVE bị lỗi định dạng!")
                raise SodConfigurationUnavailableException("Dữ liệu cấu hình ma trận RACIX không hợp lệ.")

            return str(row["id"]), int(row["seq"]), matrix

    @staticmethod
    def get_eligible_people(conn) -> List[Dict[str, Any]]:
        """Lấy danh sách người dùng và các vai trò hiệu lực từ CSDL."""
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT u.id, u.full_name as name, u.username,
                       array_agg(ur.role_code) FILTER (WHERE ur.role_code IS NOT NULL) as roles
                FROM sod.users u
                JOIN sod.user_roles ur ON u.id = ur.user_id
                WHERE u.is_active = TRUE
                  AND ur.valid_from <= now()
                  AND (ur.valid_to IS NULL OR ur.valid_to > now())
                  AND ur.revoked_at IS NULL
                GROUP BY u.id, u.full_name, u.username;
            """)
            rows = cur.fetchall()
            return [
                {"id": str(r["id"]), "name": r["name"], "username": r["username"], "roles": r["roles"] or []}
                for r in rows
            ]

    @staticmethod
    def preview_chain(form: Dict[str, Any], requester_id: str, conn) -> Dict[str, Any]:
        """Sinh chuỗi duyệt xem trước phía server theo phiên bản ma trận ACTIVE."""
        config_id, config_seq, matrix = SodService.get_active_matrix(conn)
        cl = classify_ticket(form, matrix)
        chain = build_approval_chain(cl, requester_id, matrix)
        people = SodService.get_eligible_people(conn)
        auto_assign_steps(chain["steps"], requester_id, people)
        chain["config_version_id"] = config_id
        chain["config_seq"] = config_seq
        return chain

    @staticmethod
    def create_ticket(form: Dict[str, Any], requester_id: str, conn) -> Dict[str, Any]:
        """Tạo phiếu đề nghị mới kèm snapshot phiên bản ma trận và hàm băm form_hash."""
        config_id, config_seq, matrix = SodService.get_active_matrix(conn)
        cl = classify_ticket(form, matrix)
        chain = build_approval_chain(cl, requester_id, matrix)
        people = SodService.get_eligible_people(conn)
        auto_assign_steps(chain["steps"], requester_id, people)

        form_json_str = json.dumps(form, sort_keys=True)
        form_hash = hashlib.sha256(form_json_str.encode("utf-8")).hexdigest()
        priority = form_priority(form)

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1. Sinh mã phiếu tự động
            cur.execute("SELECT sod.next_ticket_code() as code, nextval('sod.ticket_code_seq') as seq;")
            gen = cur.fetchone()
            ticket_code = gen["code"]
            ticket_seq = gen["seq"]

            # 2. Lưu ticket
            cur.execute("""
                INSERT INTO sod.tickets (
                    code, seq, kind, status, priority, level, pii, break_glass,
                    config_version_id, config_seq, form, form_hash,
                    acts, phases, requester_id, current_step_idx, total_steps
                ) VALUES (
                    %s, %s, %s, 'OPEN', %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, 1, %s
                ) RETURNING id;
            """, (
                ticket_code, ticket_seq, cl["type"]["id"], priority, cl["level"], cl["pii"], cl["break_glass"],
                config_id, config_seq, json.dumps(form), form_hash,
                cl["acts"], json.dumps(chain["phases"]), requester_id, len(chain["steps"])
            ))
            ticket_id = str(cur.fetchone()["id"])

            # 3. Lưu các bước duyệt
            step_ids = {}
            for s in chain["steps"]:
                cur.execute("""
                    INSERT INTO sod.ticket_steps (
                        ticket_id, idx, phase, key, role_code, action, acts,
                        assignee_id, status, sla_hours, started_at, due_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s,
                        CASE WHEN %s = 'CURRENT' THEN now() ELSE NULL END,
                        CASE WHEN %s = 'CURRENT' THEN now() + (%s || ' hours')::interval ELSE NULL END
                    ) RETURNING id;
                """, (
                    ticket_id, s["idx"], s["phase"], s["key"], s["role"], s["action"], [str(a) for a in s["acts"]],
                    s.get("assignee_id"), s["status"], s.get("sla_hours", 24),
                    s["status"], s["status"], s.get("sla_hours", 24)
                ))
                step_ids[s["idx"]] = str(cur.fetchone()["id"])

            # Bước 0: Tạo quyết định SUBMIT (Khởi tạo)
            s0_id = step_ids[0]
            cur.execute("""
                INSERT INTO sod.step_decisions (step_id, actor_id, outcome, comment, form_hash, rev)
                VALUES (%s, %s, 'SUBMIT', 'Khởi tạo phiếu đề nghị cấp quyền', %s, 1);
            """, (s0_id, requester_id, form_hash))

            # Cập nhật active_step_id trỏ vào bước 1
            s1_id = step_ids.get(1)
            if s1_id:
                cur.execute("UPDATE sod.tickets SET active_step_id = %s WHERE id = %s;", (s1_id, ticket_id))

            conn.commit()

        return SodService.get_ticket_detail(ticket_id, conn)

    @staticmethod
    def get_tickets(conn, status: Optional[str] = None, role: Optional[str] = None) -> List[Dict[str, Any]]:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
                SELECT t.id, t.code, t.kind, t.status, t.priority, t.level, t.pii, t.config_seq,
                       t.current_step_idx, t.total_steps, t.created_at, t.closed_at,
                       u.full_name as requester_name, u.username as requester_username,
                       t.form->>'mucDich' as purpose,
                       COALESCE(t.form->'rows'->0->>'heThong', t.form->>'system') as system,
                       COALESCE(t.form->'rows'->0->>'mucQuyen', t.form->>'access_level') as access_level,
                       ts.subject_id as proposal_id,
                       ts.subject_version as proposal_version,
                       ts.subject_hash as dry_run_hash,
                       ts.source_snapshot_hash as source_hash,
                       ts.metadata->>'finding_id' as finding_id,
                       ts.metadata->>'dataset_id' as dataset_id,
                       ts.metadata->>'column' as column_name,
                       (
                           SELECT json_agg(json_build_object(
                               'id', s.id,
                               'idx', s.idx,
                               'role', s.role_code,
                               'role_code', s.role_code,
                               'action', s.action,
                               'status', s.status,
                               'sla_hours', s.sla_hours,
                               'assignee_name', COALESCE(su.full_name, s.role_code),
                               'assignee_username', COALESCE(su.username, lower(s.role_code))
                           ) ORDER BY s.idx)
                           FROM sod.ticket_steps s
                           LEFT JOIN sod.users su ON s.assignee_id = su.id
                           WHERE s.ticket_id = t.id
                       ) as steps
                FROM sod.tickets t
                JOIN sod.users u ON t.requester_id = u.id
                LEFT JOIN sod.ticket_subjects ts ON t.id = ts.ticket_id
                WHERE 1=1
            """
            params = []
            if status:
                query += " AND t.status = %s"
                params.append(status.upper())
            query += " ORDER BY t.created_at DESC;"
            cur.execute(query, params)
            rows = [dict(r) for r in cur.fetchall()]
            for r in rows:
                if not r.get("steps"):
                    r["steps"] = []
            return rows

    @staticmethod
    def get_ticket_detail(ticket_id: str, conn) -> Dict[str, Any]:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT t.*, u.full_name as requester_name, u.username as requester_username
                FROM sod.tickets t
                JOIN sod.users u ON t.requester_id = u.id
                WHERE t.id = %s;
            """, (ticket_id,))
            ticket = cur.fetchone()
            if not ticket:
                raise HTTPException(status_code=404, detail="Không tìm thấy phiếu yêu cầu")

            # Lấy các bước duyệt
            cur.execute("""
                SELECT s.*, u.full_name as assignee_name, u.username as assignee_username
                FROM sod.ticket_steps s
                LEFT JOIN sod.users u ON s.assignee_id = u.id
                WHERE s.ticket_id = %s
                ORDER BY s.idx ASC;
            """, (ticket_id,))
            steps = cur.fetchall()

            # Lấy quyết định
            cur.execute("""
                SELECT d.*, u.full_name as actor_name, u.username as actor_username,
                       ob.full_name as on_behalf_name
                FROM sod.step_decisions d
                JOIN sod.users u ON d.actor_id = u.id
                LEFT JOIN sod.users ob ON d.on_behalf_of = ob.id
                JOIN sod.ticket_steps s ON d.step_id = s.id
                WHERE s.ticket_id = %s
                ORDER BY d.decided_at ASC;
            """, (ticket_id,))
            decisions = cur.fetchall()

            # Lấy subject liên kết DataTrust Remediation Proposal (nếu có)
            cur.execute("""
                SELECT * FROM sod.ticket_subjects WHERE ticket_id = %s;
            """, (ticket_id,))
            subj = cur.fetchone()

            res = dict(ticket)
            decisions_by_step = {}
            for d in decisions:
                decisions_by_step[str(d["step_id"])] = d

            steps_list = []
            for s in steps:
                step_dict = dict(s)
                step_dict["role"] = step_dict.get("role_code")
                step_dict["assigneeName"] = step_dict.get("assignee_name") or step_dict.get("role_code")
                step_dict["assigneeUsername"] = step_dict.get("assignee_username") or (step_dict.get("role_code") or "").lower()
                step_dict["slaHours"] = step_dict.get("sla_hours") or 24
                d = decisions_by_step.get(str(s["id"]))
                if d:
                    step_dict["decisionNote"] = d.get("comment")
                    step_dict["decidedAt"] = str(d.get("decided_at"))
                steps_list.append(step_dict)

            res["steps"] = steps_list
            res["decisions"] = [dict(d) for d in decisions]
            if subj:
                meta = subj.get("metadata") or {}
                res["subject"] = {
                    "subject_type": subj["subject_type"],
                    "proposal_id": subj["subject_id"],
                    "proposal_version": subj["subject_version"],
                    "dry_run_hash": subj["subject_hash"],
                    "source_hash": subj["source_snapshot_hash"],
                    "finding_id": meta.get("finding_id"),
                    "dataset_id": meta.get("dataset_id"),
                    "column_name": meta.get("column"),
                    "expected_rows": meta.get("quarantine_count"),
                    "metadata": meta,
                }
            return res

    @staticmethod
    def decide_step(
        ticket_id: str,
        step_id: str,
        actor_id: str,
        outcome: str,
        comment: str,
        conn,
        reconciliation: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Ghi nhận quyết định phê duyệt với TRANSACTION CONCURRENCY LOCK (SELECT FOR UPDATE).
        Kích hoạt trigger step_decision_guard kiểm tra No Self-Approval và No Dual-Role.
        Hỗ trợ quy trình Đối soát Kế toán thủ công (MANUAL_RECONCILIATION) khi SO gửi reconciliation payload.
        """
        outcome_norm = outcome.upper()
        if outcome_norm not in ("APPROVE", "RETURN", "REJECT", "COMPLETE"):
            raise HTTPException(status_code=400, detail=f"Kết quả quyết định '{outcome}' không hợp lệ.")

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1. LOCK BƯỚC ĐANG DUYỆT (Chống concurrent approval)
            cur.execute("SELECT * FROM sod.ticket_steps WHERE id = %s FOR UPDATE;", (step_id,))
            step = cur.fetchone()
            if not step:
                raise HTTPException(status_code=404, detail="Không tìm thấy bước duyệt.")
            if str(step["ticket_id"]) != str(ticket_id):
                raise HTTPException(status_code=404, detail="Bước duyệt không thuộc phiếu yêu cầu này.")
            if step["status"] != "CURRENT":
                raise HTTPException(status_code=409, detail=f"Bước này không ở trạng thái chờ duyệt (hiện tại: {step['status']}).")

            # 2. LOCK TICKET
            cur.execute("SELECT * FROM sod.tickets WHERE id = %s FOR UPDATE;", (ticket_id,))
            ticket = cur.fetchone()
            if not ticket or ticket["status"] != "OPEN":
                raise HTTPException(status_code=409, detail="Phiếu này đã đóng hoặc không hợp lệ.")

            # 2b. Kiểm tra quy trình đối soát thủ công (requires_human_input) nếu là bước SO
            cur.execute("""
                SELECT ts.subject_type, ts.subject_id, ts.subject_version, ts.subject_hash,
                       p.requires_human_input, p.target_column, p.dataset_id, p.finding_id,
                       p.params, p.source_snapshot_hash, p.expected_rows, p.target_quarantine_ids, p.operation_id
                FROM sod.ticket_subjects ts
                JOIN remediation.proposals p ON ts.subject_id = p.proposal_id
                WHERE ts.ticket_id = %s;
            """, (ticket_id,))
            prop_meta = cur.fetchone()

            if prop_meta and prop_meta.get("requires_human_input") and step["role_code"] == "SO":
                if outcome_norm in ("APPROVE", "COMPLETE"):
                    if not reconciliation or reconciliation.get("corrected_value") is None or str(reconciliation.get("corrected_value")).strip() == "":
                        raise HTTPException(
                            status_code=400,
                            detail="Bước đối soát của SO bắt buộc phải nhập giá trị đã đối soát (corrected_value), tiền tệ, lý do và chứng từ đối soát (evidence_doc_ref)."
                        )
                    if not reconciliation.get("evidence_doc_ref"):
                        raise HTTPException(
                            status_code=400,
                            detail="Bước đối soát của SO bắt buộc phải đính kèm mã chứng từ hoặc tài liệu đối soát (evidence_doc_ref)."
                        )

                    # Validate post-check trên corrected_value
                    from backend.engine.remediation_registry import RemediationRegistry
                    passed, pc_err = RemediationRegistry.run_post_check(
                        dataset_id=prop_meta["dataset_id"],
                        column=prop_meta["target_column"],
                        before_val=None,
                        cleaned_val=reconciliation["corrected_value"]
                    )
                    if not passed:
                        raise HTTPException(status_code=400, detail=f"Giá trị đối soát vi phạm post-check: {pc_err}")

                    # Cập nhật proposal params với giá trị đối soát
                    current_params = prop_meta["params"] if isinstance(prop_meta["params"], dict) else json.loads(prop_meta["params"] or "{}")
                    current_params["corrected_value"] = reconciliation["corrected_value"]
                    current_params["currency"] = reconciliation.get("currency", "VND")
                    current_params["reconciliation_reason"] = reconciliation.get("reason", comment)
                    current_params["evidence_doc_ref"] = reconciliation["evidence_doc_ref"]

                    new_version = prop_meta["subject_version"] + 1
                    proposal_data = {
                        "finding_id": prop_meta["finding_id"],
                        "target": {
                            "dataset_id": prop_meta["dataset_id"],
                            "column": prop_meta["target_column"],
                            "quarantine_ids": prop_meta["target_quarantine_ids"]
                        },
                        "operation_id": prop_meta["operation_id"],
                        "params": current_params,
                        "expected_rows": prop_meta["expected_rows"],
                        "source_snapshot_hash": prop_meta["source_snapshot_hash"],
                        "version": new_version
                    }
                    from backend.ai.services.remediation_service import compute_hash, remediation_service
                    new_prop_hash = compute_hash(proposal_data)

                    # Cập nhật proposal trong CSDL
                    cur.execute("""
                        UPDATE remediation.proposals
                        SET version = %s,
                            params = %s,
                            proposal_hash = %s,
                            status = 'PENDING_SOD_APPROVAL',
                            updated_at = NOW()
                        WHERE proposal_id = %s;
                    """, (new_version, json.dumps(current_params), new_prop_hash, prop_meta["subject_id"]))

                    # Cập nhật snapshot liên kết phiên bản trong sod.ticket_subjects
                    cur.execute("""
                        UPDATE sod.ticket_subjects
                        SET subject_version = %s,
                            subject_hash = %s
                        WHERE ticket_id = %s;
                    """, (new_version, new_prop_hash, ticket_id))

                    # Chạy lại Dry-run in-memory với corrected_value
                    try:
                        mem_prop = remediation_service.get_proposal(prop_meta["subject_id"])
                        if mem_prop:
                            mem_prop.params = current_params
                            mem_prop.version = new_version
                            remediation_service.simulate_dry_run(prop_meta["subject_id"])
                    except Exception as dry_re_err:
                        logger.warning(f"Dry-run rerun on reconciliation notice: {dry_re_err}")

            # 3. GHI QUYẾT ĐỊNH (Kích hoạt DB Trigger step_decision_guard)
            form_hash = ticket["form_hash"]
            decision_comment = comment or ("Hoàn thành bước đối soát kế toán" if reconciliation else "")
            cur.execute("""
                INSERT INTO sod.step_decisions (step_id, actor_id, outcome, comment, form_hash, rev)
                VALUES (%s, %s, %s, %s, %s, 1);
            """, (step_id, actor_id, outcome_norm, decision_comment, form_hash))

            # 4. CHUYỂN TRẠNG THÁI BƯỚC & TICKET
            current_idx = step["idx"]
            if outcome_norm in ("APPROVE", "COMPLETE"):
                cur.execute("UPDATE sod.ticket_steps SET status = 'DONE' WHERE id = %s;", (step_id,))

                # Kiểm tra xem có bước tiếp theo không
                cur.execute("""
                    SELECT id, sla_hours FROM sod.ticket_steps
                    WHERE ticket_id = %s AND idx = %s;
                """, (ticket_id, current_idx + 1))
                next_step = cur.fetchone()

                if next_step:
                    sla = next_step["sla_hours"] or 24
                    cur.execute("""
                        UPDATE sod.ticket_steps
                        SET status = 'CURRENT', started_at = now(), due_at = now() + (%s || ' hours')::interval
                        WHERE id = %s;
                    """, (sla, next_step["id"]))
                    cur.execute("""
                        UPDATE sod.tickets
                        SET current_step_idx = %s, active_step_id = %s, updated_at = now()
                        WHERE id = %s;
                    """, (current_idx + 1, next_step["id"], ticket_id))
                else:
                    # Hoàn tất phiếu
                    cur.execute("""
                        UPDATE sod.tickets
                        SET status = 'DONE', closed_at = now(), active_step_id = NULL, updated_at = now()
                        WHERE id = %s;
                    """, (ticket_id,))

                    # Phase 3 Cross-System Hook: Đồng bộ trạng thái và ghi nhận SOD_REMEDIATION_APPROVED
                    try:
                        cur.execute("""
                            SELECT subject_type, subject_id, subject_version, subject_hash, metadata
                            FROM sod.ticket_subjects
                            WHERE ticket_id = %s;
                        """, (ticket_id,))
                        subject = cur.fetchone()
                        if subject and subject["subject_type"] == "REMEDIATION_PROPOSAL":
                            prop_id = subject["subject_id"]
                            meta = subject.get("metadata") or {}
                            finding_id = meta.get("finding_id")
                            dataset_id = meta.get("dataset_id") or "quarantine"

                            from backend.sod.integration_service import append_audit_evidence_safely
                            approval_ev = append_audit_evidence_safely(
                                cur=cur,
                                event_type="SOD_REMEDIATION_APPROVED",
                                run_id=meta.get("run_id") or "RUN-SOD-APPROVAL",
                                dataset_id=dataset_id,
                                payload={
                                    "event": "SOD_REMEDIATION_APPROVED",
                                    "ticket_id": str(ticket_id),
                                    "ticket_code": ticket["code"],
                                    "proposal_id": prop_id,
                                    "proposal_version": subject["subject_version"],
                                    "proposal_hash": subject["subject_hash"],
                                    "finding_id": finding_id,
                                    "approved_at": datetime.now(timezone.utc).isoformat()
                                }
                            )

                            cur.execute("""
                                UPDATE remediation.proposals
                                SET status = 'APPROVED', approval_evidence_id = %s, updated_at = now()
                                WHERE proposal_id = %s;
                            """, (approval_ev["evidence_id"], prop_id))

                            if finding_id:
                                cur.execute("""
                                    UPDATE audit.findings
                                    SET sod_approval_status = 'APPROVED'
                                    WHERE finding_id = %s;
                                """, (finding_id,))
                    except Exception as hook_err:
                        conn.rollback()
                        logger.exception("Phase 3 SoD completion hook failed; transaction rolled back")
                        raise HTTPException(status_code=503, detail="Không thể đồng bộ kết quả SoD sang hệ thống khắc phục.") from hook_err
            elif outcome_norm == "REJECT":
                cur.execute("UPDATE sod.ticket_steps SET status = 'REJECTED' WHERE id = %s;", (step_id,))
                cur.execute("""
                    UPDATE sod.tickets
                    SET status = 'REJECTED', closed_at = now(), active_step_id = NULL, updated_at = now()
                    WHERE id = %s;
                """, (ticket_id,))

                # Phase 3 Cross-System Rejection Hook
                try:
                    cur.execute("""
                        SELECT subject_type, subject_id, metadata
                        FROM sod.ticket_subjects
                        WHERE ticket_id = %s;
                    """, (ticket_id,))
                    subject = cur.fetchone()
                    if subject and subject["subject_type"] == "REMEDIATION_PROPOSAL":
                        prop_id = subject["subject_id"]
                        meta = subject.get("metadata") or {}
                        finding_id = meta.get("finding_id")

                        cur.execute("""
                            UPDATE remediation.proposals
                            SET status = 'REJECTED', updated_at = now()
                            WHERE proposal_id = %s;
                        """, (prop_id,))

                        if finding_id:
                            cur.execute("""
                                UPDATE audit.findings
                                SET sod_approval_status = 'REJECTED'
                                WHERE finding_id = %s;
                            """, (finding_id,))
                except Exception as hook_err:
                    conn.rollback()
                    logger.exception("Phase 3 SoD rejection hook failed; transaction rolled back")
                    raise HTTPException(status_code=503, detail="Không thể đồng bộ kết quả từ chối SoD sang hệ thống khắc phục.") from hook_err
            elif outcome_norm == "RETURN":
                cur.execute("UPDATE sod.ticket_steps SET status = 'RETURNED' WHERE id = %s;", (step_id,))
                cur.execute("""
                    UPDATE sod.tickets
                    SET status = 'RETURNED', updated_at = now()
                    WHERE id = %s;
                """, (ticket_id,))

                # Phase 3 Cross-System Return Hook: Đưa proposal về DRAFT để chỉnh sửa
                try:
                    cur.execute("""
                        SELECT subject_type, subject_id, metadata
                        FROM sod.ticket_subjects
                        WHERE ticket_id = %s;
                    """, (ticket_id,))
                    subject = cur.fetchone()
                    if subject and subject["subject_type"] == "REMEDIATION_PROPOSAL":
                        prop_id = subject["subject_id"]
                        meta = subject.get("metadata") or {}
                        finding_id = meta.get("finding_id")

                        cur.execute("""
                            UPDATE remediation.proposals
                            SET status = 'DRAFT', updated_at = now()
                            WHERE proposal_id = %s;
                        """, (prop_id,))

                        if finding_id:
                            cur.execute("""
                                UPDATE audit.findings
                                SET sod_approval_status = 'RETURNED'
                                WHERE finding_id = %s;
                            """, (finding_id,))
                except Exception as hook_err:
                    conn.rollback()
                    logger.exception("Phase 3 SoD return hook failed; transaction rolled back")
                    raise HTTPException(status_code=503, detail="Không thể đồng bộ kết quả hoàn trả SoD sang hệ thống khắc phục.") from hook_err

            conn.commit()

        return SodService.get_ticket_detail(ticket_id, conn)

    @staticmethod
    def get_inbox(user_id: str, active_role: str, conn) -> List[Dict[str, Any]]:
        """Lấy danh sách các bước đang chờ duyệt (CURRENT) được giao cho user hoặc user được ủy quyền."""
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if active_role in ("ADMIN", "AUDITOR"):
                cur.execute("""
                    SELECT s.id as step_id, s.idx as step_idx, s.role_code, s.action, s.sla_hours, s.due_at,
                           t.id as ticket_id, t.code as ticket_code, t.priority, t.level, t.pii,
                           u.full_name as requester_name,
                           t.form->'rows'->0->>'heThong' as system,
                           t.form->'rows'->0->>'mucQuyen' as access_level,
                           t.form->>'mucDich' as purpose,
                           CASE WHEN s.assignee_id = %s THEN FALSE ELSE TRUE END as is_delegated
                    FROM sod.ticket_steps s
                    JOIN sod.tickets t ON s.ticket_id = t.id
                    JOIN sod.users u ON t.requester_id = u.id
                    WHERE s.status = 'CURRENT'
                      AND t.status = 'OPEN'
                    ORDER BY t.priority = 'urgent' DESC, s.due_at ASC;
                """, (user_id,))
            else:
                cur.execute("""
                    SELECT s.id as step_id, s.idx as step_idx, s.role_code, s.action, s.sla_hours, s.due_at,
                           t.id as ticket_id, t.code as ticket_code, t.priority, t.level, t.pii,
                           u.full_name as requester_name,
                           t.form->'rows'->0->>'heThong' as system,
                           t.form->'rows'->0->>'mucQuyen' as access_level,
                           t.form->>'mucDich' as purpose,
                           CASE WHEN s.assignee_id = %s THEN FALSE ELSE TRUE END as is_delegated
                    FROM sod.ticket_steps s
                    JOIN sod.tickets t ON s.ticket_id = t.id
                    JOIN sod.users u ON t.requester_id = u.id
                    WHERE s.status = 'CURRENT'
                      AND t.status = 'OPEN'
                      AND (
                          (s.assignee_id = %s AND s.role_code = %s)
                          OR (s.assignee_id IS NULL AND s.role_code = %s)
                          OR EXISTS (
                              SELECT 1 FROM sod.delegations d
                              WHERE d.delegator_id = s.assignee_id
                                AND d.delegate_id = %s
                                AND d.role_code = s.role_code
                                AND d.valid_from <= now() AND d.valid_to > now()
                                AND d.revoked_at IS NULL
                          )
                      )
                    ORDER BY t.priority = 'urgent' DESC, s.due_at ASC;
                """, (user_id, user_id, active_role, active_role, user_id))
            return [dict(r) for r in cur.fetchall()]

    @staticmethod
    def generate_integrity_evidence(ticket_id: str, conn) -> Dict[str, Any]:
        """Tạo chứng từ kiểm toán toàn vẹn kèm hàm băm SHA-256 (Integrity Hash)."""
        detail = SodService.get_ticket_detail(ticket_id, conn)
        evidence_payload = {
            "ticket_code": detail["code"],
            "config_version_seq": detail["config_seq"],
            "requester": detail["requester_name"],
            "form_hash": detail["form_hash"],
            "decisions": [
                {
                    "outcome": d["outcome"],
                    "actor": d["actor_name"],
                    "decided_at": str(d["decided_at"]),
                    "form_hash": d["form_hash"],
                }
                for d in detail["decisions"]
            ]
        }
        canonical_str = json.dumps(evidence_payload, sort_keys=True)
        integrity_hash = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

        return {
            "ticket": detail,
            "evidence_payload": evidence_payload,
            "integrity_hash": integrity_hash,
            "hash_algorithm": "SHA-256 (Append-Only Verification)",
        }
