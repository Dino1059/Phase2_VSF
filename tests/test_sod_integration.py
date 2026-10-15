"""
Tích hợp duyệt qua SoD Flow (KE_HOACH_SOD_DATATRUST.md mục 6): đề xuất ≠ duyệt ≠ thực thi. SoD Flow được thay bằng bản giả (monkeypatch),
nên chạy được không cần SoD. Kịch bản đầu-cuối với SoD thật: scripts/e2e_sod_datatrust.py.
"""
import json
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from backend.ai.services.remediation_service import (
    RemediationService,
    SodManagedProposal,
    StaleProposal,
    compute_hash,
    content_hash,
    remediation_service,
)
from backend.api.main import app
from backend.database.models import ProposalStatus
from backend.integrations import sod_client
from database.profiler_engine import get_db_connection

SECRET = "s" * 40
STEWARD = "an.nguyen"          # người gửi duyệt (Requestor)
APPROVERS = ["giang.hoang", "dung.pham"]
EXECUTOR = "phong.ta"          # Prod. Op. được SoD giao thực thi


@pytest.fixture
def quarantine():
    conn = get_db_connection()
    q_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    run_id = f"RUN-SODTEST-{uuid.uuid4().hex[:6]}"
    with conn.cursor() as cur:
        for i, qid in enumerate(q_ids):
            raw = {"trip_id": f"S{i}", "customer_phone": f"09123456{i}7"}
            cur.execute(
                """INSERT INTO quarantine.records (quarantine_id,run_id,dataset_id,source_table,source_row_pk,failure_lane,
                   violation_column,violation_rule_id,violation_reason,violation_severity,raw_record_json,lineage_hash,status,quarantined_at)
                   VALUES (%s,%s,'trips','bronze.trips',%s,'LANE_B','customer_phone','R','x','HIGH',%s,%s,'QUARANTINED',CURRENT_TIMESTAMP)""",
                (qid, run_id, f"PK{i}", json.dumps(raw), compute_hash(raw)),
            )
    conn.commit()
    conn.close()
    created = []
    yield {"run_id": run_id, "q_ids": q_ids, "created": created}
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM quarantine.records WHERE quarantine_id::text = ANY(%s)", (q_ids,))
        cur.execute("DELETE FROM staging.remediated_records WHERE quarantine_id::text = ANY(%s)", (q_ids,))
        cur.execute("DELETE FROM governance.remediation_proposals WHERE proposal_id = ANY(%s)", (created,))
        cur.execute("DELETE FROM governance.integration_events WHERE ticket_code LIKE 'SOD-TEST-%%'")
    conn.commit()
    conn.close()


def _proposal(data, proposer="AI_AGENT"):
    p = remediation_service.create_proposal(
        finding_id=f"FINDING-SODTEST-{uuid.uuid4().hex[:6]}",
        run_id=data["run_id"], dataset_id="trips", column="customer_phone", quarantine_ids=data["q_ids"],
        operation_id="MASK_PHONE", params={"prefix_len": 3, "suffix_len": 2, "mask_char": "*"},
        reason="Che số điện thoại dạng rõ", proposer=proposer,
    )
    data["created"].append(p.proposal_id)
    remediation_service.simulate_dry_run(p.proposal_id)
    return remediation_service.proposals[p.proposal_id]


@pytest.fixture
def fake_sod(monkeypatch):
    """SoD giả: ghi lại yêu cầu và trả mã phiếu."""
    calls = {"create": [], "executed": [], "available": True}

    def create_ticket(payload):
        if not calls["available"]:
            raise sod_client.SodUnavailable("SoD tắt")
        calls["create"].append(payload)
        # Mã phải duy nhất giữa các test: service dùng chung một bộ nhớ đề xuất
        return {"ticket_code": f"SOD-TEST-{uuid.uuid4().hex[:8].upper()}", "status": "OPEN", "created": True, "steps": []}

    def report_executed(code, payload):
        calls["executed"].append((code, payload))
        return {"ok": True}

    monkeypatch.setattr(sod_client, "create_ticket", create_ticket)
    monkeypatch.setattr(sod_client, "report_executed", report_executed)
    return calls


