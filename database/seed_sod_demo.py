"""
DataTrust OS x SoD Flow: Phase 2 Demo Seed Script
Seeds 14 Demo Persona Identities in PostgreSQL schema `sod` to support multi-party
workflow simulation without triggering No Self-Approval DB conflicts.
Separate from production migration; safe to run idempotently in development/staging.
"""

import os
import sys
import json
import hashlib
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from backend.sod.catalog import DEFAULT_MATRIX

DATABASE_DIR = Path(__file__).resolve().parent
load_dotenv(DATABASE_DIR.parent / ".env")

DEMO_PERSONAS = [
    # NHOM 1: BOTH (4)
    {"username": "demo_admin", "name": "Nguyễn Quốc Bảo", "email": "bao.nq@gsm.vn", "role": "ADMIN", "dept": "GSM Global Tech"},
    {"username": "demo_auditor", "name": "Trần Minh Hoàng", "email": "hoang.tran@audit-ipo.com", "role": "AUDITOR", "dept": "Big 4 Audit Consortium"},
    {"username": "demo_dpo", "name": "Lê Chi", "email": "chi.le@company.vn", "role": "DPO", "dept": "Phòng Pháp chế & Tuân thủ"},
    {"username": "demo_so", "name": "Hồ Sơn", "email": "son.ho@company.vn", "role": "SO", "dept": "Khối Công nghệ Thông tin"},
    # NHOM 2: SOD ONLY (7)
    {"username": "demo_req", "name": "Nguyễn An", "email": "an.nguyen@company.vn", "role": "REQ", "dept": "Khối Kinh doanh & Vận hành"},
    {"username": "demo_lm", "name": "Trần Bình", "email": "binh.tran@company.vn", "role": "LM", "dept": "Khối Kinh doanh & Vận hành"},
    {"username": "demo_iam", "name": "Vũ Hà", "email": "ha.vu@company.vn", "role": "IAM", "dept": "Trung tâm Hạ tầng & Định danh"},
    {"username": "demo_dev", "name": "Đỗ Khoa", "email": "khoa.do@company.vn", "role": "DEV", "dept": "Phòng Phát triển Ứng dụng"},
    {"username": "demo_rel", "name": "Bùi Lan", "email": "lan.bui@company.vn", "role": "REL", "dept": "Ban Quản lý Chất lượng & Release"},
    {"username": "demo_ops", "name": "Ngô Minh", "email": "minh.ngo@company.vn", "role": "OPS", "dept": "Khối Vận hành Hạ tầng Cloud"},
    {"username": "demo_ciso", "name": "Hoàng Giang", "email": "giang.hoang@company.vn", "role": "CISO", "dept": "Khối An toàn Thông tin"},
    # NHOM 3: DATATRUST ONLY (3)
    {"username": "demo_steward", "name": "Lê Nam", "email": "steward.le@company.vn", "role": "DATA_STEWARD", "dept": "Khối Quản trị Dữ liệu Doanh nghiệp"},
    {"username": "demo_analyst", "name": "Vũ Mai", "email": "analyst.vu@company.vn", "role": "ANALYST", "dept": "Trung tâm Phân tích Dữ liệu"},
    {"username": "demo_viewer", "name": "Trần Đức", "email": "viewer.tran@company.vn", "role": "VIEWER", "dept": "Ban Giám đốc"},
]


def get_db_connection():
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return psycopg2.connect(db_url)
    hosts = ["postgres", "localhost", "127.0.0.1"]
    for h in hosts:
        try:
            return psycopg2.connect(host=h, port=5432, user="airflow", password="airflow", dbname="airflow", connect_timeout=3)
        except Exception:
            continue
    raise ConnectionError("Không thể kết nối đến PostgreSQL.")


