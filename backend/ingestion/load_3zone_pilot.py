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
    ExecutionPhase,
    RuleSeverity,
    UserRole
)
from backend.engine.dynamic_runner import DynamicRuleRunner
from backend.engine.quarantine_manager import QuarantineManager
from backend.ai.policy_rule_proposer import PolicyRuleProposerAgent


PILOT_DATA_DIR = Path("data/vingroup_clean_3zone_pilot")


# =============================================================================
# 1. CATALOG SPECIFICATION FOR 3-ZONE PILOT
# =============================================================================

def get_3zone_datasets() -> Dict[str, DatasetModel]:
    return {
        "trips": DatasetModel(
            dataset_id="trips",
            name="ride_hailing_xanh_sm_trips",
            title="GSM Xanh SM Trips (3-Zone Pilot: EU, VN, US)",
            domain="trips",
            owner_dept="Khối Vận Hành GSM Toàn Cầu",
            storage_table_bronze="bronze.trips_raw",
            storage_table_silver="silver.trips_clean",
            description="10,382 cuốc xe taxi điện VinFast phân bổ qua 3 phân vùng EU (Berlin), VN (Hà Nội), US (New York)",
            retention_days=1825
        ),
        "telemetry": DatasetModel(
            dataset_id="telemetry",
            name="synthetic_ev_telemetry_ved_ref",
            title="VinFast EV Telematics VED (3-Zone Pilot)",
            domain="telemetry",
            owner_dept="Khối R&D Phần Mềm Xe Điện VinFast",
            storage_table_bronze="bronze.telemetry_raw",
            storage_table_silver="silver.telemetry_clean",
            description="86,400 bản ghi telemetry cảm biến pin (SOC, nhiệt độ, điện áp, dòng xả) từ 60 xe pilot trong 15 ngày",
            retention_days=730
        ),
        "charging": DatasetModel(
            dataset_id="charging",
            name="acn_charging_mapped",
            title="V-GREEN Trạm Sạc Xe Điện (3-Zone Pilot)",
            domain="charging",
            owner_dept="Công Ty Cổ Phần Phát Triển Trạm Sạc Toàn Cầu V-GREEN",
            storage_table_bronze="bronze.charging_raw",
            storage_table_silver="silver.charging_clean",
            description="1,331 phiên sạc xe điện với thông số công suất kW, sản lượng kWh tiêu thụ và chi phí",
            retention_days=1825
        ),
        "nlp_feedback": DatasetModel(
            dataset_id="nlp_feedback",
            name="nlp_benchmark_uit_vsfc",
            title="Khách Hàng Phản Hồi & Đánh Giá (NLP Benchmark)",
            domain="nlp_feedback",
            owner_dept="Trung Tâm Trải Nghiệm Khách Hàng & CSKH",
            storage_table_bronze="bronze.feedback_raw",
            storage_table_silver="silver.feedback_clean",
            description="500 phản hồi văn bản tự do của khách hàng về chất lượng cuốc xe và trạm sạc V-GREEN",
            retention_days=365
        ),
        "fleet": DatasetModel(
            dataset_id="fleet",
            name="fleet_index",
            title="Đội Xe Pilot 60 VIN (VinFast VF8, VF9, VF e34)",
            domain="fleet",
            owner_dept="Quản Lý Đội Xe GSM Global",
            storage_table_bronze="bronze.fleet_raw",
            storage_table_silver="silver.fleet_clean",
            description="60 xe điện VinFast chia đều cho 3 phân vùng VN (Hà Nội: 20 xe), EU (Berlin: 20 xe), US (New York: 20 xe)",
            retention_days=3650
        )
    }


