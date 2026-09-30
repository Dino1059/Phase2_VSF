# Catalog luật theo vùng (pack) — CSV

Ma trận tuân thủ để **điền** vào pack Lane B. File CSV hiện **chỉ có header** (trống dữ liệu), trừ khi ghi chú khác.

| Folder | Pack | Zone nguồn |
|---|---|---|
| `vn/` | `pack_vn_stub` → catalog VN-PDPD | `subject_zone=VN` |
| `eu/` | `pack_eu_stub` → catalog GDPR | `subject_zone=EU` |
| `us/` | `pack_us_stub` → catalog US | `subject_zone=US` |

**Cột ma trận** (mọi `*_controls.csv` cùng schema):

`zone,pack_id,control_code,law_ref,obligation_summary,responsible_party,severity,automation,control_id,sla,expected_behavior,fail_criteria`

- `sla` = hạn trên **phiếu / cửa ra**, không phải TTL 15 phút telemetry.  
- DSR (vd PDP-003/004): đồng hồ trên `dsr_requests.csv`, không trên từng dòng SOC.

`dsr_requests.csv` = phiếu chủ thể (ack 2 ngày LV, ngừng 15 ngày, sửa/cung cấp 10 ngày).

Chưa runtime. Điền hàng khi có ma trận đầy đủ.