def _approved(data, fake_sod, who=STEWARD, executor=EXECUTOR, approvers=APPROVERS):
    p = _proposal(data)
    remediation_service.submit_to_sod(p.proposal_id, who)
    assert p.sod_ticket_code
    assert remediation_service.apply_sod_status(p, "APPROVED", p.sod_form_hash, executor, approvers)
    return p


# ---------------------------------------------------------------- Bước 3: gửi duyệt

def test_submit_to_sod_sends_description_only_and_links_ticket(quarantine, fake_sod):
    p = _proposal(quarantine)
    remediation_service.submit_to_sod(p.proposal_id, STEWARD)
    assert p.status == ProposalStatus.PENDING_APPROVAL and p.sod_ticket_code.startswith("SOD-TEST-")
    sent = fake_sod["create"][0]
    assert sent["requesterUsername"] == STEWARD and sent["externalRef"] == p.proposal_id
    assert sent["proposalHash"] == content_hash(p) == p.sod_form_hash and len(sent["proposalHash"]) == 64
    assert sent["pii"] is True  # MASK_PHONE chạm dữ liệu cá nhân
    # Không có giá trị dữ liệu trong phiếu
    assert "0912345" not in json.dumps(sent)


def test_llm_cannot_submit_for_approval(quarantine, fake_sod):
    p = _proposal(quarantine)
    for who in ("AI_AGENT", "", "ai_agent"):
        with pytest.raises(PermissionError):
            remediation_service.submit_to_sod(p.proposal_id, who)
    assert p.status == ProposalStatus.DRY_RUN_PASSED and not fake_sod["create"]


def test_sod_down_keeps_proposal_pending_submit_never_approved(quarantine, fake_sod):
    fake_sod["available"] = False
    p = _proposal(quarantine)
    remediation_service.submit_to_sod(p.proposal_id, STEWARD)
    assert p.status == ProposalStatus.PENDING_SUBMIT and p.sod_ticket_code is None and p.sod_requester == STEWARD
    # Người khác không gửi lại hộ được; SoD bật lại thì người đã gửi gửi lại được
    fake_sod["available"] = True
    with pytest.raises(PermissionError):
        remediation_service.submit_to_sod(p.proposal_id, "nguoi.khac")
    remediation_service.submit_to_sod(p.proposal_id, STEWARD)
    assert p.status == ProposalStatus.PENDING_APPROVAL and p.sod_ticket_code


# ---------------------------------------------------------------- Bước 4: nhận kết quả

def test_approved_event_records_executor_and_is_idempotent(quarantine, fake_sod):
    p = _proposal(quarantine)
    remediation_service.submit_to_sod(p.proposal_id, STEWARD)
    assert remediation_service.apply_sod_status(p, "APPROVED", p.sod_form_hash, "Phong.Ta ", ["GIANG.HOANG", "dung.pham"]) is True
    assert p.status == ProposalStatus.APPROVED and p.approved_by == f"SoD:{p.sod_ticket_code}"
    assert p.sod_executor == EXECUTOR and p.sod_approvers == sorted(APPROVERS)
    assert remediation_service.apply_sod_status(p, "APPROVED", p.sod_form_hash, "nguoi.khac") is False  # áp lại: không làm gì
    assert remediation_service.apply_sod_status(p, "DONE", p.sod_form_hash) is False  # DONE sau khi thực thi: không đổi
    assert remediation_service.apply_sod_status(p, "REJECTED", p.sod_form_hash) is False  # không hạ cấp đề xuất đã duyệt
    assert p.sod_executor == EXECUTOR


@pytest.mark.parametrize("sod_status", ["REJECTED", "CANCELLED", "EXPIRED"])
def test_closed_without_approval_rejects(quarantine, fake_sod, sod_status):
    p = _proposal(quarantine)
    remediation_service.submit_to_sod(p.proposal_id, STEWARD)
    remediation_service.apply_sod_status(p, sod_status, p.sod_form_hash)
    assert p.status == ProposalStatus.REJECTED and sod_status in (p.reject_reason or "")


def test_done_event_with_different_hash_makes_proposal_stale(quarantine, fake_sod):
    p = _proposal(quarantine)
    remediation_service.submit_to_sod(p.proposal_id, STEWARD)
    remediation_service.apply_sod_status(p, "DONE", "0" * 64)
    assert p.status == ProposalStatus.STALE


