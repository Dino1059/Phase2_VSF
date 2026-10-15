"""
Chạy thử đầu-cuối luồng duyệt DataTrust <-> SoD Flow (PLAN_NOI_SOD_DATATRUST.md, bước 5 và 8).
Chạy trên môi trường CÔ LẬP: SoD (cổng 3001, DB sod_test) và DataTrust (cổng 8001), không đụng phiếu thật.

    python scripts/e2e_sod_datatrust.py happy|reject|submit-sod-down|resubmit <id>|submit <tên>|check <id> <trạng thái> [giây]|replay
Mỗi lệnh tự dựng bản ghi cách ly tạm và dọn sạch khi xong (trừ lệnh `submit`, dọn bằng `cleanup`).
"""
import os, sys, json, time, uuid, hmac, hashlib, subprocess, urllib.request, urllib.error
from dotenv import dotenv_values

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
ENV = dotenv_values(".env")
SECRET = ENV["DATATRUST_SHARED_SECRET"]
DT = os.getenv("E2E_DT_URL", "http://localhost:8001")
SOD_WEB = os.getenv("E2E_SOD_WEB", "/Users/vuthuhuyen/SoD /web")
SOD_BASE = ENV.get("E2E_SOD_DB_BASE")  # tuỳ chọn
STEWARD = "an.nguyen"

from database.profiler_engine import get_db_connection  # noqa: E402
from backend.ai.services.remediation_service import compute_hash  # noqa: E402

results = []
def check(name, cond, extra=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra else ""))

def http(method, path, body=None, headers=None, base=DT):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        raw = e.read()
        try: return e.code, json.loads(raw or b"{}")
        except Exception: return e.code, {"raw": raw.decode(errors="replace")}

ADMIN = lambda user: {"X-User": user, "X-User-Role": "ADMIN"}

def sod_db_env():
    """DATABASE_URL / APP_DATABASE_URL của DB sod_test, suy ra từ .env của SoD."""
    vals = dotenv_values(os.path.join(SOD_WEB, ".env"))
    owner = vals["DATABASE_URL"].split("/sod?")[0]; app = vals["APP_DATABASE_URL"].split("/sod?")[0]
    return {**os.environ, "DATABASE_URL": f"{owner}/sod_test?schema=public", "APP_DATABASE_URL": f"{app}/sod_test?schema=public",
            "DATATRUST_URL": DT, "DATATRUST_SHARED_SECRET": SECRET}

def sod_psql(sql):
    url = sod_db_env()["DATABASE_URL"].split("?")[0]
    return subprocess.run(["psql", url, "-Atc", sql], capture_output=True, text=True).stdout.strip()

def sod_decide(code, mode="approve"):
    out = subprocess.run(["npx", "tsx", "--conditions=react-server", "tests/e2e/datatrust-approve.ts", code, mode],
                         cwd=SOD_WEB, env=sod_db_env(), capture_output=True, text=True, timeout=180)
    print(out.stdout.strip()); 
    if out.returncode: print(out.stderr[-600:])
    return out.stdout

def seed_quarantine(n=2):
    q = [str(uuid.uuid4()) for _ in range(n)]; run = f"RUN-E2E-{uuid.uuid4().hex[:6]}"
    c = get_db_connection()
    with c.cursor() as cur:
        for i, qid in enumerate(q):
            raw = {"trip_id": f"E2E{i}", "customer_phone": f"09123456{i}7", "fare_amount": 50000.0}
            cur.execute("""INSERT INTO quarantine.records (quarantine_id,run_id,dataset_id,source_table,source_row_pk,failure_lane,violation_column,violation_rule_id,violation_reason,violation_severity,raw_record_json,lineage_hash,status,quarantined_at)
                VALUES (%s,%s,'trips','bronze.trips',%s,'LANE_B','customer_phone','R','Số điện thoại dạng rõ','HIGH',%s,%s,'QUARANTINED',CURRENT_TIMESTAMP)""",
                (qid, run, f"PK{i}", json.dumps(raw), compute_hash(raw)))
    c.commit(); c.close()
    return run, q

def cleanup(q, ids=()):
    c = get_db_connection()
    with c.cursor() as cur:
        cur.execute("delete from quarantine.records where quarantine_id::text = any(%s)", (q,))
        cur.execute("delete from staging.remediated_records where quarantine_id::text = any(%s)", (q,))
        for pid in ids: cur.execute("delete from governance.remediation_proposals where proposal_id=%s", (pid,))
    c.commit(); c.close()

