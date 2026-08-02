# 📌 TÓM TẮT DỰ ÁN DATATRUST OS V3.0 (PROJECT BRIEF)

## 🎯 Bài Toán Đặt Ra (Problem Statement)
Dữ liệu IoT từ xe điện VinFast, trạm sạc V-GREEN, chuyến đi Xanh SM và ứng dụng gặp rủi ro ô nhiễm lớn (mất sóng hầm, sạc quá nhiệt, nhiễu điện áp, teen-code). Việc xử lý thủ công gây chậm trễ, sai sót cho vận hành doanh nghiệp.

## 🚀 Đối Tượng Giải Quyết (Target Users)
Dành cho **Kỹ sư Dữ liệu (Data Engineers)**, **Chuyên viên Quản trị (Data Stewards)** và **Quản lý Vận hành** trong hệ sinh thái giao thông thông minh và xe điện tại Việt Nam.

## 🧭 Hướng Đi Chiến Lược (Strategic Direction)
Phát triển **Hệ điều hành Quản trị Dữ liệu Tự động** kết hợp **AI Multi-Agent ReAct** (mô hình Google Gemma-4 26B) và cơ chế **Con người Phê duyệt (Human-In-The-Loop - HITL)**, đảm bảo dữ liệu đáng tin cậy.

## 🔄 Luồng Vận Hành Hệ Thống (Workflow)
1. **Nạp dữ liệu (Ingestion)**: Thu thập tự động 4 nguồn dữ liệu VinGroup.
2. **AI Quét & Chẩn đoán**: Multi-Agent quét hồ sơ, phát hiện lỗi bất thường (Z-Score & Isolation Forest ML) và chẩn đoán nguyên nhân gốc RCA (dbt Lineage Graph).
3. **Phê duyệt HITL**: AI gợi ý bộ luật; Data Steward chấp nhận/từ chối/chỉnh sửa trực tiếp.
4. **Phân tách Clean DB**: Tách Dữ liệu Sạch & Bảng Cách ly (Quarantine), cấp mã hash SHA-256 xác thực kiểm toán.