def seed_demo_data():
    conn = get_db_connection()
    conn.autocommit = False
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            print(">>> [1/3] Nạp 14 Persona Identities cho Demo Mode trong schema sod...")
            user_ids = {}
            for p in DEMO_PERSONAS:
                cur.execute("""
                    INSERT INTO sod.users (username, full_name, email, dept, is_active, session_version)
                    VALUES (%s, %s, %s, %s, TRUE, 1)
                    ON CONFLICT (username) DO UPDATE SET
                        full_name = EXCLUDED.full_name,
                        email = EXCLUDED.email,
                        dept = EXCLUDED.dept
                    RETURNING id;
                """, (p["username"], p["name"], p["email"], p["dept"]))
                row = cur.fetchone()
                user_ids[p["role"]] = row["id"]

                # Gán vai trò tương ứng trong sod.user_roles
                cur.execute("""
                    INSERT INTO sod.user_roles (user_id, role_code, valid_from)
                    VALUES (%s, %s, now())
                    ON CONFLICT (user_id, role_code) DO NOTHING;
                """, (row["id"], p["role"]))

            # Thêm tài khoản demo duy nhất "demo_user" kiêm nhiều vai trò phục vụ chuyển đổi nhanh
            cur.execute("""
                INSERT INTO sod.users (username, full_name, email, dept, is_active, session_version)
                VALUES ('demo_user', 'Tài khoản Trải nghiệm Tập trung (Demo User)', 'demo.user@company.vn', 'Data Platform & Security', TRUE, 1)
                ON CONFLICT (username) DO NOTHING
                RETURNING id;
            """)
            demo_user_row = cur.fetchone()
            if demo_user_row:
                demo_uid = demo_user_row["id"]
                for p in DEMO_PERSONAS:
                    cur.execute("""
                        INSERT INTO sod.user_roles (user_id, role_code, valid_from)
                        VALUES (%s, %s, now())
                        ON CONFLICT (user_id, role_code) DO NOTHING;
                    """, (demo_uid, p["role"]))

            print(">>> [2/3] Cập nhật / Đồng bộ phiên bản ma trận RACIX ACTIVE chuẩn...")
            cur.execute("""
                INSERT INTO sod.config_versions (seq, config, status, reason, activated_at)
                VALUES (
                    1,
                    jsonb_build_object('version', '1.0.0-standard', 'matrix', %s::jsonb),
                    'ACTIVE',
                    'Cấu hình ma trận RACIX chuẩn ISO 27001 / SoD Governance',
                    now()
                )
                ON CONFLICT (seq) DO UPDATE SET
                    config = EXCLUDED.config,
                    status = 'ACTIVE'
                RETURNING id, seq;
            """, (json.dumps(DEFAULT_MATRIX),))
            active_cfg = cur.fetchone()
            config_id = active_cfg["id"]
            config_seq = active_cfg["seq"]

            print(">>> [3/3] Nạp các phiếu yêu cầu mẫu khởi tạo ban đầu...")
            sample_form = {
                "loaiPhieu": "new",
                "khan": "normal",
                "hoTen": "Nguyễn An",
                "email": "an.nguyen@company.vn",
                "phongBan": "Khối Kinh doanh & Vận hành",
                "chucDanh": "Business Analyst",
                "capBac": "T3",
                "thiTruong": "vn",
                "mucDich": "Khai thác dữ liệu hành trình chuyến xe phục vụ tính KPI dịch vụ",
                "dlcn": "basic",
                "lyDo": "Cần quyền đọc bảng trips và thông tin liên hệ khách hàng",
                "camKet": True,
                "rows": [
                    {"heThong": "Data Warehouse (DWH)", "taiNguyen": "silver.trips_clean", "tang": "2", "mucQuyen": "RO", "thoiHan": "2026-12-31"}
                ]
            }
            form_json_str = json.dumps(sample_form, sort_keys=True)
            form_hash = hashlib.sha256(form_json_str.encode("utf-8")).hexdigest()

            # Tạo Ticket TK-2026-001 (Đang mở - Chờ Line Manager duyệt)
            req_id = user_ids["REQ"]
            lm_id = user_ids["LM"]
            dpo_id = user_ids["DPO"]
            so_id = user_ids["SO"]
            iam_id = user_ids["IAM"]

            cur.execute("""
                INSERT INTO sod.tickets (
                    code, seq, kind, status, priority, level, pii,
                    config_version_id, config_seq, form, form_hash,
                    acts, phases, requester_id, current_step_idx, total_steps
                ) VALUES (
                    'TK-2026-001', 1, 'access', 'OPEN', 'normal', 2, TRUE,
                    %s, %s, %s, %s,
                    ARRAY[0, 1, 2, 4]::int[],
                    '[{"act": "req", "name": "Đề nghị cấp quyền"}, {"act": "lm", "name": "Quản lý trực tiếp duyệt"}, {"act": "dpo", "name": "DPO duyệt PII"}, {"act": "iam", "name": "IAM thực thi"}]'::jsonb,
                    %s, 1, 4
                ) ON CONFLICT (code) DO NOTHING
                RETURNING id;
            """, (config_id, config_seq, json.dumps(sample_form), form_hash, req_id))
            
            tkt_row = cur.fetchone()
            if tkt_row:
                tkt_id = tkt_row["id"]
                # Bước 0: Khởi tạo
                cur.execute("""
                    INSERT INTO sod.ticket_steps (ticket_id, idx, phase, key, role_code, action, assignee_id, status)
                    VALUES (%s, 0, 0, 'init', 'REQ', 'P', %s, 'CURRENT')
                    RETURNING id;
                """, (tkt_id, req_id))
                s0_id = cur.fetchone()["id"]
                cur.execute("""
                    INSERT INTO sod.step_decisions (step_id, actor_id, outcome, comment, form_hash, rev)
                    VALUES (%s, %s, 'SUBMIT', 'Nộp phiếu đề nghị cấp quyền mới', %s, 1);
                """, (s0_id, req_id, form_hash))
                cur.execute("UPDATE sod.ticket_steps SET status = 'DONE' WHERE id = %s;", (s0_id,))

                # Bước 1: Line Manager (CURRENT)
                cur.execute("""
                    INSERT INTO sod.ticket_steps (ticket_id, idx, phase, key, role_code, action, assignee_id, status, sla_hours, started_at, due_at)
                    VALUES (%s, 1, 1, 'lm_approve', 'LM', 'A', %s, 'CURRENT', 24, now(), now() + interval '24 hours')
                    RETURNING id;
                """, (tkt_id, lm_id))
                s1_id = cur.fetchone()["id"]
                cur.execute("UPDATE sod.tickets SET active_step_id = %s WHERE id = %s", (s1_id, tkt_id))

                # Bước 2: DPO (WAITING)
                cur.execute("""
                    INSERT INTO sod.ticket_steps (ticket_id, idx, phase, key, role_code, action, assignee_id, status, sla_hours)
                    VALUES (%s, 2, 2, 'dpo_review', 'DPO', 'R', %s, 'WAITING', 48);
                """, (tkt_id, dpo_id))

                # Bước 3: IAM (WAITING)
                cur.execute("""
                    INSERT INTO sod.ticket_steps (ticket_id, idx, phase, key, role_code, action, assignee_id, status, sla_hours)
                    VALUES (%s, 3, 3, 'iam_exec', 'IAM', 'P', %s, 'WAITING', 24);
                """, (tkt_id, iam_id))

        conn.commit()
        print(">>> Nạp dữ liệu seed demo SoD thành công 100%!")
    except Exception as e:
        conn.rollback()
        print(f"[!] Lỗi khi nạp seed demo SoD: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    seed_demo_data()
