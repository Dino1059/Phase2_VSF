import json

def build_elements():
    # Canvas total size: 4800 x 1100
    # Section 1: Page 1 - Executive Homepage & Dashboard (x=0..1550, w=1550)
    # Section 2: Page 2 - Agentic Chat UI & Workspace (x=1600..3150, w=1550) -> Chat filter inside stream (1 DB per session)
    # Section 3: Mentor Board (x=3200..4750, w=1550) -> 1 single clean text frame with bullet points in Vietnamese

    elements = []

    # =========================================================================
    # SECTION 1: PAGE 1 — EXECUTIVE HOMEPAGE & DASHBOARD (x=0..1550)
    # =========================================================================
    elements.extend([
        {"id": "s1_bg", "type": "rectangle", "x": 0, "y": 0, "width": 1550, "height": 1050, "strokeColor": "#1971c2", "strokeWidth": 3, "backgroundColor": "#ffffff", "text": ""},
        {"id": "s1_hdr", "type": "rectangle", "x": 0, "y": 0, "width": 1550, "height": 70, "strokeColor": "#1971c2", "strokeWidth": 2, "backgroundColor": "#a5d8ff", "text": ""},
        {"id": "s1_title", "type": "text", "x": 20, "y": 24, "fontSize": 18, "strokeColor": "#1e1e1e", "text": "🖥️ TRANG 1: Executive Governance Homepage & Dashboard (DataTrust OS v3.0)"},
        
        {"id": "s1_side", "type": "rectangle", "x": 0, "y": 70, "width": 270, "height": 980, "strokeColor": "#868e96", "strokeWidth": 2, "backgroundColor": "#e9ecef", "text": ""},
        {"id": "s1_home_btn", "type": "rectangle", "x": 10, "y": 85, "width": 250, "height": 45, "backgroundColor": "#a5d8ff", "strokeColor": "#1971c2", "strokeWidth": 2, "text": "🏠 Executive Homepage / Dashboard"},
        {"id": "s1_new_chat", "type": "rectangle", "x": 10, "y": 140, "width": 250, "height": 45, "backgroundColor": "#b2f2bb", "strokeColor": "#2f9e44", "text": "+ Phiên Chat Theo Dataset Mới"},
        {"id": "s1_lbl_threads", "type": "text", "x": 10, "y": 200, "fontSize": 13, "strokeColor": "#868e96", "text": "PHIÊN CHAT THEO TỪNG CSDL (1 DB / CHAT):"},
        {"id": "s1_th_1", "type": "rectangle", "x": 10, "y": 225, "width": 250, "height": 45, "backgroundColor": "#ffffff", "strokeColor": "#868e96", "text": "📦 [DB] VinFast EV Telemetry"},
        {"id": "s1_th_2", "type": "rectangle", "x": 10, "y": 280, "width": 250, "height": 45, "backgroundColor": "#ffffff", "strokeColor": "#868e96", "text": "📦 [DB] V-GREEN Charging Stations"},
        {"id": "s1_th_3", "type": "rectangle", "x": 10, "y": 335, "width": 250, "height": 45, "backgroundColor": "#ffffff", "strokeColor": "#868e96", "text": "📦 [DB] Xanh SM Trips Ledger"},
        {"id": "s1_th_4", "type": "rectangle", "x": 10, "y": 390, "width": 250, "height": 45, "backgroundColor": "#ffffff", "strokeColor": "#868e96", "text": "📦 [DB] Customer Feedback NLP"},

        # KPIs Banner
        {"id": "s1_kpi1", "type": "rectangle", "x": 290, "y": 85, "width": 290, "height": 80, "backgroundColor": "#ffffff", "strokeColor": "#1971c2", "strokeWidth": 2, "text": "📊 Datasets Theo Dõi:\n8 Nguồn VinGroup (100% Active)"},
        {"id": "s1_kpi2", "type": "rectangle", "x": 595, "y": 85, "width": 300, "height": 80, "backgroundColor": "#ffffff", "strokeColor": "#2f9e44", "strokeWidth": 2, "text": "⚡ Bản Ghi Đã Xử Lý:\n1,450,000 Rows (94.2% Clean DB)"},
        {"id": "s1_kpi3", "type": "rectangle", "x": 910, "y": 85, "width": 300, "height": 80, "backgroundColor": "#ffd8a8", "strokeColor": "#e8590c", "strokeWidth": 2, "text": "⚖️ Nhiệm Vụ HITL Chờ Duyệt:\n3 Luật Cần Steward Phê Duyệt"},
        {"id": "s1_kpi4", "type": "rectangle", "x": 1225, "y": 85, "width": 310, "height": 80, "backgroundColor": "#ffffff", "strokeColor": "#9c36b5", "strokeWidth": 2, "text": "🔥 Chỉ Số Bất Thường Đổ Về:\nS_composite = 0.89 (Ổn Định)"},

        # Row 1 Dashboard
        {"id": "s1_panel_rules", "type": "rectangle", "x": 290, "y": 180, "width": 610, "height": 280, "backgroundColor": "#ffffff", "strokeColor": "#2f9e44", "strokeWidth": 2, "text": "🛡️ Luật Đề Xuất Tự Động & Hàng Chờ Phê Duyệt (HITL Task Queue):\n\n1. [CRITICAL] battery_soc >= 0.0 AND battery_soc <= 100.0 (Cột: battery_soc)\n   [✓ Duyệt Ngay]   [✗ Từ Chối]   [✏️ Chỉnh Sửa]\n\n2. [WARNING] duration_minutes > 0.0 AND duration_minutes < 720 (Cột: duration)\n   [✓ Duyệt Ngay]   [✗ Từ Chối]   [✏️ Chỉnh Sửa]\n\n3. [INFO] total_fare >= fare_amount (Cột: total_fare)\n   [✓ Duyệt Ngay]   [✗ Từ Chối]   [✏️ Chỉnh Sửa]"},
        {"id": "s1_btn_approve_all", "type": "rectangle", "x": 305, "y": 415, "width": 260, "height": 35, "backgroundColor": "#b2f2bb", "strokeColor": "#2f9e44", "text": "✓ Phê Duyệt Tất Cả 3 Luật Chờ"},
        
        {"id": "s1_panel_flow", "type": "rectangle", "x": 920, "y": 180, "width": 615, "height": 280, "backgroundColor": "#ffffff", "strokeColor": "#0c8599", "strokeWidth": 2, "text": "🔄 Luồng Dữ Liệu Tự Động Ingestion Pipeline Status:\n\n1. ST-EVCDP V-GREEN Feed: 500,000 rows | Cảnh báo quá nhiệt 85.5°C\n2. JAC IEV40 EV Telemetry Feed: 450,000 rows | Cảnh báo mất sóng hầm GSM\n3. UIT-VSFC Feedback NLP Feed: 250,000 rows | Chuẩn hóa Teen-code Tiếng Việt\n4. Ride Hailing Transactions Feed: 250,000 rows | Phân tách Clean/Quarantine"},

        # Row 2 Dashboard
        {"id": "s1_panel_trends", "type": "rectangle", "x": 290, "y": 475, "width": 610, "height": 270, "backgroundColor": "#ffffff", "strokeColor": "#e03131", "strokeWidth": 2, "text": "📈 Biểu Đồ Xu Hướng Lỗi & Bất Thường Theo Thời Gian (24H):\n\n• 00:00 - 06:00 ── Trạng thái bình thường (12 lỗi/giờ)\n• 06:00 - 12:00 ────── Mất sóng GSM Hầm Vincom (145 lỗi/giờ)\n• 12:00 - 18:00 ──── Overheat Trạm Sạc V-GREEN (88 lỗi/giờ)\n• 18:00 - 24:00 ── Overvoltage CAN-Bus 9999V (32 lỗi/giờ)\n\nPhân Phân Mức Độ: 🔴 Critical: 18% | 🟡 Warning: 62% | 🔵 Info: 20%"},

        {"id": "s1_panel_rca", "type": "rectangle", "x": 920, "y": 475, "width": 615, "height": 270, "backgroundColor": "#ffffff", "strokeColor": "#9c36b5", "strokeWidth": 2, "text": "🩺 Multi-Agent Anomaly Detector & Chẩn Đoán Nguyên Nhân Gốc (RCA):\n\nThuật Toán: Dual Composite Score (MAD Z-Score + Isolation Forest ML)\nPhân Tích Nguyên Nhân Gốc (dbt Lineage Graph):\n1. Xe VinFast VF8 vào hầm Vincom Landmark 81 làm mất tín hiệu GPS (45%)\n2. Trạm sạc V-GREEN sạc dòng cao gây ngắt nhiệt bảo vệ ở 85.5°C (30%)\n3. Teen-code trong đánh giá app cần từ điển chuẩn hóa NLP (25%)"},

        # Bottom Audit Ledger
        {"id": "s1_audit_ledger", "type": "rectangle", "x": 290, "y": 760, "width": 1245, "height": 270, "backgroundColor": "#b2f2bb", "strokeColor": "#2f9e44", "strokeWidth": 2, "text": "✨ Nhật Ký Quản Trị & Cấp Mã SHA-256 Cryptographic Audit Ledger:\n\n• Tổng Số Bản Ghi Clean DB: 1,365,900 rows (94.2% Hoàn Hảo)\n• Tổng Số Bản Ghi Cách Ly (Quarantine Table): 84,100 rows (5.8% Đã Cách Ly)\n• Mã Hash Mã Hóa Lineage SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e462d71dce99026daef3200a\n• Lịch Sử Kiểm Soát Steward: 142 Luật Đã Phê Duyệt | 12 Luật Từ Chối | 100% Tuân Thủ Quản Trị"}
    ])

    # =========================================================================
    # SECTION 2: PAGE 2 — AGENTIC CHAT UI WITH IN-STREAM DATE FILTER BAR (x=1600..3150)
    # =========================================================================
    elements.extend([
        {"id": "s2_bg", "type": "rectangle", "x": 1600, "y": 0, "width": 1550, "height": 1050, "strokeColor": "#2f9e44", "strokeWidth": 3, "backgroundColor": "#ffffff", "text": ""},
        {"id": "s2_hdr", "type": "rectangle", "x": 1600, "y": 0, "width": 1550, "height": 70, "strokeColor": "#2f9e44", "strokeWidth": 2, "backgroundColor": "#b2f2bb", "text": ""},
        {"id": "s2_title", "type": "text", "x": 1620, "y": 24, "fontSize": 18, "strokeColor": "#1e1e1e", "text": "💬 TRANG 2: Phiên Chat Dedicated CSDL (Log Daily Operation & Filter Ngày/Tuần/Tháng Trong Stream)"},
        
        # Sidebar with 1 DB per Session
        {"id": "s2_side", "type": "rectangle", "x": 1600, "y": 70, "width": 290, "height": 980, "strokeColor": "#868e96", "strokeWidth": 2, "backgroundColor": "#e9ecef", "text": ""},
        {"id": "s2_new_chat_btn", "type": "rectangle", "x": 1610, "y": 80, "width": 270, "height": 45, "backgroundColor": "#b2f2bb", "strokeColor": "#2f9e44", "text": "+ Phiên Chat Theo Dataset Mới"},
        {"id": "s2_lbl_db_sessions", "type": "text", "x": 1610, "y": 140, "fontSize": 12, "strokeColor": "#868e96", "text": "DANH SÁCH CSDL (1 PHIÊN CHAT / 1 DB):"},
        
        {"id": "s2_sess_active", "type": "rectangle", "x": 1610, "y": 165, "width": 270, "height": 55, "backgroundColor": "#a5d8ff", "strokeColor": "#1971c2", "strokeWidth": 2, "text": "📦 [DB Active] VinFast EV Telemetry\nThread: VinFast IoT Data Logs"},
        {"id": "s2_sess_2", "type": "rectangle", "x": 1610, "y": 230, "width": 270, "height": 50, "backgroundColor": "#ffffff", "strokeColor": "#868e96", "text": "📦 [DB] V-GREEN Charging Stations"},
        {"id": "s2_sess_3", "type": "rectangle", "x": 1610, "y": 290, "width": 270, "height": 50, "backgroundColor": "#ffffff", "strokeColor": "#868e96", "text": "📦 [DB] Xanh SM Trips Ledger"},
        {"id": "s2_sess_4", "type": "rectangle", "x": 1610, "y": 350, "width": 270, "height": 50, "backgroundColor": "#ffffff", "strokeColor": "#868e96", "text": "📦 [DB] Customer Feedback NLP"},

        # Center Chat Area with IN-STREAM Date Filter Bar!
        {"id": "s2_chat_zone", "type": "rectangle", "x": 1890, "y": 70, "width": 610, "height": 980, "strokeColor": "#1e1e1e", "strokeWidth": 2, "backgroundColor": "#ffffff", "text": ""},
        
        # IN-STREAM DATE FILTER BAR!
        {"id": "s2_stream_filter_bar", "type": "rectangle", "x": 1900, "y": 80, "width": 590, "height": 45, "backgroundColor": "#f8f9fa", "strokeColor": "#1971c2", "strokeWidth": 2, "text": "📅 Lọc Nhật Ký Daily Operation:  [Hôm Nay]   [⚡ 3d (3 Ngày Trước)]   [7d]   [Tuần Này]   [Tháng Này]"},
        
        {"id": "s2_sticky_hitl", "type": "rectangle", "x": 1900, "y": 135, "width": 590, "height": 45, "backgroundColor": "#ffd8a8", "strokeColor": "#e8590c", "text": "⚖️ Cảnh Báo Daily Operation (30/07/2026 - 3 Ngày Trước): 3 Luật Cần Phê Duyệt"},
        
        {"id": "s2_msg_log_header", "type": "rectangle", "x": 1910, "y": 190, "width": 570, "height": 40, "backgroundColor": "#e9ecef", "strokeColor": "#868e96", "text": "📆 Nhật Ký Vận Hành Ngày 30/07/2026 (3 Ngày Trước) — CSDL: VinFast EV Telemetry"},
        
        {"id": "s2_msg_user", "type": "rectangle", "x": 1910, "y": 240, "width": 570, "height": 45, "backgroundColor": "#a5d8ff", "strokeColor": "#1971c2", "text": "👤 Steward: Kiểm tra nhật ký vận hành & luật tự động phát sinh 3 ngày trước (30/07)?"},
        
        {"id": "s2_msg_orchestrator", "type": "rectangle", "x": 1910, "y": 295, "width": 570, "height": 65, "backgroundColor": "#eebefa", "strokeColor": "#9c36b5", "text": "🤖 Orchestrator Agent (Gemma-4-26b):\nĐã lọc nhật ký vận hành ngày 30/07/2026. Tìm thấy 145 bản ghi nhảy Pin âm (-12.5%) & 25 bản ghi mất GPS Hầm Vincom."},
        
        # HITL Card inside chat stream
        {"id": "s2_hitl_card", "type": "rectangle", "x": 1910, "y": 370, "width": 570, "height": 165, "backgroundColor": "#ffffff", "strokeColor": "#2f9e44", "strokeWidth": 2, "text": "🛡️ Rule Proposer Agent (Luật Đề Xuất Nhật Ký 30/07 - 3d):\nCột: battery_soc  |  Loại: Check Miền Giá Trị  |  Mức Độ: CRITICAL\nBiểu Thức: battery_soc >= 0.0 AND battery_soc <= 100.0\nMô Tả: Đảm bảo phần trăm pin xe VinFast không bị âm do nhiễu CAN-Bus."},
        {"id": "s2_btn_app", "type": "rectangle", "x": 1925, "y": 485, "width": 105, "height": 38, "backgroundColor": "#b2f2bb", "strokeColor": "#2f9e44", "text": "✓ Chấp Nhận"},
        {"id": "s2_btn_rej", "type": "rectangle", "x": 2040, "y": 485, "width": 95, "height": 38, "backgroundColor": "#ffc9c9", "strokeColor": "#e03131", "text": "✗ Từ Chối"},
        {"id": "s2_btn_edit", "type": "rectangle", "x": 2145, "y": 485, "width": 90, "height": 38, "backgroundColor": "#e9ecef", "strokeColor": "#868e96", "text": "✏️ Sửa"},
        {"id": "s2_btn_run", "type": "rectangle", "x": 2245, "y": 485, "width": 225, "height": 38, "backgroundColor": "#a5d8ff", "strokeColor": "#1971c2", "text": "▶ Phân Tách Clean DB Ngày 30/07"},

        {"id": "s2_input", "type": "rectangle", "x": 1900, "y": 985, "width": 590, "height": 55, "backgroundColor": "#ffffff", "strokeColor": "#1e1e1e", "text": "💬 Nhập câu lệnh hoặc tra cứu nhật ký daily operation...                          [📎 Upload]"},

        # Right Workspace Dashboard (Dedicated to current DB)
        {"id": "s2_work_zone", "type": "rectangle", "x": 2500, "y": 70, "width": 650, "height": 980, "strokeColor": "#0c8599", "strokeWidth": 2, "backgroundColor": "#99e9f2", "text": ""},
        {"id": "s2_tab_bar", "type": "rectangle", "x": 2515, "y": 80, "width": 620, "height": 42, "backgroundColor": "#ffffff", "strokeColor": "#0c8599", "text": "[📊 Profile DB]   [🛡️ Luật Đã Duyệt]   [⚠️ Anomaly & RCA 3d]   [📋 Audit Manifest]"},
        {"id": "s2_rca_box", "type": "rectangle", "x": 2515, "y": 135, "width": 620, "height": 180, "backgroundColor": "#ffd8a8", "strokeColor": "#e8590c", "strokeWidth": 2, "text": "🔥 Chẩn Đoán Lỗi Nhật Ký Ngày 30/07/2026 (3 Ngày Trước):\n\n• CSDL: real_vinfast_ev_telemetry\n• S_composite: 0.91 (Cảnh báo cao)\n• Chẩn Đoán AI (dbt Lineage): Tín hiệu CAN-Bus bị nhiễu khi xe ngắt kết nối 3G/4G Hầm Vincom.\n• Hành Động: Đã áp dụng luật nội suy & đẩy 25 bản ghi lỗi vào Quarantine Table."},
        {"id": "s2_audit_box", "type": "rectangle", "x": 2515, "y": 330, "width": 620, "height": 220, "backgroundColor": "#ffffff", "strokeColor": "#1e1e1e", "strokeWidth": 2, "text": "📋 Nhật Ký Quản Trị Luật CSDL VinFast EV (Lọc Ngày 30/07/2026):\n\n1. RULE-001 (battery_soc >= 0): Phê duyệt bởi Steward @ 30/07 14:20\n2. RULE-002 (battery_voltage <= 500V): Phê duyệt bởi Steward @ 30/07 14:22\n3. RULE-003 (speed_kmh >= 0): Phê duyệt bởi Steward @ 30/07 14:25\n\nMã SHA-256 Audit Manifest: 7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284"}
    ])

    # =========================================================================
    # SECTION 3: SIMPLIFIED VIETNAMESE MENTOR BOARD (1 CLEAN FRAME + BULLET POINTS)
    # =========================================================================
    elements.extend([
        {"id": "s3_bg", "type": "rectangle", "x": 3200, "y": 0, "width": 1550, "height": 1050, "strokeColor": "#9c36b5", "strokeWidth": 3, "backgroundColor": "#ffffff", "text": ""},
        {"id": "s3_hdr", "type": "rectangle", "x": 3200, "y": 0, "width": 1550, "height": 70, "strokeColor": "#9c36b5", "strokeWidth": 2, "backgroundColor": "#eebefa", "text": ""},
        {"id": "s3_title", "type": "text", "x": 3220, "y": 24, "fontSize": 18, "strokeColor": "#1e1e1e", "text": "📋 BẢNG MÔ TẢ QUY TRÌNH HỆ THỐNG DATATRUST OS V3.0 (DÀNH CHO MENTOR)"},
        
        # 1 SINGLE CLEAN TEXT FRAME FOR MENTOR WITH SIMPLE BULLET POINTS
        {"id": "s3_mentor_frame", "type": "rectangle", "x": 3230, "y": 85, "width": 1490, "height": 930, "backgroundColor": "#ffffff", "strokeColor": "#9c36b5", "strokeWidth": 2, "text": "📋 QUY TRÌNH QUẢN TRỊ CHẤT LƯỢNG DỮ LIỆU TỰ ĐỘNG (DATATRUST OS V3.0):\n\n• Nguồn Dữ Liệu Thực Tế VinGroup (DATA-02):\n  - Tự động nạp dữ liệu từ 4 miền: Telemetry Xe Điện VinFast, Trạm Sạc V-GREEN, Chuyến Đi Xanh SM, Phản Hồi Khách Hàng NLP.\n\n• Thiết Kế Phiên Chat Dành Riêng Cho Từng CSDL (1 Chat Session / 1 DB):\n  - Mỗi phiên chat là một luồng quản trị cho 1 CSDL cụ thể (VD: VinFast EV Telemetry), ghi lại toàn bộ nhật ký vận hành hàng ngày (Daily Operation Logs).\n\n• Bộ Lọc Thời Gian Trực Tiếp Trong Chat (In-Stream Filter Bar):\n  - Thanh lọc thời gian ngay trong giao diện chat giúp tra cứu nhanh nhật ký theo: [Hôm Nay], [3d - 3 Ngày Trước], [7d], [Tuần Này], [Tháng Này].\n  - Ví dụ: Dễ dàng lọc và kiểm tra lại danh sách luật tự động phát sinh và phê duyệt cách đây 3 ngày (30/07/2026).\n\n• Kiến Trúc 6 AI Agents ReAct Multi-Agent Loop (Động Cơ Google Gemma-4 26B):\n  - Orchestrator (Phân luồng) ➔ Profiler (Thống kê) ➔ Anomaly Detector (Phát hiện lỗi bằng Z-Score & Isolation Forest ML) ➔ Diagnosis (Chẩn đoán RCA bằng dbt Lineage Graph) ➔ Rule Proposer (Đề xuất luật) ➔ Executor (Phân tách Clean DB & Quarantine Table).\n\n• Cơ Chế Con Người Kiểm Soát Tối Cao (HITL - Human-In-The-Loop):\n  - AI không tự ý ghi đè dữ liệu. Mọi luật do AI đề xuất đều hiển thị thẻ tương tác cho Steward: [✓ Chấp Nhận], [✗ Từ Chối], [✏️ Sửa Điều Kiện].\n\n• Kiểm Soát & Bảo Mật Dữ Liệu:\n  - Cấp mã hash mã hóa SHA-256 Cryptographic Audit Manifest cho mọi giao dịch làm sạch dữ liệu.\n\n• Đã Xác Nhận Đạt Benchmark:\n  - Vượt qua 100% Pass Gate (125 / 125 Pytest Integration Tests)."}
    ])

    return elements

if __name__ == "__main__":
    elements = build_elements()
    with open('/tmp/excalidraw_simplified_v3.json', 'w') as f:
        json.dump(elements, f)
    print(f"Generated {len(elements)} simplified canvas elements")
