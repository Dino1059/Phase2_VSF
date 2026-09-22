DataTrust OS - Demo Audit Dataset
=================================
Business source: ride_hailing_xanh_sm_trips.csv (10382 trips)

Các file CSV trong thư mục mô phỏng dữ liệu phục vụ kiểm soát và audit.
control_results.csv được tạo với tỷ lệ mục tiêu 70% PASS / 20% FAIL / 10% NOT_EVALUATED.
Một số vi phạm được cố tình cài vào dữ liệu để phục vụ demo: self-approval, leaver còn quyền,
export nhạy cảm thiếu approval/masking, deploy PROD thiếu RFC, SoD CI/CD, pipeline failure.

Liên kết chính:
users -> privileges/access_requests/approvals/hr_events/db_audit_events
db_audit_events -> export_events -> evidence -> control_results -> findings
change_requests -> cicd_events -> evidence -> control_results -> findings
pipeline_runs -> evidence -> control_results -> findings
trip_id trong audit/export liên kết với ride_hailing_xanh_sm_trips.csv.
