# 📋 DataTrust OS v5 Operational Trust Console.0 — Consolidated UI/UX & Mentor Workflow Board Specification

> **Document Status:** Official Consolidated UI/UX & Mentor Workflow Specification  
> **Canvas Dimensions:** 4,800px × 1,080px (3 Side-by-Side Sections)  
> **Target Audience:** Development Team & Project Mentors  
> **Excalidraw Elements:** 57 Interactive Canvas Elements Rendered  
> **Last Updated:** 2026-08-02  

---

## 🏛️ 1. Consolidated Canvas Overview

This document specifies the **single consolidated Excalidraw wireframe board** that unifies:
1. **TRANG 1 (Page 1)**: Executive Governance Homepage & Dashboard.
2. **TRANG 2 (Page 2)**: Agentic Chat & HITL Workspace with Fast Date/Rule Filters (Quickly search "3 days ago rules").
3. **TRANG 3 (Section 3)**: Vietnamese Workflow Board designed specifically for mentors to keep track of the DataTrust OS v5 Operational Trust Console.0 multi-agent governance pipeline.

---

## 🎨 2. Section Breakdown & Specifications

### Section 1: Executive Homepage & Dashboard (x=0..1550)
- **Top KPI Metrics Banner**: Monitored Datasets (8 Sources), Records Processed (1.45M Rows), Pending HITL Tasks (3 Rules), Composite Anomaly Index ($S_{composite} = 0.89$).
- **Rule Queue & Auto-Ingestion Panels**: Real-time pipeline status for ST-EVCDP V-GREEN Chargers, JAC IEV40 EV Telemetry, UIT-VSFC Feedback NLP, and Ride Hailing Trips.
- **Error Trends & RCA Panel**: 24-hour error distribution visualizer (GSM Basement Blackout, Charger Overheating @ 85.5°C, CAN-Bus Overvoltage @ 9999V).
- **Cryptographic Audit Ledger**: Clean DB vs Quarantine Table partition counts and SHA-256 lineage hash.

### Section 2: Agentic Chat UI & HITL Workspace (x=1600..3150)
- **Fast History Search & Filter Bar**:
  - Filter Input: `[🔍 Tìm Nhanh Lịch Sử Lỗi/Luật...]`
  - Preset Time Chips: `[Hôm Nay]` `[⚡ 3 Ngày Trước]` `[7 Ngày Trước]`
  - Highlighted Result: `💬 [30/07 - 3 Ngày Trước] Luật Telemetry: battery_soc >= 0.0 (14 Luật Đã Duyệt)`
- **Interactive HITL Rule Proposal Card**:
  - Pinned Sticky HITL Bar: `⚖️ Đang Chờ Duyệt (Luật 3 Ngày Trước - 30/07) | [✓ Duyệt Tất Cả] [✗ Từ Chối]`
  - Rule Proposal Details: `Column: battery_soc | Expression: battery_soc >= 0.0 AND battery_soc <= 100.0`
  - Action Controls: `[✓ Chấp Nhận]`, `[✗ Từ Chối]`, `[✏️ Sửa]`, `[▶ Chạy Clean DB Ngày 30/07]`.

### Section 3: Vietnamese Workflow Board for Mentor (x=3200..4750)
- **1️⃣ Bối Cảnh & Nguồn Dữ Liệu Thực Tế VinGroup (DATA-02)**: VinFast EV Telemetry, Trạm Sạc V-GREEN, Chuyến Đi Xanh SM, Phản Hồi Khách Hàng NLP.
- **2️⃣ Kiến Trúc Multi-Agent ReAct Bounded Loop (6 Agents)**:
  - `Orchestrator Agent` (Gemma-4-26b)
  - `Profiler Agent`
  - `Anomaly Detector Agent` (Dual Z-Score + Isolation Forest ML)
  - `Diagnosis Agent` (dbt Lineage RCA)
  - `Rule Proposer Agent`
  - `Executor Agent` (SHA-256 Audit Manifest)
- **3️⃣ Cơ Chế Con Người Giám Sát (HITL - Human-In-The-Loop)**: Steward Approval Gate (`Approve`, `Reject`, `Edit`).
- **4️⃣ Tính Năng Tra Cứu & Bộ Lọc Lịch Sử Nhanh**: Lọc theo mốc thời gian 3 ngày trước, thanh tìm kiếm `Ctrl + K`.
- **✨ Tổng Kết Luồng Vận Hành & Benchmark**: Pass 125/125 pytest tests, 100% policy compliance.

---

## 🧪 3. Deliverables Summary

- **Interactive Excalidraw Shareable Web Link**:  
  🔗 [https://excalidraw.com/#json=Wr_-1GsWSR73_Ks2_wOGt,nCKrkoG2v67drqoqM4Wrng](https://excalidraw.com/#json=Wr_-1GsWSR73_Ks2_wOGt,nCKrkoG2v67drqoqM4Wrng)
- **Local SVG Vector Graphic**:  
  🖼️ [docs/UI_UX_CONSOLIDATED_WORKFLOW_V3.svg](file:///home/shayneeo/Downloads/Documents/Coding/AI_in_Action/P-086/docs/UI_UX_CONSOLIDATED_WORKFLOW_V3.svg)
- **Specification Document**:  
  📝 [docs/UI_UX_CONSOLIDATED_WORKFLOW_V3.md](file:///home/shayneeo/Downloads/Documents/Coding/AI_in_Action/P-086/docs/UI_UX_CONSOLIDATED_WORKFLOW_V3.md)