def test_proposals_survive_restart(quarantine, fake_sod):
    p = _proposal(quarantine)
    remediation_service.submit_to_sod(p.proposal_id, STEWARD)
    reloaded = RemediationService().proposals[p.proposal_id]  # khởi động lại = dựng service mới từ DB
    assert reloaded.status == ProposalStatus.PENDING_APPROVAL and reloaded.sod_ticket_code == p.sod_ticket_code
    assert reloaded.proposal_hash == p.proposal_hash and reloaded.sod_form_hash == p.sod_form_hash


# ---------------------------------------------------------------- Bước 5: khoá duyệt nội bộ, kiểm khi thực thi

def test_internal_approve_and_reject_are_locked_when_ticket_exists(quarantine, fake_sod):
    p = _proposal(quarantine)
    remediation_service.submit_to_sod(p.proposal_id, STEWARD)
    with pytest.raises(SodManagedProposal):
        remediation_service.approve_proposal(p.proposal_id, actor_id="admin", actor_role="ADMIN")
    with pytest.raises(SodManagedProposal):
        remediation_service.reject_proposal(p.proposal_id, actor_id="admin", reason="x")
    assert p.status == ProposalStatus.PENDING_APPROVAL


def test_execute_blocked_until_ticket_done(quarantine, fake_sod):
    p = _proposal(quarantine)
    remediation_service.submit_to_sod(p.proposal_id, STEWARD)
    with pytest.raises(PermissionError):
        remediation_service.execute_remediation_transaction(p.proposal_id, STEWARD, "ADMIN")


def test_only_assigned_executor_executes_and_data_changes_once(quarantine, fake_sod):
    p = _approved(quarantine, fake_sod)
    for other in (STEWARD, "giang.hoang", "nguoi.khac", "AI_AGENT"):  # người đề xuất, người duyệt, người lạ, AI
        with pytest.raises(PermissionError):
            remediation_service.execute_remediation_transaction(p.proposal_id, other, "EXECUTOR")
    out = remediation_service.execute_remediation_transaction(p.proposal_id, EXECUTOR.upper(), "EXECUTOR")  # không phân biệt hoa thường
    assert out["status"] == "REMEDIATED" and p.status == ProposalStatus.REMEDIATED
    # Báo SoD đã thực thi, kèm hash đã duyệt và đúng người thực thi
    (code, payload), = fake_sod["executed"]
    assert code == p.sod_ticket_code and payload["proposal_hash"] == p.sod_form_hash and payload["executed_by"] == EXECUTOR
    assert p.sod_execution_reported is True
    with pytest.raises(ValueError):  # lần hai không chạy lại
        remediation_service.execute_remediation_transaction(p.proposal_id, EXECUTOR, "EXECUTOR")


@pytest.mark.parametrize("executor", [STEWARD, "giang.hoang"])
def test_executor_who_proposed_or_approved_is_blocked_even_if_assigned(quarantine, fake_sod, executor):
    """Phòng khi SoD giao nhầm: người thực thi trùng người gửi duyệt hoặc người duyệt thì DataTrust vẫn chặn."""
    p = _approved(quarantine, fake_sod, executor=executor)
    with pytest.raises(PermissionError, match="khác người đề xuất"):
        remediation_service.execute_remediation_transaction(p.proposal_id, executor, "EXECUTOR")
    assert p.status == ProposalStatus.APPROVED and not fake_sod["executed"]


def test_ticket_without_execution_step_cannot_execute(quarantine, fake_sod):
    """Phiếu duyệt theo quy trình cũ (DONE, không có Executor): phải gửi duyệt lại."""
    p = _proposal(quarantine)
    remediation_service.submit_to_sod(p.proposal_id, STEWARD)
    remediation_service.apply_sod_status(p, "DONE", p.sod_form_hash)
    assert p.status == ProposalStatus.APPROVED and p.sod_executor is None
    with pytest.raises(PermissionError, match="Gửi duyệt lại"):
        remediation_service.execute_remediation_transaction(p.proposal_id, STEWARD, "EXECUTOR")