def new_proposal(run, q, who="AI_AGENT"):
    s, p = http("POST", "/api/remediation/propose", dict(finding_id=f"FINDING-E2E-{uuid.uuid4().hex[:6]}", run_id=run, dataset_id="trips",
        column="customer_phone", quarantine_ids=q, operation_id="MASK_PHONE", params={"prefix_len": 3, "suffix_len": 2, "mask_char": "*"},
        reason="Che số điện thoại dạng rõ (chạy thử đầu-cuối)", proposer=who, confidence="SUPPORTED"))
    assert s == 200, p
    pid = p["proposal_id"]
    s, d = http("POST", f"/api/remediation/{pid}/dry-run"); assert s == 200 and d["status"] == "DRY_RUN_PASSED", d
    return pid

def get(pid): return http("GET", f"/api/remediation/proposals/{pid}")[1]

def wait_status(pid, want, secs=15):
    t0 = time.time()
    while time.time() - t0 < secs:
        st = get(pid)["status"]
        if st == want: return st, round(time.time() - t0, 1)
        time.sleep(0.5)
    return get(pid)["status"], round(time.time() - t0, 1)

def quarantine_status(q):
    c = get_db_connection()
    with c.cursor() as cur:
        cur.execute("select status, count(*) from quarantine.records where quarantine_id::text = any(%s) group by 1", (q,))
        r = dict(cur.fetchall())
    c.close(); return r

def happy():
    run, q = seed_quarantine(); pids = []
    try:
        pid = new_proposal(run, q); pids.append(pid)
        check("K8.2 đề xuất của LLM sau dry-run", get(pid)["status"] == "DRY_RUN_PASSED")
        s, _ = http("POST", f"/api/remediation/{pid}/submit")
        check("K3.x LLM/ẩn danh không gửi duyệt được (401)", s == 401, s)
        s, p = http("POST", f"/api/remediation/{pid}/submit", headers={"X-User": STEWARD})
        code = p.get("sod_ticket_code")
        check("K3.1 gửi duyệt → PENDING_APPROVAL có mã phiếu", s == 200 and p.get("status") == "PENDING_APPROVAL" and bool(code), f"{s} {code}")
        check("K3.2 phiếu bên SoD có requester đúng", sod_psql(f"select u.username from tickets t join users u on u.id=t.requester_id where code='{code}'") == STEWARD)
        print("   chuỗi:", sod_psql(f"select string_agg(role_code||':'||action, ' → ' order by idx) from ticket_steps s join tickets t on t.id=s.ticket_id where t.code='{code}'"))
        s, _ = http("POST", f"/api/remediation/{pid}/approve", headers=ADMIN("giang.hoang"))
        check("K5.1 approve nội bộ cho đề xuất có phiếu → 409", s == 409, s)
        s, _ = http("POST", f"/api/remediation/{pid}/reject", {"reason": "x"}, headers=ADMIN("giang.hoang"))
        check("K5.1b reject nội bộ → 409", s == 409, s)
        s, _ = http("POST", f"/api/remediation/{pid}/execute", headers=ADMIN(STEWARD))
        check("K5.2 thực thi khi phiếu chưa DONE → 403", s == 403, s)
        check("K5.2b dữ liệu chưa đổi", quarantine_status(q) == {"QUARANTINED": 2}, quarantine_status(q))
        sod_decide(code, "approve")
        st, secs = wait_status(pid, "APPROVED", 15)
        check("K4.1 duyệt xong bên SoD → APPROVED trong ≤ 10 giây", st == "APPROVED" and secs <= 10, f"{st} {secs}s")
        s, _ = http("POST", f"/api/remediation/{pid}/execute", headers=ADMIN("nguoi.khac"))
        check("K5.3 thực thi bằng người khác Requestor → 403", s == 403, s)
        s, _ = http("POST", f"/api/remediation/{pid}/execute", headers=ADMIN("giang.hoang"))
        check("K5.8 người duyệt (không phải Requestor) cũng không thực thi được → 403", s == 403, s)
        s, r = http("POST", f"/api/remediation/{pid}/execute", headers=ADMIN(STEWARD))
        check("K5.5 Requestor thực thi → REMEDIATED", s == 200 and r.get("status") == "REMEDIATED", f"{s} {r.get('status') or r}")
        check("K8.4 quarantine đổi đúng số dòng", quarantine_status(q) == {"REMEDIATED": 2}, quarantine_status(q))
        time.sleep(1)
        n = sod_psql(f"select count(*) from audit_log where action='ticket.executed.external' and target_id=(select id::text from tickets where code='{code}')")
        check("K5.6 SoD ghi nhận 'đã thực thi' trong nhật ký", n == "1", n)
        s, r = http("POST", f"/api/remediation/{pid}/execute", headers=ADMIN(STEWARD))
        check("K5.7 thực thi lần hai không chạy lại", s in (400, 403, 409) and quarantine_status(q) == {"REMEDIATED": 2}, s)
        c = get_db_connection()
        with c.cursor() as cur:
            cur.execute("select new_state->'audit_payload'->>'sod_ticket_code', new_state->'audit_payload'->>'sod_form_hash' from audit.system_audit_trail where entity_id=%s order by timestamp desc limit 1", (pid,))
            row = cur.fetchone()
        c.close()
        check("K6.2 bản ghi kiểm toán (đã ký) có mã phiếu và hash", bool(row) and row[0] == code and row[1] == get(pid)["sod_form_hash"], row)
        tid = sod_psql(f"select id from tickets where code='{code}'")
        s, rows = http("GET", "/api/remediation/executions?limit=50")
        row = next((r for r in rows if r["proposal_id"] == pid), {}) if s == 200 else {}
        check("K6.3 API executions: có mã phiếu, hash và đường dẫn tới đúng phiếu bên SoD",
              row.get("sod_ticket_code") == code and row.get("sod_form_hash") == get(pid)["sod_form_hash"]
              and (row.get("sod_ticket_url") or "").endswith(f"/yeu-cau/{tid}"), row.get("sod_ticket_url"))
        print("CODE", code, "PID", pid)
    finally:
        cleanup(q, pids)