def get_3zone_columns() -> Dict[str, List[ColumnModel]]:
    return {
        "trips": [
            ColumnModel(dataset_id="trips", column_name="trip_id", data_type="VARCHAR(50)", is_primary_key=True, pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="trips", column_name="vehicle_vin", data_type="VARCHAR(50)", is_personal_data=True, pii_role=PiiRoleType.LINKABLE_IDENTIFIER, default_treatment=TreatmentActionType.KEEP_RESTRICTED, semantic_tag="vehicle_identifier"),
            ColumnModel(dataset_id="trips", column_name="driver_id", data_type="VARCHAR(50)", is_personal_data=True, pii_role=PiiRoleType.LINKABLE_IDENTIFIER, default_treatment=TreatmentActionType.PSEUDONYMIZE, semantic_tag="driver_identifier"),
            ColumnModel(dataset_id="trips", column_name="pickup_datetime", data_type="TIMESTAMPTZ", pii_role=PiiRoleType.TECHNICAL_METADATA, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="trips", column_name="dropoff_datetime", data_type="TIMESTAMPTZ", pii_role=PiiRoleType.TECHNICAL_METADATA, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="trips", column_name="trip_distance_km", data_type="NUMERIC(8,3)", pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP, semantic_tag="distance_metric"),
            ColumnModel(dataset_id="trips", column_name="fare_amount", data_type="NUMERIC(12,2)", pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP, semantic_tag="financial_fare"),
            ColumnModel(dataset_id="trips", column_name="tip_amount", data_type="NUMERIC(12,2)", pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="trips", column_name="total_fare", data_type="NUMERIC(12,2)", pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="trips", column_name="pickup_latitude", data_type="NUMERIC(9,6)", is_personal_data=True, pii_role=PiiRoleType.CONTEXTUAL_PERSONAL_DATA, default_treatment=TreatmentActionType.GENERALIZE, semantic_tag="gps_latitude"),
            ColumnModel(dataset_id="trips", column_name="pickup_longitude", data_type="NUMERIC(9,6)", is_personal_data=True, pii_role=PiiRoleType.CONTEXTUAL_PERSONAL_DATA, default_treatment=TreatmentActionType.GENERALIZE, semantic_tag="gps_longitude"),
            ColumnModel(dataset_id="trips", column_name="vehicle_type", data_type="VARCHAR(50)", pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="trips", column_name="subject_zone", data_type="VARCHAR(10)", pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP, semantic_tag="regulatory_jurisdiction")
        ],
        "telemetry": [
            ColumnModel(dataset_id="telemetry", column_name="record_id", data_type="VARCHAR(50)", is_primary_key=True, pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="telemetry", column_name="vehicle_vin", data_type="VARCHAR(50)", is_personal_data=True, pii_role=PiiRoleType.LINKABLE_IDENTIFIER, default_treatment=TreatmentActionType.KEEP_RESTRICTED),
            ColumnModel(dataset_id="telemetry", column_name="timestamp", data_type="TIMESTAMPTZ", pii_role=PiiRoleType.TECHNICAL_METADATA, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="telemetry", column_name="speed_kmh", data_type="NUMERIC(6,2)", pii_role=PiiRoleType.TECHNICAL_METADATA, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="telemetry", column_name="motor_rpm", data_type="INT", pii_role=PiiRoleType.TECHNICAL_METADATA, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="telemetry", column_name="battery_soc", data_type="NUMERIC(5,2)", pii_role=PiiRoleType.TECHNICAL_METADATA, default_treatment=TreatmentActionType.KEEP, semantic_tag="battery_state_of_charge"),
            ColumnModel(dataset_id="telemetry", column_name="battery_voltage", data_type="NUMERIC(6,2)", pii_role=PiiRoleType.TECHNICAL_METADATA, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="telemetry", column_name="battery_current", data_type="NUMERIC(6,2)", pii_role=PiiRoleType.TECHNICAL_METADATA, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="telemetry", column_name="battery_temp_c", data_type="NUMERIC(5,2)", pii_role=PiiRoleType.TECHNICAL_METADATA, default_treatment=TreatmentActionType.KEEP, semantic_tag="battery_temperature_celsius"),
            ColumnModel(dataset_id="telemetry", column_name="latitude", data_type="NUMERIC(9,6)", is_personal_data=True, pii_role=PiiRoleType.CONTEXTUAL_PERSONAL_DATA, default_treatment=TreatmentActionType.GENERALIZE),
            ColumnModel(dataset_id="telemetry", column_name="longitude", data_type="NUMERIC(9,6)", is_personal_data=True, pii_role=PiiRoleType.CONTEXTUAL_PERSONAL_DATA, default_treatment=TreatmentActionType.GENERALIZE),
            ColumnModel(dataset_id="telemetry", column_name="subject_zone", data_type="VARCHAR(10)", pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP)
        ],
        "charging": [
            ColumnModel(dataset_id="charging", column_name="session_id", data_type="VARCHAR(100)", is_primary_key=True, pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="charging", column_name="vehicle_vin", data_type="VARCHAR(50)", is_personal_data=True, pii_role=PiiRoleType.LINKABLE_IDENTIFIER, default_treatment=TreatmentActionType.KEEP_RESTRICTED),
            ColumnModel(dataset_id="charging", column_name="station_id", data_type="VARCHAR(50)", pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="charging", column_name="start_time", data_type="TIMESTAMPTZ", pii_role=PiiRoleType.TECHNICAL_METADATA, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="charging", column_name="duration_mins", data_type="NUMERIC(8,2)", pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="charging", column_name="kwh_consumed", data_type="NUMERIC(8,2)", pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="charging", column_name="power_kw", data_type="NUMERIC(6,2)", pii_role=PiiRoleType.TECHNICAL_METADATA, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="charging", column_name="station_temp_c", data_type="NUMERIC(5,2)", pii_role=PiiRoleType.TECHNICAL_METADATA, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="charging", column_name="cost_vnd", data_type="NUMERIC(12,2)", pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="charging", column_name="subject_zone", data_type="VARCHAR(10)", pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP)
        ],
        "nlp_feedback": [
            ColumnModel(dataset_id="nlp_feedback", column_name="sentence", data_type="TEXT", is_personal_data=True, pii_role=PiiRoleType.AMBIGUOUS_UNSTRUCTURED_DATA, default_treatment=TreatmentActionType.PSEUDONYMIZE, semantic_tag="free_text_review"),
            ColumnModel(dataset_id="nlp_feedback", column_name="sentiment", data_type="INT", pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="nlp_feedback", column_name="topic", data_type="INT", pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP)
        ],
        "fleet": [
            ColumnModel(dataset_id="fleet", column_name="vehicle_vin", data_type="VARCHAR(50)", is_primary_key=True, pii_role=PiiRoleType.LINKABLE_IDENTIFIER, default_treatment=TreatmentActionType.KEEP_RESTRICTED, semantic_tag="vehicle_identifier"),
            ColumnModel(dataset_id="fleet", column_name="vehicle_type", data_type="VARCHAR(50)", pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="fleet", column_name="telemetry_equipped", data_type="BOOLEAN", pii_role=PiiRoleType.TECHNICAL_METADATA, default_treatment=TreatmentActionType.KEEP),
            ColumnModel(dataset_id="fleet", column_name="subject_zone", data_type="VARCHAR(10)", pii_role=PiiRoleType.NON_PERSONAL_REFERENCE, default_treatment=TreatmentActionType.KEEP)
        ]
    }