def test_reconcile_picks_up_awaiting_execution(quarantine, fake_sod, monkeypatch):
    p = _proposal(quarantine)
    remediation_service.submit_to_sod(p.proposal_id, STEWARD)
    summary = {
        "ticket_code": p.sod_ticket_code, "status": "OPEN", "awaiting_execution": True, "external_ref": p.proposal_id,
        "proposal_hash": p.sod_form_hash, "executor_username": EXECUTOR,
        "steps": [
            {"idx": 0, "action": "P", "decisions": [{"outcome": "SUBMIT", "actor": STEWARD}]},
            {"idx": 1, "action": "A", "decisions": [{"outcome": "APPROVE", "actor": "giang.hoang"}]},
            {"idx": 2, "action": "P", "decisions": []},
        ],
    }
    monkeypatch.setattr(sod_client, "get_ticket", lambda code: summary)
    assert remediation_service.reconcile_with_sod()["changed"] >= 1
    assert p.status == ProposalStatus.APPROVED and p.sod_executor == EXECUTOR and p.sod_approvers == ["giang.hoang"]


def test_tampered_content_after_approval_becomes_stale_and_does_not_run(quarantine, fake_sod):
    p = _approved(quarantine, fake_sod)
    p.params = {"prefix_len": 0, "suffix_len": 0, "mask_char": "#"}  # đổi nội dung sau khi được duyệt
    with pytest.raises(StaleProposal):
        remediation_service.execute_remediation_transaction(p.proposal_id, EXECUTOR, "EXECUTOR")
    assert p.status == ProposalStatus.STALE
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT status FROM quarantine.records WHERE quarantine_id::text = ANY(%s)", (quarantine["q_ids"],))
        assert {r[0] for r in cur.fetchall()} == {"QUARANTINED"}
    conn.close()


def test_signed_execution_record_includes_ticket_link(quarantine, fake_sod):
    p = _approved(quarantine, fake_sod)
    remediation_service.execute_remediation_transaction(p.proposal_id, EXECUTOR, "EXECUTOR")
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT new_state->'audit_payload' FROM audit.system_audit_trail WHERE entity_id = %s", (p.proposal_id,))
        payload = cur.fetchone()[0]
    conn.close()
    assert payload["sod_ticket_code"] == p.sod_ticket_code and payload["sod_form_hash"] == p.sod_form_hash


def test_failed_report_is_retried_by_reconcile(quarantine, fake_sod, monkeypatch):
    p = _approved(quarantine, fake_sod)
    monkeypatch.setattr(sod_client, "report_executed", lambda *a, **k: (_ for _ in ()).throw(sod_client.SodUnavailable("tắt")))
    remediation_service.execute_remediation_transaction(p.proposal_id, EXECUTOR, "EXECUTOR")
    assert p.status == ProposalStatus.REMEDIATED and p.sod_execution_reported is False  # đã thực thi, chưa báo được
    monkeypatch.setattr(sod_client, "report_executed", lambda code, payload: {"ok": True})
    assert remediation_service.reconcile_with_sod()["reported"] >= 1
    assert p.sod_execution_reported is True


# ---------------------------------------------------------------- API và chữ ký

@pytest.fixture
def api(monkeypatch):
    monkeypatch.setattr(sod_client, "is_configured", lambda: True)
    monkeypatch.setenv("DATATRUST_SHARED_SECRET", SECRET)
    return TestClient(app)


def _signed(path, body, ts=None, secret=SECRET):
    raw = json.dumps(body, separators=(",", ":"))
    ts = ts or str(int(time.time()))
    return raw, {"Content-Type": "application/json", "X-Timestamp": ts, "X-Signature": sod_client.sign(secret, ts, "POST", path, raw)}


def test_api_submit_requires_a_human_identity(quarantine, fake_sod, api):
    p = _proposal(quarantine)
    assert api.post(f"/api/remediation/{p.proposal_id}/submit").status_code == 401
    r = api.post(f"/api/remediation/{p.proposal_id}/submit", headers={"X-User": STEWARD})
    assert r.status_code == 200 and r.json()["status"] == "PENDING_APPROVAL" and r.json()["sod_ticket_code"]


