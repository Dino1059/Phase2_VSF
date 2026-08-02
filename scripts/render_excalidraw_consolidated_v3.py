import json

def build_consolidated_elements():
    # Canvas total size: 4800 x 1100
    # Section 1: Page 1 - Homepage & Dashboard (x=0..1550, w=1550)
    # Section 2: Page 2 - Agentic Chat & HITL Workspace with Fast Filters (x=1600..3150, w=1550)
    # Section 3: Mentor Workflow Board in Vietnamese (x=3200..4750, w=1550)

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
        {"id": "s1_new_chat", "type": "rectangle", "x": 10, "y": 140, "width": 250, "height": 45, "backgroundColor": "#b2f2bb", "strokeColor": "#2f9e44", "text": "+ Phiên Chat Agent Mới"},
        {"id": "s1_lbl_threads", "type": "text", "x": 10, "y": 200, "fontSize": 14, "strokeColor": "#868e96", "text": "DANH SÁCH TIẾN TRÌNH AGENT"},
        {"id": "s1_th_1", "type": "rectangle", "x": 10, "y": 225, "width": 250, "height": 42, "backgroundColor": "#ffffff", "strokeColor": "#868e96", "text": "💬 VinFast EV Telemetry Scan"},
        {"id": "s1_th_2", "type": "rectangle", "x": 10, "y": 275, "width": 250, "height": 42, "backgroundColor": "#ffffff", "strokeColor": "#868e96", "text": "💬 V-GREEN Charger Overheat"},
        {"id": "s1_th_3", "type": "rectangle", "x": 10, "y": 325, "width": 250, "height": 42, "backgroundColor": "#ffffff", "strokeColor": "#868e96", "text": "💬 Xanh SM Trips Ledger Audit"},
        {"id": "s1_th_4", "type": "rectangle", "x": 10, "y": 375, "width": 250, "height": 42, "backgroundColor": "#ffffff", "strokeColor": "#868e96", "text": "💬 Phản Hồi Khách Hàng NLP"},

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
    # SECTION 2: PAGE 2 — AGENTIC CHAT & HITL WORKSPACE WITH FAST FILTERS (x=1600..3150)
    # =========================================================================
    elements.extend([
        {"id": "s2_bg", "type": "rectangle", "x": 1600, "y": 0, "width": 1550, "height": 1050, "strokeColor": "#2f9e44", "strokeWidth": 3, "backgroundColor": "#ffffff", "text": ""},
        {"id": "s2_hdr", "type": "rectangle", "x": 1600, "y": 0, "width": 1550, "height": 70, "strokeColor": "#2f9e44", "strokeWidth": 2, "backgroundColor": "#b2f2bb", "text": ""},
        {"id": "s2_title", "type": "text", "x": 1620, "y": 24, "fontSize": 18, "strokeColor": "#1e1e1e", "text": "💬 TRANG 2: Agentic Chat UI & HITL Workspace (Tích Hợp Tra Cứu & Bộ Lọc Nhanh 3 Ngày Trước)"},
        
        # Sidebar with Fast History Filters
        {"id": "s2_side", "type": "rectangle", "x": 1600, "y": 70, "width": 290, "height": 980, "strokeColor": "#868e96", "strokeWidth": 2, "backgroundColor": "#e9ecef", "text": ""},
        {"id": "s2_filter_box", "type": "rectangle", "x": 1610, "y": 80, "width": 270, "height": 42, "backgroundColor": "#ffffff", "strokeColor": "#1971c2", "text": "🔍 Tìm Nhanh Lịch Sử Lỗi/Luật..."},
        {"id": "s2_chip_label", "type": "text", "x": 1610, "y": 130, "fontSize": 12, "strokeColor": "#868e96", "text": "BỘ LỌC THEO MỐC THỜI GIAN VẬN HÀNH:"},
        {"id": "s2_chip_today", "type": "rectangle", "x": 1610, "y": 150, "width": 80, "height": 30, "backgroundColor": "#ffffff", "strokeColor": "#868e96", "text": "Hôm Nay"},
        {"id": "s2_chip_3days", "type": "rectangle", "x": 1695, "y": 150, "width": 95, "height": 30, "backgroundColor": "#ffd8a8", "strokeColor": "#e8590c", "strokeWidth": 2, "text": "⚡ 3 Ngày Trước"},
        {"id": "s2_chip_7days", "type": "rectangle", "x": 1795, "y": 150, "width": 85, "height": 30, "backgroundColor": "#ffffff", "strokeColor": "#868e96", "text": "7 Ngày Trước"},
        
        {"id": "s2_lbl_hist_list", "type": "text", "x": 1610, "y": 195, "fontSize": 12, "strokeColor": "#e8590c", "text": "KẾT QUẢ LỌC: LUẬT & DATA FLOW (3 NÀY TRƯỚC):"},
        {"id": "s2_hist_1", "type": "rectangle", "x": 1610, "y": 215, "width": 270, "height": 55, "backgroundColor": "#ffd8a8", "strokeColor": "#e8590c", "strokeWidth": 2, "text": "💬 [30/07 - 3 Ngày Trước]\nLuật Telemetry: battery_soc >= 0.0\nStatus: 14 Luật Đã Duyệt"},
        {"id": "s2_hist_2", "type": "rectangle", "x": 1610, "y": 278, "width": 270, "height": 55, "backgroundColor": "#ffffff", "strokeColor": "#868e96", "text": "💬 [30/07 - 3 Ngày Trước]\nTrạm Sạc V-GREEN: Temp < 85°C\nStatus: 8 Luật Đã Duyệt"},
        {"id": "s2_hist_3", "type": "rectangle", "x": 1610, "y": 341, "width": 270, "height": 55, "backgroundColor": "#ffffff", "strokeColor": "#868e96", "text": "💬 [31/07 - 2 Ngày Trước]\nXanh SM Trips: Fare > 0 VND"},
        {"id": "s2_hist_4", "type": "rectangle", "x": 1610, "y": 404, "width": 270, "height": 55, "backgroundColor": "#ffffff", "strokeColor": "#868e96", "text": "💬 [02/08 - Hôm Nay]\nPhản Hồi NLP Teen-code Audit"},

        # Center Chat Area
        {"id": "s2_chat_zone", "type": "rectangle", "x": 1890, "y": 70, "width": 610, "height": 980, "strokeColor": "#1e1e1e", "strokeWidth": 2, "backgroundColor": "#ffffff", "text": ""},
        {"id": "s2_sticky_hitl", "type": "rectangle", "x": 1905, "y": 80, "width": 580, "height": 45, "backgroundColor": "#ffd8a8", "strokeColor": "#e8590c", "text": "⚖️ Đang Chờ Duyệt (Luật 3 Ngày Trước - 30/07)  |  [✓ Duyệt Tất Cả]  [✗ Từ Chối]"},
        {"id": "s2_msg_user", "type": "rectangle", "x": 1915, "y": 135, "width": 560, "height": 45, "backgroundColor": "#a5d8ff", "strokeColor": "#1971c2", "text": "👤 Steward: Tra cứu lại các luật tự động đề xuất từ luồng dữ liệu 3 ngày trước (30/07)?"},
        {"id": "s2_msg_orchestrator", "type": "rectangle", "x": 1915, "y": 190, "width": 560, "height": 65, "backgroundColor": "#eebefa", "strokeColor": "#9c36b5", "text": "🤖 Orchestrator Agent (Gemma-4-26b):\nTìm thấy 14 luật đã duyệt & 3 luật đang chờ phê duyệt từ phiên chạy ngày 30/07/2026."},
        
        # HITL Card
        {"id": "s2_hitl_card", "type": "rectangle", "x": 1915, "y": 265, "width": 560, "height": 165, "backgroundColor": "#ffffff", "strokeColor": "#2f9e44", "strokeWidth": 2, "text": "🛡️ Rule Proposer Agent (Đề Xuất Ngày 30/07 - 3 Ngày Trước):\nCột: battery_soc  |  Loại: Check Miền Giá Trị  |  Mức Độ: CRITICAL\nBiểu Thức: battery_soc >= 0.0 AND battery_soc <= 100.0\nMô Tả: Đảm bảo phần trăm pin xe VinFast không bị âm do lỗi CAN-Bus."},
        {"id": "s2_btn_app", "type": "rectangle", "x": 1930, "y": 380, "width": 105, "height": 38, "backgroundColor": "#b2f2bb", "strokeColor": "#2f9e44", "text": "✓ Chấp Nhận"},
        {"id": "s2_btn_rej", "type": "rectangle", "x": 2045, "y": 380, "width": 95, "height": 38, "backgroundColor": "#ffc9c9", "strokeColor": "#e03131", "text": "✗ Từ Chối"},
        {"id": "s2_btn_edit", "type": "rectangle", "x": 2150, "y": 380, "width": 90, "height": 38, "backgroundColor": "#e9ecef", "strokeColor": "#868e96", "text": "✏️ Sửa"},
        {"id": "s2_btn_run", "type": "rectangle", "x": 2250, "y": 380, "width": 210, "height": 38, "backgroundColor": "#a5d8ff", "strokeColor": "#1971c2", "text": "▶ Chạy Clean DB Ngày 30/07"},

        {"id": "s2_input", "type": "rectangle", "x": 1905, "y": 985, "width": 580, "height": 55, "backgroundColor": "#ffffff", "strokeColor": "#1e1e1e", "text": "💬 Nhập câu lệnh hoặc tra cứu lịch sử dữ liệu...                                [📎 Upload]"},

        # Right Workspace Dashboard
        {"id": "s2_work_zone", "type": "rectangle", "x": 2500, "y": 70, "width": 650, "height": 980, "strokeColor": "#0c8599", "strokeWidth": 2, "backgroundColor": "#99e9f2", "text": ""},
        {"id": "s2_tab_bar", "type": "rectangle", "x": 2515, "y": 80, "width": 620, "height": 42, "backgroundColor": "#ffffff", "strokeColor": "#0c8599", "text": "[📊 Profile]   [🛡️ Rules Lịch Sử]   [⚠️ Anomaly & RCA]   [📋 Audit Log]"},
        {"id": "s2_rca_box", "type": "rectangle", "x": 2515, "y": 135, "width": 620, "height": 180, "backgroundColor": "#ffd8a8", "strokeColor": "#e8590c", "strokeWidth": 2, "text": "🔥 Chẩn Đoán Lỗi 3 Ngày Trước (Ngày 30/07/2026):\n\n• S_composite: 0.91 (Cảnh báo cao)\n• Phát Hiện: 145 bản ghi bị nhảy Pin âm (-12.5%) & 25 bản ghi mất GPS Hầm Vincom.\n• Chẩn Đoán AI (dbt Lineage): Tín hiệu CAN-Bus bị nghẽn khi xe mất sóng 3G/4G.\n• Trạng Thái: Đã áp dụng luật nội suy & đẩy 25 bản ghi lỗi vào Quarantine Table."},
        {"id": "s2_audit_box", "type": "rectangle", "x": 2515, "y": 330, "width": 620, "height": 220, "backgroundColor": "#ffffff", "strokeColor": "#1e1e1e", "strokeWidth": 2, "text": "📋 Bảng Tra Cứu Luật Đã Duyệt 3 Ngày Trước (30/07/2026):\n\n1. RULE-001 (battery_soc >= 0): Phê duyệt bởi Steward @ 30/07 14:20\n2. RULE-002 (battery_voltage <= 500V): Phê duyệt bởi Steward @ 30/07 14:22\n3. RULE-003 (speed_kmh >= 0): Phê duyệt bởi Steward @ 30/07 14:25\n4. RULE-004 (station_temp < 85.5°C): Phê duyệt bởi Steward @ 30/07 15:10\n\nMã SHA-256 Audit Manifest: 7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284"}
    ])

    # =========================================================================
    # SECTION 3: VIETNAMESE WORKFLOW BOARD FOR MENTOR (x=3200..4750)
    # =========================================================================
    elements.extend([
        {"id": "s3_bg", "type": "rectangle", "x": 3200, "y": 0, "width": 1550, "height": 1050, "strokeColor": "#9c36b5", "strokeWidth": 3, "backgroundColor": "#fcf5ff", "text": ""},
        {"id": "s3_hdr", "type": "rectangle", "x": 3200, "y": 0, "width": 1550, "height": 70, "strokeColor": "#9c36b5", "strokeWidth": 2, "backgroundColor": "#eebefa", "text": ""},
        {"id": "s3_title", "type": "text", "x": 3220, "y": 24, "fontSize": 18, "strokeColor": "#1e1e1e", "text": "📋 BẢNG MÔ TẢ QUY TRÌNH HỆ THỐNG DATATRUST OS V3.0 (DÀNH CHO MENTOR)"},
        
        # Section 3 Board Contents
        {"id": "s3_b1", "type": "rectangle", "x": 3230, "y": 85, "width": 710, "height": 280, "backgroundColor": "#ffffff", "strokeColor": "#1971c2", "strokeWidth": 2, "text": "1️⃣ BỐI CẢNH & NGUỒN DỮ LIỆU THỰC TẾ VINGROUP (DATA-02):\n\n• VinFast EV Telemetry IoT: Dữ liệu cảm biến pin (BMS), tốc độ, điện áp, nhiệt độ.\n• V-GREEN Charging Stations: Dữ liệu dòng sạc, thời gian sạc, công suất kW, cảnh báo quá nhiệt.\n• Xanh SM Trips Ledger: Giao dịch chuyến đi, khoảng cách, giá cước, giảm giá.\n• Customer App Feedback NLP: Phản hồi khách hàng Tiếng Việt chứa Teen-code / từ lóng.\n\n👉 Tất cả được thu thập tự động hàng ngày qua Ingestion Pipeline tích hợp vào DataTrust OS."},

        {"id": "s3_b2", "type": "rectangle", "x": 3960, "y": 85, "width": 760, "height": 280, "backgroundColor": "#ffffff", "strokeColor": "#9c36b5", "strokeWidth": 2, "text": "2️⃣ KIẾN TRÚC MULTI-AGENT REACT BOUNDED LOOP (6 AGENTS CHUYÊN BIỆT):\n\n1. Orchestrator Agent (Gemma-4-26b): Điều phối luồng ReAct & quyết định chuyển giao tác vụ.\n2. Profiler Agent: Quét cấu trúc dữ liệu, thống kê Null Rate, Unique Rate, Min/Max.\n3. Anomaly Detector Agent: Thuật toán kép (MAD Z-Score + Isolation Forest ML) phát hiện 9 nhóm lỗi.\n4. Diagnosis Agent: Phân tích nguyên nhân gốc (RCA) dựa trên đồ thị phụ thuộc dbt Lineage Graph.\n5. Rule Proposer Agent: Tự động tổng hợp và đề xuất bộ luật kiểm soát chất lượng dữ liệu.\n6. Executor Agent: Phân tách Clean DB & Quarantine Table, cấp mã hash SHA-256 bảo mật."},

        {"id": "s3_b3", "type": "rectangle", "x": 3230, "y": 380, "width": 710, "height": 330, "backgroundColor": "#ffffff", "strokeColor": "#2f9e44", "strokeWidth": 2, "text": "3️⃣ CƠ CHẾ CON NGƯỜI GIÁM SÁT (HITL - HUMAN-IN-THE-LOOP):\n\n• Agent KHÔNG TỰ Ý sửa dữ liệu gốc: Mọi luật chất lượng dữ liệu do Rule Proposer đề xuất đều phải đi qua Cổng Kiểm Soát (Permission Gate).\n• Steward có quyền:\n  - [✓ Approve]: Chấp nhận luật và cho phép Executor phân tách Clean DB.\n  - [✗ Reject]: Từ chối luật không phù hợp kèm lý do phản hồi.\n  - [✏️ Edit]: Chỉnh sửa biểu thức điều kiện (Expression/Threshold) trực tiếp.\n• Đảm bảo tính minh bạch, tuân thủ quản trị dữ liệu doanh nghiệp và tránh lỗi AI hallucination."},

        {"id": "s3_b4", "type": "rectangle", "x": 3960, "y": 380, "width": 760, "height": 330, "backgroundColor": "#ffffff", "strokeColor": "#e8590c", "strokeWidth": 2, "text": "4️⃣ TÍNH NĂNG TRA CỨU & BỘ LỌC LỊCH SỬ NHANH (SEARCH & FILTERS):\n\n• Bộ Lọc Mốc Thời Gian Vận Hành: Nút bấm 1-click lọc nhanh dữ liệu [Hôm Nay], [3 Ngày Trước], [7 Ngày Trước].\n• Thống Kê & Lập Luật Theo Ngày: Người dùng / Mentor dễ dàng tra cứu lại bộ luật được đề xuất và phê duyệt cách đây 3 ngày (30/07/2026).\n• Thanh Tìm Kiếm Thông Minh (Ctrl + K): Tra cứu tức thì toàn bộ lịch sử hội thoại, danh sách luật, báo cáo RCA và mã audit manifest Hash SHA-256.\n• Đảm bảo việc theo dõi tiến độ và đánh giá lại chất lượng pipeline cực kỳ đơn giản."},

        {"id": "s3_b5", "type": "rectangle", "x": 3230, "y": 725, "width": 1490, "height": 290, "backgroundColor": "#b2f2bb", "strokeColor": "#2f9e44", "strokeWidth": 2, "text": "✨ TỔNG KẾT LUỒNG VẬN HÀNH & KẾT QUẢ ĐẠT ĐƯỢC (BENCHMARK VERIFIED):\n\n1. Ingestion Tự Động ➔ 2. Phân Tích & Chẩn Đoán AI ➔ 3. Đề Xuất Luật ➔ 4. Steward Phê Duyệt (HITL) ➔ 5. Phân Tách Clean DB & Cấp Mã Lineage Hash SHA-256.\n\n• Đã vượt qua 125 / 125 Pytest Tests (Đạt 100% Pass Gate).\n• Tích hợp mô hình AI đơn duy nhất Google Gemma-4 26B (gemma-4-26b-a4b-it) hỗ trợ Native Function Calling.\n• Xử lý hoàn hảo 4 bộ dữ liệu thực tế VinGroup (VinFast EV, V-GREEN, Xanh SM, NLP Phản Hồi Khách Hàng)."}
    ])

    return elements

if __name__ == "__main__":
    elements = build_consolidated_elements()
    with open('/tmp/excalidraw_consolidated_v3.json', 'w') as f:
        json.dump(elements, f)
    print(f"Generated {len(elements)} consolidated canvas elements")