DATASET_FILE_MAP = {
    "trips": "ride_hailing_xanh_sm_trips.csv",
    "ride_hailing_xanh_sm_trips": "ride_hailing_xanh_sm_trips.csv",
    "telemetry": "synthetic_ev_telemetry_ved_ref.csv",
    "synthetic_ev_telemetry_ved_ref": "synthetic_ev_telemetry_ved_ref.csv",
    "charging": "acn_charging_mapped.csv",
    "acn_charging_mapped": "acn_charging_mapped.csv",
    "nlp_feedback": "nlp_benchmark_uit_vsfc.csv",
    "nlp_benchmark_uit_vsfc": "nlp_benchmark_uit_vsfc.csv",
    "fleet": "fleet_index.csv",
    "fleet_index": "fleet_index.csv"
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
    return {
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
        "POL-VN-ND13": CompliancePolicyModel(
            policy_id="POL-VN-ND13",
            title="Nghị Định 13/2023/NĐ-CP - Phân Vùng Việt Nam",
            jurisdiction="VN",
            legal_framework="Nghị định 13/2023/NĐ-CP",
            raw_policy_text="Áp dụng cho đội xe và cuốc xe vùng Việt Nam (Hà Nội: lat 20.95-21.10, lon 105.75-105.90). Yêu cầu che giấu định danh và làm mờ tọa độ di chuyển.",
            effective_date="2023-07-01",
            clauses=[
                PolicyClauseModel(clause_id="C-VN-01", policy_id="POL-VN-ND13", clause_number="Điều 17.2", requirement_summary="Che mờ hoặc bí danh hóa dữ liệu cá nhân liên lạc", target_pii_roles=[PiiRoleType.DIRECT_IDENTIFIER], mandated_action=TreatmentActionType.PSEUDONYMIZE),
                PolicyClauseModel(clause_id="C-VN-02", policy_id="POL-VN-ND13", clause_number="Điều 13", requirement_summary="Làm mờ vị trí đón trả khách", target_pii_roles=[PiiRoleType.CONTEXTUAL_PERSONAL_DATA], mandated_action=TreatmentActionType.GENERALIZE)
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
        return pd.read_csv(file_path)

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
                law_ref="Nghị định 13/2023 & GDPR Art. 25",
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
                law_ref="Nghị định 13/2023 & GDPR Art. 25",
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
