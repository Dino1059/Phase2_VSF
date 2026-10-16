# 🛡️ DataTrust OS & SoD Flow (Phase 2 VSF)

> **Hệ sinh thái Quản trị Chất lượng Dữ liệu, Tuân thủ Pháp lý Chuẩn IPO & Phân tách Trách nhiệm (Segregation of Duties - SoD)**  
> *Áp dụng thí điểm quy mô toàn cầu cho VinFast & GSM (3 Vùng lãnh thổ: Việt Nam, Châu Âu, Hoa Kỳ)*

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19.x-61DAFB.svg?style=flat&logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x%2F6.x-3178C6.svg?style=flat&logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![Vite](https://img.shields.io/badge/Vite-8.x-646CFF.svg?style=flat&logo=vite&logoColor=white)](https://vitejs.dev)
[![Apache Airflow](https://img.shields.io/badge/Apache_Airflow-2.5+-017CEE.svg?style=flat&logo=apacheairflow&logoColor=white)](https://airflow.apache.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-13%2B%20%7C%2016-4169E1.svg?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![LangChain](https://img.shields.io/badge/LangChain%20%2F%20LangGraph-0.3+-1C3C3C.svg?style=flat)](https://langchain.com)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)](LICENSE)

---

## 📑 Mục lục
1. [Giới thiệu Dự án](#-1-giới-thiệu-dự-án)
2. [Khung Tiêu chuẩn Tuân thủ & Pháp lý](#-2-khung-tiêu-chuẩn-tuân-thủ--pháp-lý)
3. [Kiến trúc Kỹ thuật Cốt lõi](#-3-kiến-trúc-kỹ-thuật-cốt-lõi)
   - [3.1. DataTrust OS: Pipeline Kiểm toán 3 Làn & Sổ cái Bất biến](#31-datatrust-os-pipeline-kiểm-toán-3-làn--sổ-cái-bất-biến)
   - [3.2. SoD Flow: Kiểm soát Phân tách Trách nhiệm (RACIX)](#32-sod-flow-kiểm-soát-phân-tách-trách-nhiệm-racix)
   - [3.3. Tích hợp 2 Chiều (Cross-System Integration)](#33-tích-hợp-2-chiều-cross-system-integration)
   - [3.4. Trợ lý AI Companion & Human-in-the-Loop (HITL)](#34-trợ-lý-ai-companion--human-in-the-loop-hitl)
4. [Tech Stack](#-4-tech-stack)
5. [Cấu trúc Thư mục Dự án](#-5-cấu-trúc-thư-mục-dự-án)
6. [Hướng dẫn Cài đặt & Khởi chạy Nhanh](#-6-hướng-dẫn-cài-đặt--khởi-chạy-nhanh)
   - [6.1. Yêu cầu Hệ thống](#61-yêu-cầu-hệ-thống)
   - [6.2. Cấu hình Môi trường (.env)](#62-cấu-hình-môi-trường-env)
   - [6.3. Khởi tạo Cơ sở Dữ liệu & Seed Data](#63-khởi-tạo-cơ-sở-dữ-liệu--seed-data)
   - [6.4. Khởi chạy Ứng dụng](#64-khởi-chạy-ứng-dụng)
7. [Tài khoản Demo & Ma trận Phân quyền (RBAC)](#-7-tài-khoản-demo--ma-trận-phân-quyền-rbac)
8. [Kiểm thử Tự động (Testing Suite)](#-8-kiểm-thử-tự-động-testing-suite)
9. [Hướng dẫn Triển khai (Deployment)](#-9-hướng-dẫn-triển-khai-deployment)
10. [Tài liệu Liên quan](#-10-tài-liệu-liên-quan)

---

## 🌟 1. Giới thiệu Dự án

**DataTrust OS & SoD Flow** là nền tảng quản trị chất lượng dữ liệu doanh nghiệp, kiểm toán tuân thủ pháp lý và quản soát phân quyền phân tách trách nhiệm (Segregation of Duties) tự động hóa toàn diện. Dự án được nghiên cứu và thiết kế chuyên biệt phục vụ tiêu chuẩn kiểm toán **IPO quốc tế** cho hệ sinh thái xe điện thông minh **VinFast** và dịch vụ gọi xe taxi điện **GSM** trên quy mô thí điểm 3 thị trường: **Việt Nam (VN), Châu Âu (EU), và Hoa Kỳ (US)**.

Hệ sinh thái giải quyết 3 thách thức lớn nhất của dữ liệu doanh nghiệp chuẩn bị IPO:
1. **Toàn vẹn Dữ liệu Doanh thu & Kỹ thuật**: Ngăn ngừa cuốc xe ảo, cước âm, sai lệch GPS và lỗi cảm biến pin xe điện trước khi đồng bộ vào kho dữ liệu báo cáo tài chính.
2. **Tuân thủ Quyền riêng tư (Privacy by Design)**: Tự động phát hiện và làm sạch thông tin định danh cá nhân (PII) qua cơ chế che mờ (masking), mã hóa băm một chiều (keyed HMAC-SHA256) và làm tròn tọa độ GPS thích ứng theo từng vùng pháp lý.
3. **Phân tách Trách nhiệm & Bằng chứng Kiểm toán Bất biến**: Ngăn chặn rủi ro xung đột quyền hạn nội bộ (gian lận SOX) qua ma trận RACIX, đồng thời phát hành chuỗi bằng chứng băm liên tục (Continuous SHA-256 Hash-Chaining / Merkle DAG) phục vụ kiểm toán độc lập.

---

## 📜 2. Khung Tiêu chuẩn Tuân thủ & Pháp lý

Hệ thống được xây dựng và căn chỉnh nghiêm ngặt theo các bộ luật và quy chuẩn quốc tế:

| Lĩnh vực | Tiêu chuẩn / Văn bản Luật | Nội dung Kiểm soát & Phạm vi Áp dụng |
| :--- | :--- | :--- |
| **Bảo vệ Dữ liệu Cá nhân VN** | **Luật 91/2025/QH15** & **Nghị định 356/2025/NĐ-CP** *(Hiệu lực 01/01/2026)* | Che mờ SĐT, CCCD, định danh tài xế có salt; Giới hạn độ chính xác tọa độ GPS cuốc xe dưới mức nhận dạng nhà riêng. |
| **Bảo vệ Dữ liệu EU** | **EU GDPR (General Data Protection Regulation)** | Tuân thủ Điều 5, 6, 9 & 32: Thu nhỏ dữ liệu (Data Minimization), xử lý dữ liệu định danh theo cơ chế Pseudonymization. |
| **Bảo vệ Dữ liệu Hoa Kỳ** | **US CCPA / CPRA** | Quyền riêng tư người tiêu dùng bang California; Bảo vệ dữ liệu nhạy cảm của khách hàng và lịch trình di chuyển. |
| **Kiểm soát Nội bộ & Tài chính** | **IFRS 15** & **SOX Section 404** | Ghi nhận doanh thu hợp đồng dịch vụ vận tải minh bạch; Triển khai kiểm soát nội bộ và phân tách trách nhiệm (SoD). |
| **Chất lượng Dữ liệu Công nghiệp** | **ISO 8000** | Đo lường độ chính xác, đầy đủ, tính duy nhất và tính kịp thời của dữ liệu số lớn. |
| **An toàn Kỹ thuật Xe Điện** | **ISO 26262 ASIL-D** & **UN ECE R100** | Cảnh báo nhiệt độ khối pin EV ($\le 65^\circ\text{C}$), trạng thái pin SoC, điện áp tế bào pin và telemetry động cơ. |

---

## 🏗️ 3. Kiến trúc Kỹ thuật Cốt lõi

### 3.1. DataTrust OS: Pipeline Kiểm toán 3 Làn & Sổ cái Bất biến

Quy trình xử lý dữ liệu đi qua 4 nhiệm vụ khép kín được điều phối tự động bởi Apache Airflow:

```mermaid
flowchart TD
    subgraph S1["TASK 1: Ingestion & Bronze Layer"]
        A1["Nguồn dữ liệu 3 Vùng (VN, EU, US)<br/>8 Bảng chuẩn CSV / Storage"] --> A2["Truncate & Ingest Bronze<br/>(Hỗ trợ Single-table hoặc ALL)"]
        A2 --> A3[("Schema: bronze.*<br/>catalog.datasets")]
    end

    subgraph S2["TASK 2: Data Profiling Engine"]
        A3 --> B1["Statistical Profiler & Health Scorer<br/>(Null rate, Unique rate, Z-score)"]
        B1 --> B2["PII Sensitivity Risk Scanner<br/>(Phone, Email, Citizen ID, Name)"]
        B2 --> B3[("catalog.table_profiles<br/>catalog.column_profiles")]
    end

    subgraph S3["TASK 3: Parallel Evaluation & 3-Way Dynamic Routing"]
        B3 --> PARALLEL_SPLIT{"Phân Tách Song Song"}
        
        %% Lane A
        subgraph LANE_A["Lane A: Technical Reliability Suite (L1 - L4)"]
            L1["L1: Deterministic Check<br/>(Schema, Null, Physical Bounds)"]
            L2["L2: Statistical Outlier<br/>(Median, MAD, Robust Z-Score)"]
            L3["L3: Multivariate Regression<br/>(Residual Error y = ax + b)"]
            L4["L4: Change Point Detection<br/>(CUSUM & PELT Drift Detection)"]
            L1 --> L2 --> L3 --> L4
        end
        
        %% Lane B
        subgraph LANE_B["Lane B: Hierarchical Policy Engine (7 Bước)"]
            B_STEP1["1. Phân giải Vùng (Global -> Zone -> Country)"]
            B_STEP2["2. Áp dụng Bộ Luật (Luật 91, GDPR, CCPA, IFRS 15)"]
            B_STEP3["3. Thẩm tra Tiền xử lý (Pre-check)"]
            B_STEP4["4. Xác định Xử lý (MASK, HASH, ROUND)"]
            B_STEP5["5. Thực thi qua OperationRegistry Engine"]
            B_STEP6["6. Thẩm tra Hậu xử lý (Post-check)"]
            B_STEP7["7. Phán quyết Lane B (PASS / WARN / FAIL)"]
            B_STEP1 --> B_STEP2 --> B_STEP3 --> B_STEP4 --> B_STEP5 --> B_STEP6 --> B_STEP7
        end

        PARALLEL_SPLIT --> LANE_A
        PARALLEL_SPLIT --> LANE_B

        %% Lane C
        subgraph LANE_C["Lane C: Verdict Merger & Precedence Router"]
            C1["Hội tụ Phán quyết (Matrix A/B)<br/>Quy tắc ưu tiên: FAIL > WARN > PASS"]
            C2["Bộ Định Tuyến Động"]
            C1 --> C2
        end

        LANE_A --> C1
        LANE_B --> C1

        %% 3 Làn định tuyến
        C2 -->|"Verdict: PASS"| ROUTE_SILVER[("silver.*<br/>Dữ liệu sạch, PII đã khử")]
        C2 -->|"Verdict: FAIL"| ROUTE_QUARANTINE[("quarantine.records<br/>Cách ly nguyên vẹn kèm mã Finding")]
        C2 -->|"Verdict: WARN"| ROUTE_WARNING[("warning.records<br/>Lưu trữ gắn cờ cảnh báo & che mờ PII")]
    end

    subgraph S4["TASK 4: Immutable Audit Evidence Ledger"]
        ROUTE_SILVER & ROUTE_QUARANTINE & ROUTE_WARNING --> D1["Thu thập Pipeline Run Metrics"]
        D1 --> D2["Truy vấn Previous Hash từ Sổ Cái"]
        D2 --> D3["Tính continuous SHA-256 Hash Chain<br/>Chữ ký số: SIG-AIRFLOW-3LANE-GSM-IPO-2026"]
        D3 --> D4[("audit.evidence<br/>Sổ cái Bằng chứng Bất biến")]
        D4 --> D5[("orchestration.pipeline_runs<br/>Lịch sử Run & Toàn vẹn số liệu")]
    end
```

#### Ma trận Định tuyến Lane C:
- **Silver (`silver.*`)**: Bản ghi đạt 100% tiêu chí kỹ thuật và chính sách pháp lý; Đã qua xử lý che giấu thông tin cá nhân an toàn (PII Treatment) để đưa vào phục vụ báo cáo thương mại và kế toán tài chính.
- **Quarantine (`quarantine.records`)**: Bản ghi vi phạm lỗi chặn (lỗi vật lý xe điện, gian lận doanh thu hoặc vi phạm chính sách bảo mật). Lưu trữ 100% payload gốc trong khu vực cách ly phục vụ điều tra nguyên nhân gốc rễ (RCA) mà không gây ô nhiễm kho dữ liệu sạch.
- **Warning (`warning.records`)**: Bản ghi có độ lệch thống kê nhẹ (L2-L4 drift) hoặc cảnh báo khuyến nghị. Cho phép thông qua nhưng gắn cờ giám sát và tự động che giấu PII.

---

### 3.2. SoD Flow: Kiểm soát Phân tách Trách nhiệm (RACIX)

Phân hệ **SoD Flow** cung cấp cơ chế phân tách quyền hạn tự động nhằm tuân thủ **SOX Section 404**:
- **Ngăn chặn Xung đột Quyền hạn (Conflict Detector)**: Tự động rà soát ma trận xung đột (ví dụ: Nhà phát triển phần mềm `DEV` bị cấm kiêm nhiệm quyền Deploy Production `OPS`; Người đề xuất `Maker` không được tự duyệt `Checker`).
- **Chuỗi Phê duyệt Tuần tự RACIX**:
  - **R (Responsible)**: Kiểm toán viên / Chuyên viên an ninh rà soát trước thực thi.
  - **A (Accountable)**: Quản lý trực tiếp (Line Manager) / Chủ quản hệ thống (System Owner) phê duyệt cấp 1.
  - **P (Permission/Execution)**: Quản trị viên IAM thực thi cấp quyền sau khi có đủ chữ ký hợp lệ.
  - **C (Consulted) & I (Informed)**: Tham vấn DPO/CISO và gửi thông báo kiểm toán.
  - **X (Exception)**: Ngoại lệ khẩn cấp yêu cầu sự chấp thuận của cả Admin và CISO.

---

### 3.3. Tích hợp 2 Chiều (Cross-System Integration)

DataTrust OS và SoD Flow được liên kết chặt chẽ thông qua cơ chế tích hợp 2 chiều:
1. **Từ Vi phạm sang Phiếu duyệt**: Khi DataTrust phát hiện Finding vi phạm nghiêm trọng hoặc Admin tạo đề xuất can thiệp dữ liệu cách ly (`Quarantine Override / Remediation`), hệ thống tự động sinh một Phiếu yêu cầu SoD (`sod_request_tickets`).
2. **Từ Quyết định sang Sổ cái**: Quyết định phê duyệt trong SoD Flow được ký số và ghi nhận ngược lại vào Sổ cái Bằng chứng Bất biến (`audit.evidence`) với cấu trúc **Merkle DAG SHA-256**, cho phép kiểm toán viên truy vết xuyên suốt từ dòng dữ liệu lỗi đến chữ ký của cấp có thẩm quyền.

---

### 3.4. Trợ lý AI Companion & Human-in-the-Loop (HITL)

Hệ thống tích hợp kiến trúc giao diện **Dual-Pane Global Shell** kết hợp trợ lý AI thông minh:
- **Persistent AI Panel**: Trợ lý AI luôn hiện diện bên cạnh không gian làm việc, duy trì trạng thái ngữ cảnh theo đúng lượt chạy (`run_id`) và bộ dữ liệu đang chọn.
- **Chẩn đoán RCA (Root Cause Analysis)**: Tự động phân tích các Finding lỗi phức tạp, chỉ rõ lý do vi phạm theo từng điều luật cụ thể.
- **Đề xuất Sửa đổi Quy tắc (Rule Proposal)**: Gợi ý thêm mới hoặc hiệu chỉnh biểu thức quy tắc (Rule Expression) khi phát hiện biến động dữ liệu.
- **Đề xuất Khắc phục Vi phạm (Structured Remediation Proposal)**: Sinh đề xuất xử lý dữ liệu cách ly (như Mask, Impute, Re-evaluate) và kích hoạt quy trình phê duyệt Maker-Checker 2 bước (Admin phê duyệt, Auditor thẩm tra).

---

## 💻 4. Tech Stack

### 🚀 Backend & Data Pipeline
- **Ngôn ngữ**: Python 3.10+ / 3.14
- **API Framework**: [FastAPI](https://fastapi.tiangolo.com) (RESTful APIs, WebSockets, OpenAPI docs)
- **ASGI Server**: [Uvicorn](https://www.uvicorn.org)
- **Data Pipeline & Orchestration**: [Apache Airflow 2.5+](https://airflow.apache.org) (CeleryExecutor, Triggerer, Flower), [Redis](https://redis.io)
- **Xử lý Dữ liệu**: [Pandas](https://pandas.pydata.org), [NumPy](https://numpy.org), [PyArrow](https://arrow.apache.org/docs/python/), [Scikit-learn](https://scikit-learn.org)
- **AI & Agentic Orchestration**: [LangChain](https://www.langchain.com), [LangGraph](https://langchain-ai.github.io/langgraph/), `langchain-openai` (GPT-4o-mini)
- **Cơ sở Dữ liệu**: [PostgreSQL 13 / 16](https://www.postgresql.org) (Multi-Schema: `bronze`, `silver`, `quarantine`, `warning`, `catalog`, `compliance`, `orchestration`, `audit`, `sod`)
- **Bảo mật & Giám sát**: PyJWT, Sentry SDK, HMAC-SHA256 Keyed Hashing

### 🎨 Frontend
- **Framework**: [React 19](https://react.dev) + [TypeScript](https://www.typescriptlang.org)
- **Build Tool**: [Vite 8](https://vitejs.dev)
- **Styling**: [TailwindCSS v4](https://tailwindcss.com) + Framer Motion (Transitions & Micro-interactions)
- **State Management**: [Zustand](https://github.com/pmndrs/zustand)
- **Routing**: [React Router DOM v7](https://reactrouter.com)
- **Biểu đồ & Trực quan hóa**: [Recharts](https://recharts.org), [Chart.js](https://www.chartjs.org)
- **Icons & UI Utilities**: [Lucide React](https://lucide.dev), Marked, i18next (Đa ngôn ngữ: Tiếng Việt / Tiếng Anh)
- **Kiểm thử**: [Vitest](https://vitest.dev), Testing Library, JSDOM

---

## 📁 5. Cấu trúc Thư mục Dự án

```text
Phase2_VSF/
├── .agents/                        # Kỹ năng định nghĩa Agent (Audit, Design, Multi-agent build)
├── backend/                        # Nguồn Backend FastAPI & AI Engine
│   ├── ai/                         # LangChain/LangGraph Agents, Tools & Proposers
│   ├── api/                        # REST API Routes (main.py, auth_routes.py, sod_routes.py)
│   ├── audit/                      # Cryptographic Hash Chaining & Merkle DAG Evidence
│   ├── database/                   # Pydantic & SQLAlchemy Models
│   ├── engine/                     # Compliance Evaluator, Precedence Router, OperationRegistry
│   ├── lineage/                    # Data Lineage Tracking & Schema Diff Service
│   └── sod/                        # Segregation of Duties Engine, Conflict Detector & Catalog
├── dags/                           # Apache Airflow DAGs & Data Engines
│   ├── datatrust_adaptive_pipeline_dag.py # DAG chính điều phối Pipeline 4 Tasks
│   ├── parallel_evaluation_engine.py      # Bộ máy đánh giá song song Lane A & Lane B
│   ├── profiler_engine.py                 # Engine thống kê dữ liệu & quét rủi ro PII
│   └── reset_and_ingest_bronze.py         # Nạp dữ liệu thô vào schema Bronze
├── data/                           # Dữ liệu mẫu CSV 3 Vùng (VN, EU, US)
├── database/                       # Kiến trúc CSDL & Migrations PostgreSQL
│   ├── init_db.py                  # Script khởi tạo toàn bộ CSDL và schema ban đầu
│   ├── run_migrations.py           # Bộ chạy migration tăng tiến bảo toàn dữ liệu
│   ├── reset_and_ingest_bronze.py  # Script làm mới và nạp dữ liệu thô Bronze
│   ├── seed_sod_demo.py            # Dữ liệu demo cho phân hệ SoD Flow
│   ├── seed_data.sql               # Seed data quy chuẩn ban đầu
│   └── migration_*.sql             # Các tệp SQL migration tăng tiến theo phiên bản
├── docs/                           # Tài liệu thiết kế chi tiết & đặc tả hệ thống
├── frontend/                       # Ứng dụng Giao diện React 19 + TypeScript + Vite
│   ├── src/
│   │   ├── components/             # Components UI (DataTrust shell, SoD, Auth, Findings)
│   │   ├── stores/                 # Zustand Stores (AuthStore, AgentStore, PipelineStore)
│   │   ├── types/                  # TypeScript Types & Interfaces
│   │   ├── i18n/                   # Cấu hình đa ngôn ngữ (VI / EN)
│   │   └── App.tsx                 # Định tuyến ứng dụng và AuthGuard
│   ├── package.json
│   └── vite.config.ts
├── infrastructure/                 # Hạ tầng Cloud, Docker & cấu hình môi trường
├── scripts/                        # Scripts tự động hóa và Shell Deploy
├── tests/                          # Bộ kiểm thử tự động toàn diện (>40 test suites)
├── .env.example                    # Tệp mẫu biến môi trường
├── admin_handbook_datatrust_os.md  # Cẩm nang Quản trị Hệ thống
├── docker-compose.yml              # Cấu hình Docker Compose (Airflow, Postgres, Redis)
├── Dockerfile.airflow              # Dockerfile mở rộng cho Apache Airflow
├── HDSD.md                         # Cẩm nang Hướng dẫn Sử dụng Chi tiết
├── KE_HOACH_SOD_DATATRUST.md       # Đặc tả Kế hoạch Tích hợp SoD & DataTrust
├── PIPELINE_ARCHITECTURE.md        # Tài liệu Kỹ thuật Kiến trúc Pipeline
└── requirements.txt                # Danh mục thư viện Python dependencies
```

---

## 🚀 6. Hướng dẫn Cài đặt & Khởi chạy Nhanh

### 6.1. Yêu cầu Hệ thống
- **Hệ điều hành**: Linux, macOS, hoặc Windows (khuyến nghị WSL2 nếu dùng Windows).
- **Python**: Phiên bản 3.10 trở lên (khuyến nghị 3.11 hoặc 3.12).
- **Node.js**: Phiên bản 20.x trở lên & package manager `npm` hoặc `pnpm`.
- **Docker & Docker Compose**: Dung lượng RAM tối thiểu 4GB (khuyến nghị 8GB cho Airflow).
- **Git**: Quản lý phiên bản mã nguồn.

---

### 6.2. Cấu hình Môi trường (.env)

Sao chép tệp mẫu `.env.example` thành `.env` tại thư mục gốc:

```bash
cp .env.example .env
```

Cập nhật các giá trị cấu hình cần thiết:

```ini
# ---- AI & LLM Provider ----
OPENAI_API_KEY=your-openai-api-key-here
LLM_PROVIDER=openai
OPENAI_MODEL=gpt-4o-mini

# ---- Database ----
DATABASE_URL=postgresql://airflow:airflow@localhost:5432/airflow
AIRFLOW_UID=0

# ---- Lane B Cryptographic Key (HMAC-SHA256 Pseudonymization) ----
DATATRUST_PSEUDONYMIZATION_KEY=datatrust-secret-salt-key-gsm-ipo-2026
```

---

### 6.3. Khởi tạo Cơ sở Dữ liệu & Seed Data

1. **Khởi động dịch vụ Cơ sở dữ liệu và Message Broker**:
   ```bash
   docker-compose up -d postgres redis
   ```

2. **Khởi tạo môi trường ảo Python & cài đặt thư viện**:
   ```bash
   python -m venv .venv
   # Kích hoạt trên Windows:
   .venv\Scripts\activate
   # Hoặc trên Linux/macOS:
   source .venv/bin/activate

   pip install -r requirements.txt
   ```

3. **Khởi tạo CSDL, Schemas và nạp dữ liệu chuẩn**:
   ```bash
   # Khởi tạo toàn bộ schemas và cấu hình quy tắc
   python database/init_db.py

   # Nạp dữ liệu thô vào các bảng Bronze (8 bộ dữ liệu mẫu)
   python database/reset_and_ingest_bronze.py

   # Nạp dữ liệu mẫu cho phân hệ Phân tách trách nhiệm (SoD Flow)
   python database/seed_sod_demo.py
   ```

> [!TIP]
> **Nâng cấp CSDL không mất dữ liệu**: Khi cập nhật mã nguồn mới trong môi trường đã có dữ liệu, hãy chạy `python database/run_migrations.py` thay vì `init_db.py`.

---

### 6.4. Khởi chạy Ứng dụng

#### Cách 1: Khởi chạy Cục bộ cho Lập trình viên (Recommended)

Mở 3 cửa sổ terminal riêng biệt:

**Terminal 1 — Backend FastAPI**:
```bash
# Kích hoạt venv trước
uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --reload
```
*API Docs (Swagger UI) khả dụng tại:* `http://localhost:8000/docs`

**Terminal 2 — Frontend React**:
```bash
cd frontend
npm install
npm run dev
```
*Giao diện Web khả dụng tại:* `http://localhost:5173`

**Terminal 3 — Apache Airflow (Pipeline Orchestrator)**:
```bash
docker-compose up -d
```
*Airflow Web UI khả dụng tại:* `http://localhost:8080` *(Tài khoản: `airflow` / `airflow`)*

---

#### Cách 2: Khởi chạy Toàn bộ với Docker Compose

```bash
docker-compose --profile flower up -d
```

Các dịch vụ sẽ sẵn sàng:
- **FastAPI Backend**: `http://localhost:8000`
- **Airflow Webserver**: `http://localhost:8080`
- **Celery Flower (Giám sát Tasks)**: `http://localhost:5555`
- **PostgreSQL**: `localhost:5432`

---

## 👥 7. Tài khoản Demo & Ma trận Phân quyền (RBAC)

Hệ thống tích hợp Cổng Đăng nhập Hợp nhất (`/login`) với **14 Personas** mẫu đại diện cho 3 nhóm thẩm quyền truy cập:

```mermaid
flowchart TD
    Login["Cổng Đăng nhập Tập trung (/login)"] --> Check{"Xác thực & Thẩm quyền Roles"}
    
    Check -->|sod_only| SoDStandalone["SoD Standalone Workspace (/sod)<br/>(Chặn truy cập DataTrust)"]
    Check -->|datatrust_only| DTStandard["DataTrust OS Shell (/overview)<br/>(3 Tabs tiêu chuẩn - Ẩn Tab SoD)"]
    Check -->|both| DTIntegrated["DataTrust OS Shell (/overview)<br/>(Kích hoạt Tab thứ 4: Phân quyền & SoD)"]
```

| STT | Username Mẫu | Tên Persona Mẫu | Mã Vai trò | Nhóm Quyền | Phạm vi Thẩm quyền & Trang đích |
| :---: | :--- | :--- | :---: | :---: | :--- |
| **I** | **NHÓM CẢ HAI HỆ THỐNG (BOTH)** | | | | |
| 1 | `admin` | Nguyễn Quốc Bảo | `ADMIN` | `both` | Toàn quyền Quản trị DataTrust OS & Đề xuất Ma trận SoD (`/overview` + Tab SoD) |
| 2 | `auditor` | Trần Minh Hoàng | `AUDITOR` | `both` | Thẩm tra độc lập, kích hoạt Audit Run, kiểm tra Sổ cái Merkle SHA-256 |
| 3 | `dpo` | Lê Chi | `DPO` | `both` | Duyệt Maker-Checker PII (GDPR Art 6, NĐ 356) & ngoại lệ bảo mật SoD |
| 4 | `so` | Hồ Sơn | `SO` | `both` | Chủ quản hệ thống nghiệp vụ (System Owner), duyệt quy tắc dữ liệu |
| **II** | **NHÓM CHỈ SOD FLOW (SOD ONLY)** | | | | |
| 5 | `an.nguyen` | Nguyễn An | `REQ` | `sod_only` | Khởi tạo phiếu xin cấp quyền & ngoại lệ kiểm soát (`/sod`) |
| 6 | `binh.tran` | Trần Bình | `LM` | `sod_only` | Phê duyệt bước 1 (Line Manager - Quản lý trực tiếp) (`/sod`) |
| 7 | `ha.vu` | Vũ Hà | `IAM` | `sod_only` | Thực thi cấp/thu hồi quyền trên IAM/PAM sau khi phiếu đủ chữ ký (`/sod`) |
| 8 | `khoa.do` | Đỗ Khoa | `DEV` | `sod_only` | Kỹ sư phát triển (Bị chặn tự duyệt phát hành Prod) (`/sod`) |
| 9 | `lan.bui` | Bùi Lan | `REL` | `sod_only` | Quản lý phát hành (Release Manager), duyệt release Prod (`/sod`) |
| 10 | `minh.ngo` | Ngô Minh | `OPS` | `sod_only` | Kỹ sư vận hành (Chỉ deploy khi có phê duyệt của Release Manager) (`/sod`) |
| 11 | `giang.hoang` | Hoàng Giang | `CISO` | `sod_only` | Giám đốc An ninh Thông tin, duyệt ma trận SoD và ngoại lệ Level 3 (`/sod`) |
| **III** | **NHÓM CHỈ DATATRUST OS (DATATRUST ONLY)** | | | | |
| 12 | `steward.le` | Lê Nam | `DATA_STEWARD` | `datatrust_only` | Quản trị dữ liệu, duyệt Quality Rules, xử lý Quarantine (`/overview`) |
| 13 | `analyst.vu` | Vũ Mai | `ANALYST` | `datatrust_only` | Khảo sát dữ liệu, phân tích RCA, đề xuất quy tắc (`/overview`) |
| 14 | `viewer.tran` | Trần Đức | `VIEWER` | `datatrust_only` | Xem Dashboard tổng quan, KPI chất lượng dữ liệu (Read-only) (`/overview`) |

> [!NOTE]
> Mật khẩu mặc định cho tất cả các tài khoản demo trên môi trường phát triển là: `password` hoặc đăng nhập nhanh 1-click qua giao diện Persona selector tại `/login`.

---

## 🧪 8. Kiểm thử Tự động (Testing Suite)

Dự án sở hữu bộ kiểm thử tự động toàn diện với hơn 40 test suites bao quát từ cấp độ đơn vị (Unit Tests), tích hợp (Integration Tests), đến kiểm thử hợp đồng (Contract Tests):

### 🐍 Chạy Backend Tests (Pytest)
```bash
# Chạy toàn bộ bộ kiểm thử backend
pytest

# Chạy kiểm tra riêng cho từng làn đánh giá
pytest tests/test_lane_a_production_rules.py
pytest tests/test_lane_b_16_operational_runs.py
pytest tests/test_lane_c_optimization.py

# Chạy kiểm thử Sổ cái Bất biến Merkle DAG & Evidence
pytest tests/test_cryptographic_audit_merkle.py

# Chạy kiểm thử phân hệ SoD & Tích hợp 2 chiều
pytest tests/test_sod_backend.py
pytest tests/test_sod_phase3_integration.py
```

### ⚛️ Chạy Frontend Tests (Vitest)
```bash
cd frontend
npm test
```

---

## 🚢 9. Hướng dẫn Triển khai (Deployment)

### 9.1. Triển khai trên AWS (ECS / RDS / S3 / SSM)
Thư mục `scripts/deploy_aws.sh` và `docker-compose.aws.yml` hỗ trợ đóng gói và triển khai tự động lên hạ tầng đám mây AWS:
- **Cơ sở dữ liệu**: AWS RDS PostgreSQL 16 (Multi-AZ).
- **Lưu trữ Bằng chứng Kiểm toán**: AWS S3 Bucket với chính sách khóa Object Lock (WORM - Write Once, Read Many).
- **Quản lý Khóa Bí mật**: AWS Systems Manager (SSM) Parameter Store cho `DATATRUST_PSEUDONYMIZATION_KEY` và API Keys.

### 9.2. Triển khai trên Render / PaaS
Tệp `render.yaml` định cấu hình sẵn sàng cho mô hình triển khai Microservices trên Render bao gồm Web Service (FastAPI) và Static Site (React/Vite).

---

## 📚 10. Tài liệu Liên quan

Để tìm hiểu sâu hơn về từng nghiệp vụ và khía cạnh kỹ thuật, vui lòng tham khảo các tài liệu chuyên đề:
- 📖 [Cẩm nang Hướng dẫn Sử dụng Chi tiết (HDSD.md)](file:///E:/Phase2_VSF/HDSD.md): Hướng dẫn thao tác màn hình, khởi chạy Run, đọc kết quả, duyệt HITL Remediation và khai thác AI Companion.
- 🏛️ [Tài liệu Kiến trúc Kỹ thuật Pipeline (PIPELINE_ARCHITECTURE.md)](file:///E:/Phase2_VSF/PIPELINE_ARCHITECTURE.md): Chi tiết 4 tầng Lane A (L1-L4), 7 bước Lane B, ma trận phân giải Lane C và cấu trúc băm SHA-256 Ledger.
- ⚖️ [Kế hoạch Tích hợp SoD & DataTrust (KE_HOACH_SOD_DATATRUST.md)](file:///E:/Phase2_VSF/KE_HOACH_SOD_DATATRUST.md): Lộ trình 3 Phase tích hợp SoD Flow, ma trận xung đột và chuỗi duyệt RACIX.
- 📋 [Cẩm nang Dành cho Quản trị viên (admin_handbook_datatrust_os.md)](file:///E:/Phase2_VSF/admin_handbook_datatrust_os.md): Hướng dẫn xử lý sự cố, cấu hình quyền và vận hành hệ thống cấp cao.

---

<p align="center">
  <b>DataTrust OS & SoD Flow — Built for Enterprise Data Assurance & IPO Readiness</b><br/>
  <i>Copyright © 2026 VinFast / GSM Global Data Platform Team. All rights reserved.</i>
</p>