def reject():
    run, q = seed_quarantine(); pids = []
    try:
        pid = new_proposal(run, q); pids.append(pid)
        s, p = http("POST", f"/api/remediation/{pid}/submit", headers={"X-User": STEWARD}); code = p.get("sod_ticket_code")
        sod_decide(code, "reject")
        st, secs = wait_status(pid, "REJECTED", 15)
        check("K4.2 từ chối bên SoD → REJECTED", st == "REJECTED", f"{st} {secs}s")
        s, _ = http("POST", f"/api/remediation/{pid}/execute", headers=ADMIN(STEWARD))
        check("K8.6 phiếu bị từ chối: không thực thi được, dữ liệu không đổi", s in (400, 403) and quarantine_status(q) == {"QUARANTINED": 2}, s)
        print("outbox:", sod_psql(f"select status, attempts from integration_outbox where event_id='{code}:REJECTED'"))
    finally:
        cleanup(q, pids)

STATE = os.path.join(os.getenv("E2E_STATE_DIR", "/tmp"), "e2e_sod_state.json")

def _save(d):
    cur = json.load(open(STATE)) if os.path.exists(STATE) else {}
    cur.update(d); json.dump(cur, open(STATE, "w"))

def submit_only(tag="a"):
    """Tạo đề xuất + gửi duyệt, giữ lại để các lệnh sau kiểm tra tiếp. Dọn bằng `cleanup_all`."""
    run, q = seed_quarantine(); pid = new_proposal(run, q)
    s, p = http("POST", f"/api/remediation/{pid}/submit", headers={"X-User": STEWARD})
    print("submit:", s, p.get("status") or p, p.get("sod_ticket_code"))
    _save({tag: {"pid": pid, "q": q, "code": p.get("sod_ticket_code")}})
    return pid, p

def sod_down_submit(tag="a"):
    pid, p = submit_only(tag)
    check("K3.3 SoD tắt: đề xuất ở PENDING_SUBMIT, không phải APPROVED", p.get("status") == "PENDING_SUBMIT" and not p.get("sod_ticket_code"), p.get("status"))

def resubmit(tag="a"):
    pid = json.load(open(STATE))[tag]["pid"]
    s, p = http("POST", f"/api/remediation/{pid}/resubmit", headers={"X-User": STEWARD})
    check("K3.4 bật lại SoD, gửi lại → PENDING_APPROVAL có mã phiếu", s == 200 and p.get("status") == "PENDING_APPROVAL" and bool(p.get("sod_ticket_code")), f"{s} {p.get('status')} {p.get('sod_ticket_code')}")
    d = json.load(open(STATE)); d[tag]["code"] = p.get("sod_ticket_code"); json.dump(d, open(STATE, "w"))
    s2, _ = http("POST", f"/api/remediation/{pid}/resubmit", headers={"X-User": "nguoi.khac"})
    check("gửi lại bởi người khác bị chặn", s2 in (403, 409), s2)

def approve(tag="a"):
    code = json.load(open(STATE))[tag]["code"]; sod_decide(code, "approve")
    print("outbox:", sod_psql(f"select status||' lần '||attempts||' '||coalesce(last_error,'') from integration_outbox where event_id='{code}:DONE'"))

