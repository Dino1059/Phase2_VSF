# Phương án sửa lỗi XCom cho dataset telemetry (Lane A + Lane B)

## Context
- Pipeline `datatrust_adaptive_pipeline` lỗi ở dataset `synthetic_ev_telemetry_ved_ref` (57.600 dòng); các dataset nhỏ (trips, customers) chạy thành công.
- Lane A và Lane B tính xong, rồi chết khi đẩy kết quả từng bản ghi qua XCom (Airflow lưu XCom vào Postgres):
  - Lane A: `invalid memory alloc request size 1073741824`. Một giá trị vượt giới hạn 1 GB của Postgres; tăng RAM không sửa được.
  - Lane B: `SIGKILL` (hết RAM, worker `memory.peak` khoảng 5,5 GB) lúc tuần tự hoá khối XCom khổng lồ.
- Nguyên nhân phình to: `execute_lane_a_detectors` (`dags/parallel_evaluation_engine.py:380`) gắn **toàn bộ `rule_snapshot`** vào **từng** bản ghi, tức 57.600 bản sao. Router Lane C (`backend/engine/verdict_merger_and_router.py`) không đọc trường này, chỉ đọc `status`, `evidence`, `signals`.
- Mục tiêu: telemetry chạy hết cả 4 bước, **ít thay đổi nhất**, không đổi kết quả của các dataset đang chạy đúng, không phải sửa test có sẵn.

## Nguyên tắc
- **Chỉ sửa một file:** `dags/datatrust_adaptive_pipeline_dag.py`, cộng một file test mới.
- **Không sửa** `execute_lane_a_detectors`, `execute_lane_b_policy`, `execute_lane_c_merge_and_persist` và router. Nội dung dữ liệu Lane C nhận được giữ y hệt bây giờ. Test `tests/test_lane_a_db_config.py:23` (kiểm tra `rule_snapshot` theo bản ghi) vẫn qua.
- Không đổi `docker-compose.yml`. Thư mục `./logs` đã được mount vào mọi container Airflow tại `/opt/airflow/logs`.
- Tương thích ngược: nếu XCom cũ là dữ liệu thường (không phải tham chiếu file), vẫn đọc như cũ.

## Thiết kế: chuyển kết quả qua file, XCom chỉ giữ đường dẫn

Thêm 2 hàm nhỏ vào DAG (viết theo Python 3.7, đúng bản trong container):

1. `_push_lane_payload(ti, key, value, run_id)`
   - Ghi `value` ra `/opt/airflow/logs/xcom_payloads/<run_id>/<key>.json.gz` (gzip mức 1), dùng `json.dump` ghi luồng nên không dựng chuỗi lớn trong RAM. Ghi vào file `.tmp` rồi `os.replace`, để một lần thử lại không đọc phải file dở.
   - **Gộp `rule_snapshot` trùng của Lane A:** nếu `value` là dict theo bản ghi và mọi bản ghi có cùng `rule_snapshot`, thì ghi `{"__shared_rule_snapshot__": snap, "records": {pk: bản ghi không có rule_snapshot}}` (bỏ trường bằng bản sao nông, không động vào dữ liệu gốc).
   - `ti.xcom_push(key, {"__xcom_file__": path, "count": n})`, chỉ vài chục byte.
2. `_pull_lane_payload(ti, task_ids, key, default)`
   - Gọi `ti.xcom_pull(...)`. Nếu giá trị có `__xcom_file__` thì mở file gzip và `json.load`. Nếu có `__shared_rule_snapshot__` thì gắn lại **cùng một đối tượng list** vào từng bản ghi, theo tham chiếu, không tạo bản sao, nên Lane C nhận cấu trúc y như hiện tại.
   - Nếu không có `__xcom_file__` thì trả nguyên giá trị (tương thích ngược). Nếu `None` thì trả `default`.

Thay 5 chỗ trong `dags/datatrust_adaptive_pipeline_dag.py`:

| Dòng (hiện tại) | Đang là | Đổi thành |
|---|---|---|
| 546 | `xcom_push(key='lane_a_results', ...)` | `_push_lane_payload(ti, 'lane_a_results', lane_a_results, run_id)` |
| 567 | `xcom_push(key='lane_b_results', ...)` | `_push_lane_payload(ti, 'lane_b_results', lane_b_results, run_id)` |
| 583 | `xcom_pull(... 'lane_a_results') or {}` | `_pull_lane_payload(..., default={})` |
| 584 | `xcom_pull(... 'lane_b_results') or []` | `_pull_lane_payload(..., default=[])` |
| 661 | `xcom_pull(... 'lane_b_results')` (bước 4) | `_pull_lane_payload(..., default=[])` |

