"""
DataTrust OS: 3-Zone Pilot Ingestion & Catalog Mapping Module
Loads and catalogs datasets from data/vingroup_clean_3zone_pilot:
- ride_hailing_xanh_sm_trips.csv (10,382 trips across EU, VN, US)
- synthetic_ev_telemetry_ved_ref.csv (86,400 telemetries, 60 VINs)
- acn_charging_mapped.csv (1,331 charging sessions)
- nlp_benchmark_uit_vsfc.csv (500 user feedbacks)
- fleet_index.csv (60 pilot vehicles)
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Tuple
import pandas as pd

from backend.database.models import (
    DatasetModel,
    ColumnModel,
    CompliancePolicyModel,
    PolicyClauseModel,
    PiiRoleType,
    TreatmentActionType,
    FieldProcessConfigModel,
    ComplianceCheckRuleModel,
    DataTreatmentRuleModel,
    ExecutionPhase,
    RuleSeverity,
    UserRole
)
from backend.engine.dynamic_runner import DynamicRuleRunner
from backend.engine.quarantine_manager import QuarantineManager
from backend.ai.policy_rule_proposer import PolicyRuleProposerAgent


PILOT_DATA_DIR = Path("data/vingroup_clean_3zone_pilot")
if not PILOT_DATA_DIR.exists():
    PILOT_DATA_DIR = Path("data/vingroup_pii_faulty_testset_3zone")


# =============================================================================
# 1. CATALOG SPECIFICATION FOR 3-ZONE PILOT
# =============================================================================

class DatasetDict(dict):
    """
    Dictionary hỗ trợ truy vấn bằng tên file dữ liệu (.csv) làm khóa chính,
    đồng thời hỗ trợ tra cứu tương thích ngược qua alias (trips, telemetry, v.v.).
    """
    ALIASES = {
        "trips": "ride_hailing_xanh_sm_trips.csv",
        "ride_hailing_xanh_sm_trips": "ride_hailing_xanh_sm_trips.csv",
        "telemetry": "synthetic_ev_telemetry_ved_ref.csv",
        "synthetic_ev_telemetry_ved_ref": "synthetic_ev_telemetry_ved_ref.csv",
        "charging": "acn_charging_mapped.csv",
        "acn_charging_mapped": "acn_charging_mapped.csv",
        "nlp_feedback": "nlp_benchmark_uit_vsfc.csv",
        "nlp_benchmark_uit_vsfc": "nlp_benchmark_uit_vsfc.csv",
        "fleet": "fleet_index.csv",
        "fleet_index": "fleet_index.csv",
    }
    def __getitem__(self, key):
        actual_key = self.ALIASES.get(key, key)
        return super().__getitem__(actual_key)
    def get(self, key, default=None):
        actual_key = self.ALIASES.get(key, key)
        return super().get(actual_key, default)
    def __contains__(self, key):
        actual_key = self.ALIASES.get(key, key)
        return super().__contains__(actual_key)


def get_3zone_datasets() -> Dict[str, DatasetModel]:
    datasets = DatasetDict({
        "ride_hailing_xanh_sm_trips.csv": DatasetModel(
            dataset_id="ride_hailing_xanh_sm_trips.csv",
            name="ride_hailing_xanh_sm_trips.csv",
            title="ride_hailing_xanh_sm_trips.csv",
            domain="trips",
            owner_dept="Khối Vận Hành GSM Toàn Cầu",
            storage_table_bronze="bronze.trips_raw",
            storage_table_silver="silver.trips_clean",
            description="10,382 cuốc xe taxi điện VinFast phân bổ qua 3 phân vùng EU (Berlin), VN (Hà Nội), US (New York)",
            retention_days=1825
        ),
        "synthetic_ev_telemetry_ved_ref.csv": DatasetModel(
            dataset_id="synthetic_ev_telemetry_ved_ref.csv",
            name="synthetic_ev_telemetry_ved_ref.csv",
            title="synthetic_ev_telemetry_ved_ref.csv",
            domain="telemetry",
            owner_dept="Khối R&D Phần Mềm Xe Điện VinFast",
            storage_table_bronze="bronze.telemetry_raw",
            storage_table_silver="silver.telemetry_clean",
            description="86,400 bản ghi telemetry cảm biến pin (SOC, nhiệt độ, điện áp, dòng xả) từ 60 xe pilot trong 15 ngày",
            retention_days=730
        ),
        "acn_charging_mapped.csv": DatasetModel(
            dataset_id="acn_charging_mapped.csv",
            name="acn_charging_mapped.csv",
            title="acn_charging_mapped.csv",
            domain="charging",
            owner_dept="Công Ty Cổ Phần Phát Triển Trạm Sạc Toàn Cầu V-GREEN",
            storage_table_bronze="bronze.charging_raw",
            storage_table_silver="silver.charging_clean",
            description="1,331 phiên sạc xe điện với thông số công suất kW, sản lượng kWh tiêu thụ và chi phí",
            retention_days=1825
        ),
        "nlp_benchmark_uit_vsfc.csv": DatasetModel(
            dataset_id="nlp_benchmark_uit_vsfc.csv",
            name="nlp_benchmark_uit_vsfc.csv",
            title="nlp_benchmark_uit_vsfc.csv",
            domain="nlp_feedback",
            owner_dept="Trung Tâm Trải Nghiệm Khách Hàng & CSKH",
            storage_table_bronze="bronze.feedback_raw",
            storage_table_silver="silver.feedback_clean",
            description="500 phản hồi văn bản tự do của khách hàng về chất lượng cuốc xe và trạm sạc V-GREEN",
            retention_days=365
        ),
        "fleet_index.csv": DatasetModel(
            dataset_id="fleet_index.csv",
            name="fleet_index.csv",
            title="fleet_index.csv",
            domain="fleet",
            owner_dept="Quản Lý Đội Xe GSM Global",
            storage_table_bronze="bronze.fleet_raw",
            storage_table_silver="silver.fleet_clean",
            description="60 xe điện VinFast chia đều cho 3 phân vùng VN (Hà Nội: 20 xe), EU (Berlin: 20 xe), US (New York: 20 xe)",
            retention_days=3650
        )
    })
    return datasets


def get_3zone_columns() -> Dict[str, List[ColumnModel]]:
    base_cols = DatasetDict({
        "ride_hailing_xanh_sm_trips.csv": [
            ColumnModel(dataset_id="ride_hailing_xanh_sm_trips.csv", column_name="trip_id", data_type="VARCHAR(50)", is_primary_key=True, pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="ride_hailing_xanh_sm_trips.csv", column_name="vehicle_vin", data_type="VARCHAR(50)", is_personal_data=True, pii_role=PiiRoleType.LINKABLE_IDENTIFIER, default_treatment=TreatmentActionType.KEEP_RESTRICTED, semantic_tag="vehicle_identifier"),
            ColumnModel(dataset_id="ride_hailing_xanh_sm_trips.csv", column_name="driver_id", data_type="VARCHAR(50)", is_personal_data=True, pii_role=PiiRoleType.LINKABLE_IDENTIFIER, default_treatment=TreatmentActionType.PSEUDONYMIZE, semantic_tag="driver_identifier"),
            ColumnModel(dataset_id="ride_hailing_xanh_sm_trips.csv", column_name="pickup_datetime", data_type="TIMESTAMPTZ", pii_role=PiiRoleType.TECHNICAL_METADATA, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="ride_hailing_xanh_sm_trips.csv", column_name="dropoff_datetime", data_type="TIMESTAMPTZ", pii_role=PiiRoleType.TECHNICAL_METADATA, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="ride_hailing_xanh_sm_trips.csv", column_name="trip_distance_km", data_type="NUMERIC(8,3)", pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP, semantic_tag="distance_metric"),
            ColumnModel(dataset_id="ride_hailing_xanh_sm_trips.csv", column_name="fare_amount", data_type="NUMERIC(12,2)", pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP, semantic_tag="financial_fare"),
            ColumnModel(dataset_id="ride_hailing_xanh_sm_trips.csv", column_name="tip_amount", data_type="NUMERIC(12,2)", pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="ride_hailing_xanh_sm_trips.csv", column_name="total_fare", data_type="NUMERIC(12,2)", pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="ride_hailing_xanh_sm_trips.csv", column_name="pickup_latitude", data_type="NUMERIC(9,6)", is_personal_data=True, pii_role=PiiRoleType.CONTEXTUAL_PERSONAL_DATA, default_treatment=TreatmentActionType.GENERALIZE, semantic_tag="gps_latitude"),
            ColumnModel(dataset_id="ride_hailing_xanh_sm_trips.csv", column_name="pickup_longitude", data_type="NUMERIC(9,6)", is_personal_data=True, pii_role=PiiRoleType.CONTEXTUAL_PERSONAL_DATA, default_treatment=TreatmentActionType.GENERALIZE, semantic_tag="gps_longitude"),
            ColumnModel(dataset_id="ride_hailing_xanh_sm_trips.csv", column_name="vehicle_type", data_type="VARCHAR(50)", pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="ride_hailing_xanh_sm_trips.csv", column_name="subject_zone", data_type="VARCHAR(10)", pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP, semantic_tag="regulatory_jurisdiction")
        ],
        "synthetic_ev_telemetry_ved_ref.csv": [
            ColumnModel(dataset_id="synthetic_ev_telemetry_ved_ref.csv", column_name="record_id", data_type="VARCHAR(50)", is_primary_key=True, pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="synthetic_ev_telemetry_ved_ref.csv", column_name="vehicle_vin", data_type="VARCHAR(50)", is_personal_data=True, pii_role=PiiRoleType.LINKABLE_IDENTIFIER, default_treatment=TreatmentActionType.KEEP_RESTRICTED),
            ColumnModel(dataset_id="synthetic_ev_telemetry_ved_ref.csv", column_name="timestamp", data_type="TIMESTAMPTZ", pii_role=PiiRoleType.TECHNICAL_METADATA, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="synthetic_ev_telemetry_ved_ref.csv", column_name="speed_kmh", data_type="NUMERIC(6,2)", pii_role=PiiRoleType.TECHNICAL_METADATA, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="synthetic_ev_telemetry_ved_ref.csv", column_name="motor_rpm", data_type="INT", pii_role=PiiRoleType.TECHNICAL_METADATA, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="synthetic_ev_telemetry_ved_ref.csv", column_name="battery_soc", data_type="NUMERIC(5,2)", pii_role=PiiRoleType.TECHNICAL_METADATA, default_treatment=TreatmentActionType.KEEP, semantic_tag="battery_state_of_charge"),
            ColumnModel(dataset_id="synthetic_ev_telemetry_ved_ref.csv", column_name="battery_voltage", data_type="NUMERIC(6,2)", pii_role=PiiRoleType.TECHNICAL_METADATA, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="synthetic_ev_telemetry_ved_ref.csv", column_name="battery_current", data_type="NUMERIC(6,2)", pii_role=PiiRoleType.TECHNICAL_METADATA, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="synthetic_ev_telemetry_ved_ref.csv", column_name="battery_temp_c", data_type="NUMERIC(5,2)", pii_role=PiiRoleType.TECHNICAL_METADATA, default_treatment=TreatmentActionType.KEEP, semantic_tag="battery_temperature_celsius"),
            ColumnModel(dataset_id="synthetic_ev_telemetry_ved_ref.csv", column_name="latitude", data_type="NUMERIC(9,6)", is_personal_data=True, pii_role=PiiRoleType.CONTEXTUAL_PERSONAL_DATA, default_treatment=TreatmentActionType.GENERALIZE),
            ColumnModel(dataset_id="synthetic_ev_telemetry_ved_ref.csv", column_name="longitude", data_type="NUMERIC(9,6)", is_personal_data=True, pii_role=PiiRoleType.CONTEXTUAL_PERSONAL_DATA, default_treatment=TreatmentActionType.GENERALIZE),
            ColumnModel(dataset_id="synthetic_ev_telemetry_ved_ref.csv", column_name="subject_zone", data_type="VARCHAR(10)", pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP)
        ],
        "acn_charging_mapped.csv": [
            ColumnModel(dataset_id="acn_charging_mapped.csv", column_name="session_id", data_type="VARCHAR(100)", is_primary_key=True, pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="acn_charging_mapped.csv", column_name="vehicle_vin", data_type="VARCHAR(50)", is_personal_data=True, pii_role=PiiRoleType.LINKABLE_IDENTIFIER, default_treatment=TreatmentActionType.KEEP_RESTRICTED),
            ColumnModel(dataset_id="acn_charging_mapped.csv", column_name="station_id", data_type="VARCHAR(50)", pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="acn_charging_mapped.csv", column_name="start_time", data_type="TIMESTAMPTZ", pii_role=PiiRoleType.TECHNICAL_METADATA, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="acn_charging_mapped.csv", column_name="duration_mins", data_type="NUMERIC(8,2)", pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="acn_charging_mapped.csv", column_name="kwh_consumed", data_type="NUMERIC(8,2)", pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="acn_charging_mapped.csv", column_name="power_kw", data_type="NUMERIC(6,2)", pii_role=PiiRoleType.TECHNICAL_METADATA, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="acn_charging_mapped.csv", column_name="station_temp_c", data_type="NUMERIC(5,2)", pii_role=PiiRoleType.TECHNICAL_METADATA, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="acn_charging_mapped.csv", column_name="cost_vnd", data_type="NUMERIC(12,2)", pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="acn_charging_mapped.csv", column_name="subject_zone", data_type="VARCHAR(10)", pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP)
        ],
        "nlp_benchmark_uit_vsfc.csv": [
            ColumnModel(dataset_id="nlp_benchmark_uit_vsfc.csv", column_name="sentence", data_type="TEXT", is_personal_data=True, pii_role=PiiRoleType.AMBIGUOUS_UNSTRUCTURED_DATA, default_treatment=TreatmentActionType.PSEUDONYMIZE, semantic_tag="free_text_review"),
            ColumnModel(dataset_id="nlp_benchmark_uit_vsfc.csv", column_name="sentiment", data_type="INT", pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="nlp_benchmark_uit_vsfc.csv", column_name="topic", data_type="INT", pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP)
        ],
        "fleet_index.csv": [
            ColumnModel(dataset_id="fleet_index.csv", column_name="vehicle_vin", data_type="VARCHAR(50)", is_primary_key=True, pii_role=PiiRoleType.LINKABLE_IDENTIFIER, default_treatment=TreatmentActionType.KEEP_RESTRICTED, semantic_tag="vehicle_identifier"),
            ColumnModel(dataset_id="fleet_index.csv", column_name="vehicle_type", data_type="VARCHAR(50)", pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="fleet_index.csv", column_name="telemetry_equipped", data_type="BOOLEAN", pii_role=PiiRoleType.TECHNICAL_METADATA, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="fleet_index.csv", column_name="subject_zone", data_type="VARCHAR(10)", pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP)
        ]
    })
    return base_cols


DATASET_FILE_MAP = {
    "trips": "ride_hailing_xanh_sm_trips.csv",
    "ride_hailing_xanh_sm_trips": "ride_hailing_xanh_sm_trips.csv",
    "ride_hailing_xanh_sm_trips.csv": "ride_hailing_xanh_sm_trips.csv",
    "telemetry": "synthetic_ev_telemetry_ved_ref.csv",
    "synthetic_ev_telemetry_ved_ref": "synthetic_ev_telemetry_ved_ref.csv",
    "synthetic_ev_telemetry_ved_ref.csv": "synthetic_ev_telemetry_ved_ref.csv",
    "charging": "acn_charging_mapped.csv",
    "acn_charging_mapped": "acn_charging_mapped.csv",
    "acn_charging_mapped.csv": "acn_charging_mapped.csv",
    "nlp_feedback": "nlp_benchmark_uit_vsfc.csv",
    "nlp_benchmark_uit_vsfc": "nlp_benchmark_uit_vsfc.csv",
    "nlp_benchmark_uit_vsfc.csv": "nlp_benchmark_uit_vsfc.csv",
    "fleet": "fleet_index.csv",
    "fleet_index": "fleet_index.csv",
    "fleet_index.csv": "fleet_index.csv",
}


def resolve_csv_path(filename_or_id: str) -> Path:
    fname = DATASET_FILE_MAP.get(filename_or_id, filename_or_id)
    if not fname.endswith(".csv"):
        fname += ".csv"
    candidates = [
        PILOT_DATA_DIR / fname,
        Path("data/vingroup_clean_3zone_pilot") / fname,
        Path("../data/vingroup_clean_3zone_pilot") / fname
    ]
    for c in candidates:
        if c.exists():
            return c
    return PILOT_DATA_DIR / fname


def get_dataset_preview(dataset_id: str, limit: int = 20) -> Dict[str, Any]:
    file_path = resolve_csv_path(dataset_id)
    if not file_path.exists():
        return {
            "dataset_id": dataset_id,
            "filename": file_path.name,
            "columns": [],
            "rows": [],
            "total_records": 0,
            "error": "File not found"
        }
    df = pd.read_csv(file_path, nrows=limit)
    df = df.where(pd.notnull(df), None)
    total_records = sum(1 for _ in open(file_path, encoding="utf-8")) - 1
    return {
        "dataset_id": dataset_id,
        "filename": file_path.name,
        "columns": list(df.columns),
        "rows": df.to_dict(orient="records"),
        "total_records": total_records,
        "limit": limit
    }


def get_dataset_stats(dataset_id: str) -> Dict[str, Any]:
    file_path = resolve_csv_path(dataset_id)
    if not file_path.exists():
        return {"dataset_id": dataset_id, "filename": file_path.name, "error": "File not found"}
    df_sample = pd.read_csv(file_path, nrows=1000)
    total_records = sum(1 for _ in open(file_path, encoding="utf-8")) - 1
    
    zone_distribution = {}
    if "subject_zone" in df_sample.columns:
        df_zones = pd.read_csv(file_path, usecols=["subject_zone"])
        zone_distribution = {k: int(v) for k, v in df_zones["subject_zone"].value_counts().to_dict().items()}
    
    return {
        "dataset_id": dataset_id,
        "filename": file_path.name,
        "total_records": total_records,
        "columns_count": len(df_sample.columns),
        "columns": list(df_sample.columns),
        "zone_distribution": zone_distribution
    }


# =============================================================================
# 2. MULTI-ZONE POLICY PACK DEFINITION
# =============================================================================

def get_3zone_policies() -> Dict[str, CompliancePolicyModel]:
    policies = {
        "POL-EU-GDPR": CompliancePolicyModel(
            policy_id="POL-EU-GDPR",
            title="EU GDPR Regulation (EU) 2016/679 - Phân Vùng Châu Âu",
            jurisdiction="EU",
            legal_framework="GDPR Regulation (EU) 2016/679",
            raw_policy_text="Áp dụng cho đội xe và cuốc xe vùng EU (Berlin: lat 52.45-52.55, lon 13.3-13.45). Bắt buộc bí danh hóa Driver ID, làm mờ tọa độ GPS và bảo vệ quyền riêng tư mặc định.",
            effective_date="2018-05-25",
            clauses=[
                PolicyClauseModel(clause_id="C-EU-01", policy_id="POL-EU-GDPR", clause_number="Article 5.1(c)", requirement_summary="Tối thiểu hóa dữ liệu và bí danh hóa định danh lái xe", target_pii_roles=[PiiRoleType.LINKABLE_IDENTIFIER], mandated_action=TreatmentActionType.PSEUDONYMIZE),
                PolicyClauseModel(clause_id="C-EU-02", policy_id="POL-EU-GDPR", clause_number="Article 25", requirement_summary="Làm mờ tọa độ GPS đón khách xuống độ phân giải 2 chữ số thập phân", target_pii_roles=[PiiRoleType.CONTEXTUAL_PERSONAL_DATA], mandated_action=TreatmentActionType.GENERALIZE)
            ]
        ),
        "POL-VN-LAW91": CompliancePolicyModel(
            policy_id="POL-VN-LAW91",
            title="Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15 & Nghị định 356/2025/NĐ-CP",
            jurisdiction="VN",
            legal_framework="Luật 91/2025/QH15 & Nghị định 356/2025/NĐ-CP",
            raw_policy_text="Áp dụng cho đội xe và cuốc xe vùng Việt Nam (hiệu lực từ 01/01/2026). Yêu cầu bắt buộc che giấu định danh trực tiếp (SĐT, Email, CCCD) và làm mờ tọa độ di chuyển.",
            effective_date="2026-01-01",
            clauses=[
                PolicyClauseModel(clause_id="C-VN-01", policy_id="POL-VN-LAW91", clause_number="Điều 17 & NĐ 356", requirement_summary="Che mờ hoặc bí danh hóa dữ liệu cá nhân liên lạc", target_pii_roles=[PiiRoleType.DIRECT_IDENTIFIER], mandated_action=TreatmentActionType.PSEUDONYMIZE),
                PolicyClauseModel(clause_id="C-VN-02", policy_id="POL-VN-LAW91", clause_number="Điều 13 & NĐ 356", requirement_summary="Làm mờ vị trí đón trả khách", target_pii_roles=[PiiRoleType.CONTEXTUAL_PERSONAL_DATA], mandated_action=TreatmentActionType.GENERALIZE)
            ]
        ),
        "POL-IFRS-15": CompliancePolicyModel(
            policy_id="POL-IFRS-15",
            title="Quy Chuẩn Doanh Thu & Kiểm Soát Cuốc Xe IFRS 15 / SOX 404",
            jurisdiction="GLOBAL",
            legal_framework="IFRS 15 Revenue Contracts & SOX 404",
            raw_policy_text="Quy chuẩn toàn cầu: cước phí cuốc xe (fare_amount) bắt buộc > 0 và cự ly di chuyển (trip_distance_km) >= 0.1km. Toàn bộ record vi phạm phải vào Quarantine giải trình.",
            effective_date="2024-01-01",
            clauses=[
                PolicyClauseModel(clause_id="C-REV-01", policy_id="POL-IFRS-15", clause_number="Section 404", requirement_summary="Kiểm toán cước phí và cự ly hợp lệ", target_pii_roles=[PiiRoleType.NON_PERSONAL_REFERENCE], mandated_action=TreatmentActionType.KEEP)
            ]
        ),
        "POL-EV-SAFETY": CompliancePolicyModel(
            policy_id="POL-EV-SAFETY",
            title="Quy Chuẩn An Toàn Vận Hành Pin Xe Điện VinFast IEC 62660-1",
            jurisdiction="GLOBAL",
            legal_framework="IEC 62660-1 & VinFast Technical Standard",
            raw_policy_text="Quy chuẩn an toàn pin: Nhiệt độ pack pin (battery_temp_c) nằm trong dải an toàn [-10°C, 85°C], dung lượng pin (battery_soc) nằm trong khoảng [0%, 100%].",
            effective_date="2024-01-01",
            clauses=[
                PolicyClauseModel(clause_id="C-EV-01", policy_id="POL-EV-SAFETY", clause_number="IEC 62660 Section 4", requirement_summary="Giám sát nhiệt độ pin an toàn", target_pii_roles=[PiiRoleType.TECHNICAL_METADATA], mandated_action=TreatmentActionType.KEEP)
            ]
        )
    }
    # Backward compatibility alias for legacy tests/references
    policies["POL-VN-ND13"] = policies["POL-VN-LAW91"]
    return policies


# =============================================================================
# 3. LOADER & PROCESSOR FOR 3-ZONE PILOT DATA
# =============================================================================

class ThreeZonePilotLoader:
    def __init__(self, data_dir: Path = PILOT_DATA_DIR):
        self.data_dir = data_dir
        self.quar_mgr = QuarantineManager()
        self.runner = DynamicRuleRunner(quarantine_manager=self.quar_mgr)
        self.agent = PolicyRuleProposerAgent()

    def load_raw_csv(self, filename: str) -> pd.DataFrame:
        file_path = self.data_dir / filename
        if not file_path.exists():
            raise FileNotFoundError(f"Không tìm thấy file: {file_path}")
        df = pd.read_csv(file_path)
        df.columns = [c.strip() for c in df.columns]
        return df.map(lambda x: x.strip() if isinstance(x, str) else x)

    def initialize_pilot_environment(self) -> Dict[str, Any]:
        """
        Khởi tạo môi trường Pilot:
        1. Đăng ký Catalog & Policies.
        2. Kích hoạt các Active Rules ban đầu do Admin Nguyễn Quốc Bảo phê duyệt.
        """
        datasets = get_3zone_datasets()
        columns = get_3zone_columns()
        policies = get_3zone_policies()

        # Cấu hình các Active Rules mặc định cho 3-zone pilot
        initial_rules = [
            # 1. Doanh thu hợp lệ IFRS 15
            FieldProcessConfigModel(
                config_id="ACT-TRIP-FARE",
                dataset_id="trips",
                column_name="fare_amount",
                pii_role=PiiRoleType.NON_PERSONAL_REFERENCE,
                treatment_action=TreatmentActionType.KEEP,
                operation_id="range_check",
                execution_phase=ExecutionPhase.POST_CHECK,
                execution_order=1,
                params_json={"min_val": 0.01, "allow_zero": False},
                expression_display="fare_amount > 0",
                severity=RuleSeverity.CRITICAL,
                law_ref="IFRS 15 / SOX 404",
                enforced_by="Nguyễn Quốc Bảo (Lead Platform)"
            ),
            # 2. Khoảng cách hợp lệ
            FieldProcessConfigModel(
                config_id="ACT-TRIP-DIST",
                dataset_id="trips",
                column_name="trip_distance_km",
                pii_role=PiiRoleType.NON_PERSONAL_REFERENCE,
                treatment_action=TreatmentActionType.KEEP,
                operation_id="range_check",
                execution_phase=ExecutionPhase.POST_CHECK,
                execution_order=2,
                params_json={"min_val": 0.1, "allow_zero": False},
                expression_display="trip_distance_km >= 0.1",
                severity=RuleSeverity.HIGH,
                law_ref="IFRS 15 / SOX 404",
                enforced_by="Nguyễn Quốc Bảo (Lead Platform)"
            ),
            # 3. Làm mờ tọa độ GPS đón khách (Generalize -> 2 decimals)
            FieldProcessConfigModel(
                config_id="ACT-TRIP-GPS-LAT",
                dataset_id="trips",
                column_name="pickup_latitude",
                pii_role=PiiRoleType.CONTEXTUAL_PERSONAL_DATA,
                treatment_action=TreatmentActionType.GENERALIZE,
                operation_id="round_decimal",
                execution_phase=ExecutionPhase.TREATMENT,
                execution_order=3,
                params_json={"decimals": 2},
                expression_display="round_decimal(pickup_latitude, 2)",
                severity=RuleSeverity.MEDIUM,
                law_ref="Luật 91/2025/QH15 & Nghị định 356/2025/NĐ-CP",
                enforced_by="Nguyễn Quốc Bảo (Lead Platform)"
            ),
            FieldProcessConfigModel(
                config_id="ACT-TRIP-GPS-LON",
                dataset_id="trips",
                column_name="pickup_longitude",
                pii_role=PiiRoleType.CONTEXTUAL_PERSONAL_DATA,
                treatment_action=TreatmentActionType.GENERALIZE,
                operation_id="round_decimal",
                execution_phase=ExecutionPhase.TREATMENT,
                execution_order=4,
                params_json={"decimals": 2},
                expression_display="round_decimal(pickup_longitude, 2)",
                severity=RuleSeverity.MEDIUM,
                law_ref="Luật 91/2025/QH15 & Nghị định 356/2025/NĐ-CP",
                enforced_by="Nguyễn Quốc Bảo (Lead Platform)"
            ),
            # 4. Bí danh hóa Driver ID
            FieldProcessConfigModel(
                config_id="ACT-TRIP-DRIVER",
                dataset_id="trips",
                column_name="driver_id",
                pii_role=PiiRoleType.LINKABLE_IDENTIFIER,
                treatment_action=TreatmentActionType.PSEUDONYMIZE,
                operation_id="hash_sha256",
                execution_phase=ExecutionPhase.TREATMENT,
                execution_order=5,
                params_json={"salt": "gsm_driver_salt_2026"},
                expression_display="hash_sha256(driver_id)",
                severity=RuleSeverity.HIGH,
                law_ref="GDPR Article 5(1)(c) & NĐ 13",
                enforced_by="Nguyễn Quốc Bảo (Lead Platform)"
            ),
            # 5. An toàn pin xe điện (Nhiệt độ [-10, 85])
            FieldProcessConfigModel(
                config_id="ACT-TELEM-TEMP",
                dataset_id="telemetry",
                column_name="battery_temp_c",
                pii_role=PiiRoleType.TECHNICAL_METADATA,
                treatment_action=TreatmentActionType.KEEP,
                operation_id="range_check",
                execution_phase=ExecutionPhase.POST_CHECK,
                execution_order=1,
                params_json={"min_val": -10.0, "max_val": 85.0, "allow_zero": True},
                expression_display="battery_temp_c BETWEEN -10 AND 85",
                severity=RuleSeverity.CRITICAL,
                law_ref="IEC 62660-1 Pin EV",
                enforced_by="Nguyễn Quốc Bảo (Lead Platform)"
            ),
            # 6. Dung lượng pin (SOC [0, 100])
            FieldProcessConfigModel(
                config_id="ACT-TELEM-SOC",
                dataset_id="telemetry",
                column_name="battery_soc",
                pii_role=PiiRoleType.TECHNICAL_METADATA,
                treatment_action=TreatmentActionType.KEEP,
                operation_id="range_check",
                execution_phase=ExecutionPhase.POST_CHECK,
                execution_order=2,
                params_json={"min_val": 0.0, "max_val": 100.0, "allow_zero": True},
                expression_display="battery_soc BETWEEN 0 AND 100",
                severity=RuleSeverity.CRITICAL,
                law_ref="VinFast EV Telematics Spec",
                enforced_by="Nguyễn Quốc Bảo (Lead Platform)"
            )
        ]
        self.runner.load_rules(initial_rules)
        return {
            "datasets": datasets,
            "columns": columns,
            "policies": policies,
            "active_rules_count": len(initial_rules)
        }

    def process_pilot_trips(self, limit: int = 1000) -> Dict[str, Any]:
        """
        Nạp dữ liệu ride_hailing_xanh_sm_trips.csv vào Bronze và thực thi qua Dynamic Rule Runner.
        Tách ra Silver (sạch, đã làm mờ GPS, bí danh hóa driver_id) và Quarantine.
        """
        df = self.load_raw_csv("ride_hailing_xanh_sm_trips.csv")
        if limit:
            df = df.head(limit)
        
        records = df.to_dict(orient="records")
        res = self.runner.run_pipeline("trips", records, run_id="run_pilot_trips_001")
        return {
            "run_id": res.run_id,
            "scanned": res.scanned_count,
            "silver": res.silver_count,
            "quarantine": res.quarantine_count,
            "sample_silver": res.silver_records[0] if res.silver_records else None
        }

    def process_pilot_telemetry(self, limit: int = 1000) -> Dict[str, Any]:
        """
        Nạp dữ liệu synthetic_ev_telemetry_ved_ref.csv và thực thi qua Dynamic Rule Runner.
        """
        df = self.load_raw_csv("synthetic_ev_telemetry_ved_ref.csv")
        if limit:
            df = df.head(limit)

        records = df.to_dict(orient="records")
        res = self.runner.run_pipeline("telemetry", records, run_id="run_pilot_telemetry_001")
        return {
            "run_id": res.run_id,
            "scanned": res.scanned_count,
            "silver": res.silver_count,
            "quarantine": res.quarantine_count,
            "sample_silver": res.silver_records[0] if res.silver_records else None
        }


def get_3zone_compliance_rules() -> List[ComplianceCheckRuleModel]:
    """Quy tắc kiểm tra tuân thủ & chất lượng CỐ ĐỊNH (Backend-only, không thể sửa trên UI, AI không đề xuất)."""
    return [
        ComplianceCheckRuleModel(
            rule_id="CHK-TRIP-FARE",
            dataset_id="ride_hailing_xanh_sm_trips.csv",
            target_column="fare_amount",
            rule_name="Doanh thu & cự ly chuyến đi hợp lệ",
            rule_code="TC-REV-01",
            expression="fare_amount > 0 AND trip_distance_km >= 0.1",
            description="Cước phí phải lớn hơn 0 và cự ly >= 0.1km theo chuẩn IFRS 15 / SOX 404",
            law_ref="IFRS 15 / SOX Section 404",
            severity=RuleSeverity.CRITICAL,
            is_fixed=True
        ),
        ComplianceCheckRuleModel(
            rule_id="CHK-TRIP-GPS",
            dataset_id="ride_hailing_xanh_sm_trips.csv",
            target_column="pickup_latitude",
            rule_name="Giới hạn tọa độ đón khách lãnh thổ VN",
            rule_code="TC-GEO-01",
            expression="pickup_latitude BETWEEN 8.0 AND 24.0",
            description="Tọa độ GPS điểm đón khách phải nằm trong phạm vi lãnh thổ Việt Nam",
            law_ref="Quy định Vận tải GSM VN",
            severity=RuleSeverity.HIGH,
            is_fixed=True
        ),
        ComplianceCheckRuleModel(
            rule_id="CHK-TELEM-TEMP",
            dataset_id="synthetic_ev_telemetry_ved_ref.csv",
            target_column="battery_temp_c",
            rule_name="Ngưỡng nhiệt độ an toàn pack pin EV",
            rule_code="TC-TEL-01",
            expression="battery_temp_c BETWEEN -10.0 AND 85.0",
            description="Nhiệt độ cell pin xe điện VinFast phải nằm trong ngưỡng kỹ thuật an toàn",
            law_ref="IEC 62660-1 / UN ECE R100",
            severity=RuleSeverity.CRITICAL,
            is_fixed=True
        ),
        ComplianceCheckRuleModel(
            rule_id="CHK-TELEM-SOC",
            dataset_id="synthetic_ev_telemetry_ved_ref.csv",
            target_column="battery_soc",
            rule_name="Dung lượng pin xe điện khả dụng (SoC)",
            rule_code="TC-TEL-02",
            expression="battery_soc BETWEEN 0.0 AND 100.0",
            description="Mức pin xe điện phải nằm trong dải 0% đến 100%",
            law_ref="VinFast EV Telematics Spec",
            severity=RuleSeverity.CRITICAL,
            is_fixed=True
        ),
        ComplianceCheckRuleModel(
            rule_id="CHK-CHG-METER",
            dataset_id="acn_charging_mapped.csv",
            target_column="meter_kwh_delta",
            rule_name="Sai số công tơ Modbus trụ sạc V-GREEN",
            rule_code="TC-CHG-01",
            expression="abs(meter_kwh_delta - bms_kwh_delta) <= 0.03 * meter_kwh_delta",
            description="Chênh lệch điện năng giữa đồng hồ trụ sạc và xe không vượt quá 3%",
            law_ref="SOX 404 & Tiêu chuẩn V-GREEN",
            severity=RuleSeverity.HIGH,
            is_fixed=True
        ),
        ComplianceCheckRuleModel(
            rule_id="CHK-FLT-STATUS",
            dataset_id="fleet_index.csv",
            target_column="operating_status",
            rule_name="Trạng thái vận hành xe hợp lệ",
            rule_code="TC-FLT-01",
            expression="operating_status IN ('READY', 'IN_SERVICE', 'CHARGING')",
            description="Trạng thái xe trong đội xe phải thuộc danh mục chuẩn",
            law_ref="GSM Fleet Management Standard",
            severity=RuleSeverity.MEDIUM,
            is_fixed=True
        )
    ]


def get_3zone_treatment_rules() -> List[DataTreatmentRuleModel]:
    """Quy tắc xử lý & chuẩn hóa dữ liệu chung (Masking, Hashing, Rounding, Sanitization - AI đề xuất note riêng, sửa được trên UI)."""
    return [
        # Active Treatments (Đang áp dụng)
        DataTreatmentRuleModel(
            rule_id="TRT-TRIP-DRIVER",
            dataset_id="ride_hailing_xanh_sm_trips.csv",
            column_name="driver_id",
            operation_id="hash_sha256",
            treatment_name="Mã hóa một chiều Driver ID",
            params_json={"salt": "gsm_driver_salt_2026"},
            expression_display="hash_sha256(driver_id)",
            description="Bí danh hóa mã tài xế đối tác GSM",
            is_ai_proposed=False,
            status="active",
            enforced_by="Nguyễn Quốc Bảo (Lead Platform)"
        ),
        DataTreatmentRuleModel(
            rule_id="TRT-TRIP-GPS",
            dataset_id="ride_hailing_xanh_sm_trips.csv",
            column_name="pickup_latitude",
            operation_id="round_decimal",
            treatment_name="Làm tròn tọa độ GPS đón khách",
            params_json={"decimals": 2},
            expression_display="round_decimal(pickup_latitude, 2)",
            description="Làm mờ tọa độ GPS đón khách độ chính xác ~1km bảo vệ nơi ở",
            is_ai_proposed=False,
            status="active",
            enforced_by="Nguyễn Quốc Bảo (Lead Platform)"
        ),
        # AI Proposed Treatments (Được note riêng biệt, chờ Admin duyệt và có thể sửa biểu thức trên UI)
        DataTreatmentRuleModel(
            rule_id="TRT-PROP-PHONE",
            dataset_id="ride_hailing_xanh_sm_trips.csv",
            column_name="customer_phone",
            operation_id="mask_phone",
            treatment_name="Che mờ số điện thoại khách hàng",
            params_json={"prefix_len": 3, "suffix_len": 2, "mask_char": "*"},
            expression_display="mask_phone(customer_phone, prefix=3, suffix=2)",
            description="Che mờ số điện thoại khách đặt xe",
            is_ai_proposed=True,
            ai_rationale="AI phát hiện số điện thoại khách hàng dạng cleartext, đề xuất che mờ bảo vệ dữ liệu theo Luật 91/2025/QH15 & Nghị định 356/2025/NĐ-CP.",
            ai_confidence=0.965,
            status="pending",
            enforced_by="AI Treatment Proposer"
        ),
        DataTreatmentRuleModel(
            rule_id="TRT-PROP-NAME",
            dataset_id="ride_hailing_xanh_sm_trips.csv",
            column_name="customer_name",
            operation_id="mask_name",
            treatment_name="Che mờ họ tên khách hàng",
            params_json={"keep_first": True, "mask_char": "*"},
            expression_display="mask_name(customer_name)",
            description="Che mờ họ tên hành khách",
            is_ai_proposed=True,
            ai_rationale="Họ tên khách hàng cần được ẩn danh tên riêng theo quy định bảo vệ dữ liệu cá nhân.",
            ai_confidence=0.940,
            status="pending",
            enforced_by="AI Treatment Proposer"
        ),
        DataTreatmentRuleModel(
            rule_id="TRT-PROP-VIN",
            dataset_id="synthetic_ev_telemetry_ved_ref.csv",
            column_name="vehicle_vin",
            operation_id="to_upper",
            treatment_name="Chuẩn hóa mã VIN in hoa",
            params_json={},
            expression_display="to_upper(vehicle_vin)",
            description="Chuẩn hóa chuỗi ký tự mã VIN xe",
            is_ai_proposed=True,
            ai_rationale="AI phát hiện một số gói tin telemetry có mã VIN chữ thường, đề xuất chuẩn hóa in hoa chuẩn ISO 3779.",
            ai_confidence=0.980,
            status="pending",
            enforced_by="AI Treatment Proposer"
        )
    ]