def wait(tag="a", want="APPROVED", secs="150"):
    pid = json.load(open(STATE))[tag]["pid"]; code = json.load(open(STATE))[tag]["code"]
    st, took = wait_status(pid, want, int(secs))
    ob = sod_psql(f"select status||' lần '||attempts from integration_outbox where event_id='{code}:DONE'")
    check(f"K4.4 sau khi DataTrust bật lại: đề xuất thành {want}", st == want, f"{st} sau {took}s; outbox {ob}")
    return ob

def lost(tag="a"):
    """Mất webhook: xoá sự kiện khỏi outbox rồi đối soát."""
    d = json.load(open(STATE))[tag]; pid, code = d["pid"], d["code"]
    print("xoá outbox:", sod_psql(f"delete from integration_outbox where event_id='{code}:DONE' returning event_id") or "(không có, đã gửi)")
    check("trước đối soát đề xuất vẫn chờ", get(pid)["status"] == "PENDING_APPROVAL", get(pid)["status"])
    s, r = http("POST", "/api/integrations/sod/reconcile", headers=ADMIN("admin"))
    check("K4.7 đối soát với SoD cập nhật đúng trạng thái", s == 200 and get(pid)["status"] == "APPROVED", f"{s} {r} {get(pid)['status']}")

def replay(tag="a"):
    """K4.5 / K4.6: phát lại cùng sự kiện, sai chữ ký, quá hạn."""
    code = json.load(open(STATE))[tag]["code"]
    payload = json.loads(sod_psql(f"select payload::text from integration_outbox where event_id='{code}:DONE'") or "{}")
    if not payload:
        print("không có sự kiện trong outbox để phát lại"); return
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False); path = "/api/integrations/sod/events"
    def post(ts=None, sig=None, b=body):
        ts = ts or str(int(time.time()))
        sig = sig or hmac.new(SECRET.encode(), f"{ts}\nPOST\n{path}\n{b}".encode(), hashlib.sha256).hexdigest()
        req = urllib.request.Request(DT + path, data=b.encode(), method="POST", headers={"Content-Type": "application/json", "X-Timestamp": ts, "X-Signature": sig})
        try:
            with urllib.request.urlopen(req, timeout=30) as r: return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e: return e.code, json.loads(e.read() or b"{}")
    s1, r1 = post(); s2, r2 = post()
    check("K4.5 cùng event_id gửi hai lần → lần hai 'đã xử lý'", s2 == 200 and r2.get("already_processed") is True, f"{s1} {r1} | {s2} {r2}")
    s, r = post(sig="0" * 64); check("K4.6 webhook sai chữ ký → 401", s == 401, f"{s} {r}")
    s, r = post(ts=str(int(time.time()) - 900)); check("webhook quá 5 phút → 401", s == 401, f"{s} {r}")
    ts = str(int(time.time())); sig_original = hmac.new(SECRET.encode(), f"{ts}\nPOST\n{path}\n{body}".encode(), hashlib.sha256).hexdigest()
    s, r = post(ts=ts, sig=sig_original, b=body.replace("DONE", "REJECTED")); check("nội dung bị sửa sau khi ký → 401", s == 401, f"{s} {r}")

def restart_check(tag="a"):
    d = json.load(open(STATE))[tag]; pid = d["pid"]
    p = get(pid); check("K1.3/T12 đề xuất còn nguyên sau khi DataTrust khởi động lại", p.get("proposal_id") == pid and p.get("sod_ticket_code") == d["code"], p.get("status"))

def cleanup_all():
    if os.path.exists(STATE):
        for v in json.load(open(STATE)).values():
            cleanup(v.get("q", []), [v.get("pid")] if v.get("pid") else [])
        os.remove(STATE)
    c = get_db_connection()
    with c.cursor() as cur:
        cur.execute("delete from quarantine.records where run_id like 'RUN-E2E-%'")
        cur.execute("delete from governance.remediation_proposals where payload->>'finding_id' like 'FINDING-E2E-%'")
    c.commit(); c.close(); print("đã dọn")

COMMANDS = ("happy", "reject", "sod_down_submit", "resubmit", "approve", "wait", "lost", "replay", "restart_check", "cleanup_all", "submit_only")

if __name__ == "__main__":
    cmd = (sys.argv[1] if len(sys.argv) > 1 else "happy").replace("-", "_")
    if cmd not in COMMANDS: sys.exit(f"Lệnh không hợp lệ: {cmd}. Có: {', '.join(COMMANDS)}")
    globals()[cmd](*sys.argv[2:])
    fails = [n for n, ok in results if not ok]
    if results: print(f"\n{len(results) - len(fails)}/{len(results)} đạt" + (f"; KHÔNG đạt: {fails}" if fails else ""))
    sys.exit(1 if fails else 0)