`run_id` lấy bằng `get_canonical_run_id(context)` (hàm có sẵn trong DAG, Lane C và bước 4 đã dùng).

Dọn file: cuối bước 4, khi thành công, xoá best-effort thư mục `xcom_payloads/<run_id>`. Nếu thất bại thì giữ lại để thử lại hoặc gỡ lỗi.

Giữ `AIRFLOW__CELERY__WORKER_CONCURRENCY: "1"` trong `docker-compose.yml` (đã thêm trước đó) để Lane A và B không chiếm RAM cùng lúc.

## Các bước thực hiện
0. **Đo mốc (trước khi sửa):**
   - Chạy pipeline cho `ride_hailing_xanh_sm_trips` và `dim_customers` trên **bộ dữ liệu mới**, ghi lại các số scanned/silver/quarantine/warning làm mốc so sánh.
   - Đo kích thước kết quả Lane A và Lane B của telemetry: chạy `execute_lane_a_detectors` và `execute_lane_b_policy` trong container `airflow-worker` (chỉ đọc DB), ghi `json.dump` ra file tạm, đo kích thước file (trước và sau khi gộp `rule_snapshot`) và RAM đỉnh. Nếu payload Lane B sau gzip vẫn quá lớn để Lane C nạp an toàn (RAM đỉnh dự kiến vượt khoảng 6 GB), dừng lại báo bạn trước khi làm tiếp.
1. Thêm 2 hàm và đổi 5 chỗ như bảng trên. Thêm dọn file ở cuối bước 4.
2. Thêm `tests/test_xcom_file_handoff.py`: dùng `ti` giả và thư mục tạm, kiểm tra
   - Lane A khứ hồi giữ nguyên dữ liệu (kể cả `rule_snapshot` theo bản ghi);
   - Lane B (list) khứ hồi;
   - giá trị XCom cũ (không phải tham chiếu file) vẫn đọc được.
3. Không cần khởi động lại container: thư mục `dags/` được mount, Airflow tự nạp lại DAG.
4. Lưu phương án này vào repo tại `docs/PLAN_FIX_XCOM_TELEMETRY.md` theo yêu cầu "ghi vào file md".

## Kiểm tra
- `.venv/bin/python -m pytest tests/test_xcom_file_handoff.py tests/test_lane_a_db_config.py tests/test_task3_parallel_and_routing.py tests/test_task4_audit_evidence.py -q` đều qua.
- Chạy lại trips và customers: số scanned/silver/quarantine/warning **khớp mốc** ở bước 0.
- Chạy telemetry:
  - `orchestration.pipeline_runs.status = SUCCESS` và cả 4 bước `success`;
  - `memory.events` của worker có `oom_kill` không tăng;
  - `memory.peak` ghi lại để báo cáo.
- XCom nhỏ lại: `select key, length(value) from xcom where run_id='app_<run_id>'` cho thấy `lane_a_results` và `lane_b_results` chỉ vài trăm byte.
- Có bản ghi `audit.evidence` cho lần chạy telemetry, giao diện (http://localhost:5173) hiển thị kết quả, `/api/pipeline/latest-completed?dataset_id=synthetic_ev_telemetry_ved_ref` trả về 200.

## Rủi ro và giới hạn
- Lane C vẫn nạp toàn bộ kết quả vào RAM như thiết kế hiện tại. Phương án này bỏ được phần phình do XCom và do `rule_snapshot` trùng, nhưng không viết lại Lane C. Bước 0 sẽ cho biết có đủ RAM không trước khi sửa.
- Thay đổi chưa commit, có thể xung đột nhỏ khi `git pull` bản mới của tác giả ở đúng các dòng này.
- Phương án này chỉ sửa **hạ tầng**. Lane B vẫn chưa có luật cho `fatigue_score`, đồng ý/xoá, `legal_basis` (thư mục `legal-packs` chưa có code đọc), nên kết quả Lane B của telemetry chưa so được với `lane_b_manifest.json`. Đó là việc tách riêng.