def test_api_internal_approve_returns_409_for_sod_proposal(quarantine, fake_sod, api):
    p = _proposal(quarantine)
    api.post(f"/api/remediation/{p.proposal_id}/submit", headers={"X-User": STEWARD})
    h = {"X-User": "giang.hoang", "X-User-Role": "ADMIN"}
    assert api.post(f"/api/remediation/{p.proposal_id}/approve", headers=h).status_code == 409
    assert api.post(f"/api/remediation/{p.proposal_id}/reject", json={"reason": "x"}, headers=h).status_code == 409


def test_api_webhook_signature_replay_and_flow(quarantine, fake_sod, api):
    p = _proposal(quarantine)
    api.post(f"/api/remediation/{p.proposal_id}/submit", headers={"X-User": STEWARD})
    path = "/api/integrations/sod/events"
    event = {"event_id": f"SOD-TEST-EVT-{uuid.uuid4().hex[:6]}", "ticket_code": p.sod_ticket_code, "status": "APPROVED",
             "proposal_hash": p.sod_form_hash, "executor_username": EXECUTOR,
             "approvers": [{"role": "SO", "action": "A", "actor": "dung.pham", "outcome": "APPROVE"},
                           {"role": "REQ", "action": "P", "actor": STEWARD, "outcome": "SUBMIT"}]}
    # sai chữ ký, quá hạn → 401, không đổi gì
    raw, h = _signed(path, event, secret="x" * 40)
    assert api.post(path, content=raw, headers=h).status_code == 401
    raw, h = _signed(path, event, ts=str(int(time.time()) - 900))
    assert api.post(path, content=raw, headers=h).status_code == 401
    assert p.status == ProposalStatus.PENDING_APPROVAL
    # đúng chữ ký → APPROVED; gửi lại cùng event_id → đã xử lý
    raw, h = _signed(path, event)
    r1 = api.post(path, content=raw, headers=h)
    assert r1.status_code == 200 and r1.json()["changed"] is True and p.status == ProposalStatus.APPROVED
    assert p.sod_executor == EXECUTOR and p.sod_approvers == ["dung.pham"]
    raw, h = _signed(path, event)
    r2 = api.post(path, content=raw, headers=h)
    assert r2.status_code == 200 and r2.json()["already_processed"] is True
    # phiếu lạ → 404 để SoD giữ sự kiện và gửi lại sau
    raw, h = _signed(path, {**event, "event_id": f"SOD-TEST-EVT-{uuid.uuid4().hex[:6]}", "ticket_code": "SOD-TEST-9999"})
    assert api.post(path, content=raw, headers=h).status_code == 404


def test_sign_and_verify_contract():
    ts = "1760000000"
    sig = sod_client.sign(SECRET, ts, "POST", "/p", '{"a":1}')
    assert sod_client.verify(SECRET, ts, sig, "POST", "/p", '{"a":1}', now=1760000100) is None
    assert sod_client.verify(SECRET, ts, sig, "GET", "/p", '{"a":1}', now=1760000100) == "bad_signature"  # chữ ký không dùng lại cho method khác
    assert sod_client.verify(SECRET, ts, sig, "POST", "/q", '{"a":1}', now=1760000100) == "bad_signature"  # ...cũng không cho đường dẫn khác
    assert sod_client.verify(SECRET, ts, sig, "POST", "/p", '{"a":2}', now=1760000100) == "bad_signature"
    assert sod_client.verify(SECRET, ts, sig, "POST", "/p", '{"a":1}', now=1760009999) == "stale_or_missing_timestamp"
    assert sod_client.verify("short", ts, sig, "POST", "/p", '{"a":1}', now=1760000100) == "integration_not_configured"


# ---------------------------------------------------------------- Không có đường vòng qua SoD khi đã bật tích hợp

def test_when_sod_enabled_internal_approval_is_off_even_without_ticket(quarantine, fake_sod, api):
    """Nút 'Phê duyệt (Admin)' ở DRY_RUN_PASSED (chưa gửi duyệt) không được trở thành đường vòng qua SoD."""
    p = _proposal(quarantine)  # DRY_RUN_PASSED, chưa có phiếu
    h = {"X-User": "giang.hoang", "X-User-Role": "ADMIN"}
    r = api.post(f"/api/remediation/{p.proposal_id}/approve", headers=h)
    assert r.status_code == 409 and "SoD" in r.json()["detail"]
    assert p.status == ProposalStatus.DRY_RUN_PASSED and p.approved_by is None


def test_when_sod_enabled_proposal_without_ticket_cannot_execute(quarantine, fake_sod, api):
    p = _proposal(quarantine)
    p.status = ProposalStatus.APPROVED  # giả lập đề xuất đã được duyệt từ trước khi bật tích hợp
    p.approved_by = "admin"
    r = api.post(f"/api/remediation/{p.proposal_id}/execute", headers={"X-User": "admin", "X-User-Role": "ADMIN"})
    assert r.status_code == 403
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT status FROM quarantine.records WHERE quarantine_id::text = ANY(%s)", (quarantine["q_ids"],))
        assert {x[0] for x in cur.fetchall()} == {"QUARANTINED"}
    conn.close()


def test_executions_endpoint_links_each_run_to_its_sod_ticket(quarantine, fake_sod, api, monkeypatch):
    monkeypatch.setenv("SOD_URL", "http://sod.example")
    p = _approved(quarantine, fake_sod)
    p.sod_ticket_id = "11111111-2222-3333-4444-555555555555"
    remediation_service.execute_remediation_transaction(p.proposal_id, EXECUTOR, "EXECUTOR")
    rows = api.get("/api/remediation/executions?limit=20").json()
    row = next(r for r in rows if r["proposal_id"] == p.proposal_id)
    assert row["sod_ticket_code"] == p.sod_ticket_code and row["sod_form_hash"] == p.sod_form_hash
    assert row["sod_ticket_url"] == "http://sod.example/yeu-cau/11111111-2222-3333-4444-555555555555"
    assert row["executed_by"] == EXECUTOR and len(row["signature"]) == 64
    status = api.get("/api/integrations/sod/status").json()
    assert status == {"configured": True, "url": "http://sod.example"}


def test_event_is_matched_by_proposal_id_and_ticket_code_together(quarantine, fake_sod, api):
    """Mã phiếu chỉ duy nhất trong một CSDL SoD: sự kiện mang mã đề xuất khác thì không được áp vào đề xuất trùng mã phiếu."""
    a = _proposal(quarantine)
    remediation_service.submit_to_sod(a.proposal_id, STEWARD)
    b = _proposal(quarantine)
    remediation_service.submit_to_sod(b.proposal_id, STEWARD)
    b.sod_ticket_code = a.sod_ticket_code  # giả lập trùng mã phiếu (SoD bị khôi phục / dựng lại)
    path = "/api/integrations/sod/events"
    event = {"event_id": f"SOD-TEST-EVT-{uuid.uuid4().hex[:6]}", "ticket_code": a.sod_ticket_code, "status": "DONE",
             "external_ref": a.proposal_id, "proposal_hash": a.sod_form_hash}
    raw, h = _signed(path, event)
    assert api.post(path, content=raw, headers=h).status_code == 200
    assert a.status == ProposalStatus.APPROVED
    assert b.status == ProposalStatus.PENDING_APPROVAL, "đề xuất trùng mã phiếu không được bị đổi"
    # external_ref của đề xuất khác nhưng cùng mã phiếu: không khớp
    event2 = {**event, "event_id": f"SOD-TEST-EVT-{uuid.uuid4().hex[:6]}", "external_ref": "PROP-REM-KHONGCO"}
    raw, h = _signed(path, event2)
    assert api.post(path, content=raw, headers=h).status_code == 404


def test_api_execute_requires_executor_role_and_assigned_person(quarantine, fake_sod, api):
    p = _approved(quarantine, fake_sod)
    path = f"/api/remediation/{p.proposal_id}/execute"
    assert api.post(path, headers={"X-User": EXECUTOR, "X-User-Role": "AUDITOR"}).status_code == 403
    assert api.post(path, headers={"X-User": STEWARD, "X-User-Role": "EXECUTOR"}).status_code == 403
    r = api.post(path, headers={"X-User": EXECUTOR, "X-User-Role": "EXECUTOR"})
    assert r.status_code == 200 and r.json()["status"] == "REMEDIATED"
