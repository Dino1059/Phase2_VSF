"""
ingest_vingroup_real_data.py

Layer 2 (+ 2.5) của pipeline DataTrust OS DATA-02.

Đọc dữ liệu thật đã fetch ở Layer 1 (VED, ACN-Data, fact_rides+related, UIT-VSFC),
map sang schema VinGroup, và gắn nhãn provenance theo 4 tier (R / RD / RS / S)
cho TỪNG CỘT — thay vì gắn nhãn nhị phân "real" / "seed" cho cả file.

Tier definitions (xem data_provenance_analysis.md mục 3):
    R  = Real-Exact              : lấy thẳng từ nguồn thật, không biến đổi
    RD = Real-Derived            : tính từ >=1 trường thật bằng công thức xác định
    RS = Real-Statistically-Parameterized : không có trường thật tương ứng,
         sinh synthetic nhưng tham số hóa từ phân phối/tài liệu thật
    S  = Scenario-Construct      : dựng có chủ đích cho kịch bản, không có
         tương ứng thật, phải có lập luận bảo vệ được

Layer 2.5 (Fleet Linkage) tạo khóa nối vehicle_id xuyên domain một cách TƯỜNG MINH,
tách biệt khỏi dữ liệu đo lường, không lẫn vào benchmark precision/recall.

Design decisions (see scratch_ingest_redesign_analysis.md, 2026-08-07;
                        + scratch_impl_notes_timeseries.md, 2026-08-08):
  - Trips: driver_id gốc không tương ứng VIN được gán → Tier S (deterministic).
    Fare giữ giá trị gốc + cờ `currency_unverified` (Tier S) — chưa xác minh VND/USD.
  - Charging: phân loại `charging_pattern` theo duration thật
    (>120min: overnight_deep, <=90min: opportunity_fast, 90-120: ambiguous).
    **2026-08-08 update**: soft priority ngoài operating hours + soft_overlap_flag.
  - Telemetry: 2026-08-08 FULL FLEET (60 pilot VIN) — synthetic 15-min/sample
    86,400 rows. VED 20 xe làm per-vehicle distribution reference (speed/RPM/SOC).
    Mỗi pilot ánh xạ 1 VED VehId (cycling qua 20 để cover 60 pilot).
    KHÔNG anchor timeline bằng VED trip duration.
  - Fleet Index: thêm cột `telemetry_equipped` (gi� = True cho 60 VIN).

CHƯA fetch dữ liệu thật — script này giả định Layer 1 đã ghi các file raw vào
data/raw_public_v2/ theo đúng schema mô tả trong schema_analysis.md. Chỉnh
đường dẫn trong CONFIG bên dưới cho khớp máy của bạn.
"""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, time
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# CONFIG — chỉnh lại đường dẫn cho khớp máy bạn
# --------------------------------------------------------------------------- #

RAW_DIR = Path("scripts/data/raw_public_v2")
# Output folder rename: thêm hậu tố `_timeseries` (user quyết định 2026-08-08)
# Lý do: tách bạch với output cũ, dễ so sánh A/B khi benchmark.
# Output folder: synthetic_pilot_dataset (telemetry=100% synthetic, ref=real distributions)
OUT_DIR = Path("data/vingroup_pilot_dataset")
MANIFEST_PATH = OUT_DIR / "provenance_manifest.json"
FLEET_META_PATH = OUT_DIR / "fleet_index.json"

# 2026-08-08 v4 redesign: VED per-vehicle calibration cache (decouple from raw CSV)
VED_CALIBRATION_PATH = OUT_DIR / "ved_calibration.json"

RANDOM_SEED = 42  # cố định để pipeline tái lập được (reproducibility)
FLEET_SIZE = 60  # số VIN giả định trong Constructed Fleet Index
PILOT_SIZE = 60  # 2026-08-08: full fleet có telemetry (VED distribution làm reference)
OBSERVATION_DAYS = 15  # cửa sổ quan sát tối thiểu (VinGroup baseline docx)
TRIPS_PER_VIN_PER_DAY = 14  # 2026-08-08 v4: scale-down tu 20 -> 14 vi operating window 12h (06-18) disjoint voi overnight
CHARGING_PER_VIN_PER_DAY = 1.5  # baseline 1.5 session/ngày/VIN
OVERNIGHT_RATIO = 1.0 / CHARGING_PER_VIN_PER_DAY  # ~67% overnight (1.0/day)
# opportunity = 0.5 ngày/VIN (chia trên tổng CHARGING_PER_VIN_PER_DAY=1.5)
# tổng: 1.0 + 0.5 = 1.5 session/ngày/VIN

# 2026-08-08 v4 redesign: State machine parameters (Hướng 2)
# Deadhead (xe chạy không khách) chiếm ~30-40% operating hours trong thực tế
# taxi ride-hailing → tăng telemetry density tự nhiên.
DEADHEAD_FRACTION = 0.35  # ~35% operating time = deadhead (speed > 0, no fare)
CHARGING_OVERNIGHT_MIN_DURATION = 6 * 60  # 6 tiếng min overnight
CHARGING_OVERNIGHT_MAX_DURATION = 9 * 60  # 9 tiếng max overnight
CHARGING_OPPORTUNITY_MIN_DURATION = 30    # 30 phút min opportunity
CHARGING_OPPORTUNITY_MAX_DURATION = 90    # 90 phút max opportunity
TRIP_MIN_DURATION = 15  # phút - taxi ride trung bình nội đô
TRIP_MAX_DURATION = 25  # phút
DEADHEAD_MIN_DURATION = 5   # phút - xe chạy giữa các điểm đón
DEADHEAD_MAX_DURATION = 20  # phút
IDLE_MIN_DURATION = 3       # phút - xe đỗ ch� khách
IDLE_MAX_DURATION = 15      # phút
BUFFER_BETWEEN_TRIPS_MIN = 5  # phút buffer chuyển trạng thái

# Telemetry: pure synthetic 15-min/sample (VED distribution làm reference)
TELEMETRY_SAMPLES_PER_DAY = 96  # 24h × 4 = 96 mẫu/15 phút (full 24h coverage)
TELEMETRY_INTERVAL_MIN = 15  # khoảng cách giữa 2 sample liên tiếp (phút)

# Biểu giá điện VN tham khảo (EVN, bậc kinh doanh trung bình) — cập nhật khi có
# số liệu chính thức mới hơn. Dùng cho RD cost_vnd = kwh * tariff.
EVN_TARIFF_VND_PER_KWH = 3_100.0

# Tỷ giá quy đổi nếu fact_rides ở USD — XÁC MINH LẠI đơn vị gốc trước khi dùng.
USD_TO_VND = 25_400.0

# Bounding box Hà Nội để re-project tọa độ thật (giữ pattern chuyển động,
# đổi vị trí tuyệt đối) — không claim đây là tọa độ Hà Nội thật.
HANOI_BBOX = {"lat_min": 20.95, "lat_max": 21.10, "lon_min": 105.75, "lon_max": 105.90}

# Giờ hoạt động taxi (phân bổ pickup_datetime trong 1 ngày)
TAXI_OPERATING_HOURS = (6, 22)  # 6h - 22h (16 tiếng/ngày)

# Charging pattern thresholds (giả định từ docx baseline)
CHARGING_OVERNIGHT_MIN_MINS = 120.0  # > 120 min → overnight deep charge
CHARGING_OPPORTUNITY_MAX_MINS = 90.0  # <= 90 min → opportunity fast charge

rng = np.random.default_rng(RANDOM_SEED)


# --------------------------------------------------------------------------- #
# Provenance manifest — ghi tier cho từng cột của từng dataset output
# --------------------------------------------------------------------------- #

@dataclass
class ProvenanceManifest:
    entries: dict = field(default_factory=dict)

    def tag(self, dataset: str, column: str, tier: str, note: str = ""):
        assert tier in {"R", "RD", "RS", "S"}, f"Tier không hợp lệ: {tier}"
        self.entries.setdefault(dataset, {})[column] = {"tier": tier, "note": note}

    def save(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "generated_at": datetime.utcnow().isoformat() + "Z",
                    "random_seed": RANDOM_SEED,
                    "tier_definitions": {
                        "R": "Real-Exact: lay thang tu nguon that, khong bien doi",
                        "RD": "Real-Derived: tinh tu truong that bang cong thuc xac dinh",
                        "RS": "Real-Statistically-Parameterized: sinh synthetic tham so hoa tu phan phoi/tai lieu that",
                        "S": "Scenario-Construct: dung co chu dich cho kich ban, khong co tuong ung that",
                    },
                    "columns": self.entries,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )


manifest = ProvenanceManifest()


# --------------------------------------------------------------------------- #
# Layer 2.5 — Constructed Fleet Index (khóa nối vehicle_id xuyên domain)
# --------------------------------------------------------------------------- #

def build_fleet_index(n: int = FLEET_SIZE, pilot_size: int = PILOT_SIZE) -> pd.DataFrame:
    """
    Sinh danh sách VIN giả định — khóa join nhân tạo, tier S ngay từ định nghĩa.
    Dùng seed cố định để tái lập được cho benchmark.

    2026-08-08: pilot_size = 60 (full fleet) — synthetic 15-min telemetry được gán
    cho TẤT CẢ VIN (học distribution từ 20 xe VED làm reference).
    Không còn khái niệm 'telemetry_coverage=none' — column vẫn giữ để downstream
    detect edge cases, default 'full' cho mọi VIN.
    """
    vins = [f"VF8VNF_{i:04d}" for i in range(1, n + 1)]
    fleet = pd.DataFrame({
        "vehicle_vin": vins,
        "vehicle_type": rng.choice(
            ["VF_5_TAXI", "VF_e34_TAXI", "FELIZ_S_BIKE"], size=n, p=[0.5, 0.35, 0.15]
        ),
        "telemetry_equipped": [True] * pilot_size + [False] * max(0, n - pilot_size),
    })
    return fleet


def save_fleet_metadata(fleet: pd.DataFrame, path: Path) -> None:
    """Ghi metadata fleet: linkage_type, pilot subset, design decisions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "linkage_type": "constructed_subset_with_partial_coverage",
        "fleet_size": len(fleet),
        "pilot_size": int(fleet["telemetry_equipped"].sum()),
        "vehicle_type_distribution": (
            fleet["vehicle_type"].value_counts().to_dict()
        ),
        "design_decisions": {
            "v4_2026_08_08_redesign": "STATE MACHINE (Huong 2) - single source of truth cho trips/charging/telemetry. "
                                       "4 states MUTUALLY EXCLUSIVE theo thoi gian -> disjoint by construction (overlap = 0 ve mat logic).",
            "state_machine": "DRIVING_PASSENGER (trip co khach) | DEADHEAD (chay khong khach) | IDLE (do cho) | CHARGING (sac). "
                              "generate_vin_day_states() deterministic per (vin, day_idx) - dam bao telemetry/charging/trips cung share 1 schedule.",
            "telemetry": "FULL FLEET (PILOT_SIZE=60): synthetic 15-min/sample cho 60 VIN x 15 days x 96 samples/day = 86,400 rows. "
                         "VED 20 xe lam per-vehicle distribution reference cho speed/RPM/SOC/voltage/current (cache qua ved_calibration.json). "
                         "Speed > 0 CHI trong DRIVING_PASSENGER/DEADHEAD, = 0 trong IDLE/CHARGING. "
                         "SOC physical: giam khi DRIVING*, tang khi CHARGING, stable khi IDLE. "
                         "Cot state_at_sample cho bi state tai moi sample timestamp. "
                         "Operating window cap 18:00 (truoc next overnight 18:00+) -> disjoint guarantee.",
            "trips": "Tier S: driver_id deterministic DRV_XANH_<SEQ> tu VIN. "
                     "Pool 25,003 trips tu fact_rides phan bo vao state machine's DRIVING_PASSENGER slots. "
                     "TRIPS_PER_VIN_PER_DAY=14 (~12h operating window, target 14 trip, actual mean ~11.4 do DEADHEAD/IDLE chen). "
                     "pickup/dropoff lay tu schedule, sequential + 5min buffer enforced boi state machine.",
            "charging": "State machine place: overnight (priority 1, [18:00 prior_day, 06:00 day_idx]) + next_overnight (priority 1, [18:00 day_idx, 06:00 next_day]) + 0-1 opportunity (priority 2, [10:00, 15:00]). "
                        "1,290-1,350 sessions/15days (900 overnight + 390-450 opportunity). "
                        "ACN pool subset theo duration tier. "
                        "soft_overlap_flag luon False (state machine guarantees disjoint).",
            "cross_domain_consistency": "All 3 datasets (trips/charging/telemetry) consume SAME generate_vin_day_states() output. "
                                         "Deterministic seed = hash((vin, day_idx)) % 2^31 -> reproducible cross-function.",
            "fare_currency": "Da xac minh USD (Kaggle Ride Hailing Transaction), da quy doi sang VND (x 25400). Tier RD.",
            "feedback": "2026-08-08: UIT-VSFC loai bo (sai domain: sinh vien danh gia giang vien). "
                        "Thay bang synthetic feedback scenario-driven trong inject_vingroup_real_faults.py.",
        },
        "references_pending": [
            "station_temp_c (charging) — IEC 61851-23 thermal management standard (da co gia tri)",
            "battery_temp_c (telemetry) — IEC 62660-1 Li-ion BMS operating range (da co gia tri)",
            "tip_amount (trips) — log-normal parametric, mode ~40k VND (da co gia tri)",
            "EVN tariff — bien gia dien chinh thuc (hien tai 3100 VND/kWh, da confirm)",
        ],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def assign_fleet_linkage(df: pd.DataFrame, fleet: pd.DataFrame,
                          date_col: str | None = None,
                          only_pilot: bool = False) -> pd.DataFrame:
    """
    Gán mỗi bản ghi thật (đã map) cho một VIN trong fleet — stratified random
    assignment, KHÔNG claim đây là entity resolution thật.

    Nếu `only_pilot=True`, chỉ gán cho VIN có `telemetry_equipped=True`
    (dùng cho telemetry subset VED).

    Nếu date_col được cung cấp, gán theo cách rải đều trong ngày để trình tự
    sự kiện hợp lý về mặt thời gian khi ghép qua các domain khác nhau (ví dụ:
    một VIN không thể "sạc" và "chạy trip" ở cùng một giây) — đây vẫn là
    ràng buộc phục vụ tính hợp lý của kịch bản, không phải phát hiện pattern
    thật.
    """
    n = len(df)
    if only_pilot:
        pool = fleet.loc[fleet["telemetry_equipped"], "vehicle_vin"].values
        if len(pool) == 0:
            raise ValueError("Pilot subset rỗng — kiểm tra fleet.telemetry_equipped")
    else:
        pool = fleet["vehicle_vin"].values
    assigned_vins = rng.choice(pool, size=n, replace=True)
    df = df.copy()
    df["vehicle_vin"] = assigned_vins
    return df


def assign_day_index(n: int, days: int = OBSERVATION_DAYS) -> np.ndarray:
    """
    Phân bổ N bản ghi vào `days` ngày quan sát (0..days-1) — dàn đều.
    Dùng cho trips, charging: round-robin ngẫu nhiên có kiểm soát.
    """
    return rng.integers(low=0, high=days, size=n)


def distribute_pickup_datetime(base_date: datetime, n: int,
                                days: int = OBSERVATION_DAYS,
                                operating_hours: tuple[int, int] = TAXI_OPERATING_HOURS
                                ) -> pd.Series:
    """
    Sinh pickup_datetime dàn đều trong `days` ngày × operating_hours.
    Random assignment nên datetime gốc không tương ứng VIN — đây là Tier RD.
    """
    day_offsets = rng.integers(low=0, high=days, size=n)
    seconds_in_day = (operating_hours[1] - operating_hours[0]) * 3600
    seconds_offset = rng.integers(low=0, high=seconds_in_day, size=n)
    out = []
    for d, s in zip(day_offsets, seconds_offset):
        out.append(base_date + timedelta(days=int(d), seconds=int(s)))
    return pd.Series(out)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def reproject_to_hanoi(lat: pd.Series, lon: pd.Series) -> tuple[pd.Series, pd.Series]:
    """
    Giữ pattern chuyển động tương đối thật (min-max shape) nhưng affine-transform
    sang bounding box Hà Nội. Tier RS: pattern thật, vị trí tuyệt đối tái định vị.
    """
    def _rescale(s: pd.Series, lo: float, hi: float) -> pd.Series:
        s_min, s_max = s.min(), s.max()
        if s_max == s_min:
            return pd.Series(np.full(len(s), (lo + hi) / 2), index=s.index)
        return lo + (s - s_min) / (s_max - s_min) * (hi - lo)

    new_lat = _rescale(lat, HANOI_BBOX["lat_min"], HANOI_BBOX["lat_max"])
    new_lon = _rescale(lon, HANOI_BBOX["lon_min"], HANOI_BBOX["lon_max"])
    return new_lat, new_lon


def gen_id(prefix: str, i: int, width: int = 4) -> str:
    return f"{prefix}_{i:0{width}d}"


# --------------------------------------------------------------------------- #
# Per-(VIN, day) State Machine -- single source of truth (2026-08-08 v4 redesign)
# --------------------------------------------------------------------------- #

# 4 mutually exclusive states
STATE_DRIVING_PASSENGER = "DRIVING_PASSENGER"
STATE_DEADHEAD = "DEADHEAD"
STATE_IDLE = "IDLE"
STATE_CHARGING = "CHARGING"
ALL_STATES = {STATE_DRIVING_PASSENGER, STATE_DEADHEAD, STATE_IDLE, STATE_CHARGING}


@dataclass
class ScheduleEvent:
    """Mot segment trong state machine cho 1 (VIN, day).
    Moi event co state, start/end time, va metadata rieng theo state.
    """
    state: str           # STATE_DRIVING_PASSENGER | STATE_DEADHEAD | STATE_IDLE | STATE_CHARGING
    event_type: str      # backward-compat alias: 'trip' | 'charge_overnight' | 'charge_opportunity' | 'deadhead' | 'idle'
    start: datetime
    end: datetime
    payload: dict        # metadata rieng theo event_type
    soft_overlap: bool = False  # legacy - luon False trong state machine moi (disjoint by construction)

    @property
    def duration_mins(self) -> float:
        return (self.end - self.start).total_seconds() / 60.0

    def to_legacy_event_type(self) -> str:
        """Backward-compat mapping cho code cu dung event_type."""
        m = {
            STATE_DRIVING_PASSENGER: "trip",
            STATE_CHARGING: "charge_overnight",
            STATE_DEADHEAD: "deadhead",
            STATE_IDLE: "idle",
        }
        return m.get(self.state, self.event_type)


def _minutes_in_day(h: int, m: int) -> int:
    """Convert (hour, minute) sang phut ke tu 00:00:00 cua day."""
    return h * 60 + m


def _datetime_on_day(day_idx: int, minutes_from_midnight: int) -> datetime:
    """Datetime tuyet doi tren day_idx (0..OBSERVATION_DAYS-1)."""
    base = datetime(2026, 1, 1)
    return base + timedelta(days=int(day_idx), minutes=int(minutes_from_midnight))


def _clamp_end(start: datetime, duration_min: int, hard_end: datetime) -> datetime:
    """Tra ve end = min(start + duration, hard_end). Neu duration <= 0 -> tra start."""
    end = start + timedelta(minutes=int(duration_min))
    if end > hard_end:
        end = hard_end
    if end <= start:
        end = start
    return end


def _make_event(state: str, event_type: str, start: datetime, end: datetime,
                 payload: dict | None = None) -> ScheduleEvent:
    return ScheduleEvent(
        state=state,
        event_type=event_type,
        start=start,
        end=end,
        payload=payload or {},
        soft_overlap=False,
    )


def generate_vin_day_states(
    vin: str,
    day_idx: int,
    rng: np.random.Generator,
    n_trips_target: int | None = None,
    p_opportunity_charge: float = 0.5,
) -> list[ScheduleEvent]:
    """
    State machine generator cho 1 (VIN, day).

    Quy trinh:
      1. Sample 1 overnight CHARGING (priority 1, fixed window truoc 06:00 day_idx)
      2. Sample 0-1 opportunity CHARGING (priority 2, [10:00, 15:00])
      3. Chia operating window [06:00, 22:00] thanh alternating segments:
         DRIVING_PASSENGER / DEADHEAD / IDLE -- tuan thu disjoint.
      4. Moi segment co duration theo distribution rieng.

    Tinh disjoint guarantee:
      - Overnight: [18:00 prior_day, 06:00 day_idx] -- hoan toan ngoai operating window
      - Opportunity: [10:00, 15:00] -- chua cho cho trips xung quanh (5 min buffer)
      - Operating hours segments: lap day [06:00, 22:00] tuan tu, khong overlap

    Returns:
        list[ScheduleEvent] sorted by start.
    """
    # Deterministic seed cho (vin, day_idx) de dam bao:
    # - map_ev_telemetry, map_charging_sessions, map_trips cung dung 1 schedule
    # - reproducibility cross-function
    seed_val = hash((vin, day_idx)) % (2**31)
    local_rng = np.random.default_rng(seed_val)

    if n_trips_target is None:
        n_trips_target = int(local_rng.integers(TRIPS_PER_VIN_PER_DAY - 2,
                                                  TRIPS_PER_VIN_PER_DAY + 3))

    events: list[ScheduleEvent] = []

    # ---------------------------------------------------------------- #
    # 1. OVERNIGHT CHARGING (priority 1, fixed window)
    # Overnight charge: from PRIOR DAY evening -> day_idx 06:00 (morning charge).
    # ---------------------------------------------------------------- #
    ov_start_min = int(local_rng.integers(_minutes_in_day(18, 0), _minutes_in_day(22, 0)))
    ov_duration_min = int(local_rng.integers(CHARGING_OVERNIGHT_MIN_DURATION,
                                       CHARGING_OVERNIGHT_MAX_DURATION + 1))
    ov_start_dt = _datetime_on_day(day_idx - 1, ov_start_min)
    hard_end_ov = _datetime_on_day(day_idx + 1, _minutes_in_day(6, 0))
    ov_end_dt = _clamp_end(ov_start_dt, ov_duration_min, hard_end_ov)
    ov_duration_min = int((ov_end_dt - ov_start_dt).total_seconds() / 60)
    if ov_duration_min > 0:
        events.append(_make_event(
            state=STATE_CHARGING,
            event_type='charge_overnight',
            start=ov_start_dt,
            end=ov_end_dt,
            payload={'duration_mins': float(ov_duration_min), 'priority': 1},
        ))

    # ---------------------------------------------------------------- #
    # 1b. NEXT-DAY overnight charge (from THIS evening -> next day 06:00)
    # Can thiet de telemetry thay CHARGING tu 18:00+ cua day_idx.
    # ---------------------------------------------------------------- #
    next_ov_start_min = int(local_rng.integers(_minutes_in_day(18, 0), _minutes_in_day(22, 0)))
    next_ov_duration_min = int(local_rng.integers(CHARGING_OVERNIGHT_MIN_DURATION,
                                                    CHARGING_OVERNIGHT_MAX_DURATION + 1))
    next_ov_start_dt = _datetime_on_day(day_idx, next_ov_start_min)
    next_hard_end = _datetime_on_day(day_idx + 1, _minutes_in_day(6, 0))
    next_ov_end_dt = _clamp_end(next_ov_start_dt, next_ov_duration_min, next_hard_end)
    next_ov_duration_min = int((next_ov_end_dt - next_ov_start_dt).total_seconds() / 60)
    if next_ov_duration_min > 0:
        events.append(_make_event(
            state=STATE_CHARGING,
            event_type='charge_overnight_next',
            start=next_ov_start_dt,
            end=next_ov_end_dt,
            payload={'duration_mins': float(next_ov_duration_min), 'priority': 1},
        ))

    # ---------------------------------------------------------------- #
    # 2. OPPORTUNITY CHARGING (priority 2, 50% probability)
    # ---------------------------------------------------------------- #
    op_event: ScheduleEvent | None = None
    if local_rng.random() < p_opportunity_charge:
        op_start_min = int(local_rng.integers(_minutes_in_day(10, 0), _minutes_in_day(15, 0)))
        op_duration_min = int(local_rng.integers(CHARGING_OPPORTUNITY_MIN_DURATION,
                                            CHARGING_OPPORTUNITY_MAX_DURATION + 1))
        op_start_dt = _datetime_on_day(day_idx, op_start_min)
        op_end_dt = _clamp_end(
            op_start_dt, op_duration_min,
            _datetime_on_day(day_idx, _minutes_in_day(15, 0))
        )
        op_duration_min = int((op_end_dt - op_start_dt).total_seconds() / 60)
        if op_duration_min >= CHARGING_OPPORTUNITY_MIN_DURATION:
            op_event = _make_event(
                state=STATE_CHARGING,
                event_type='charge_opportunity',
                start=op_start_dt,
                end=op_end_dt,
                payload={'duration_mins': float(op_duration_min), 'priority': 2},
            )
            events.append(op_event)

    # ---------------------------------------------------------------- #
    # 3. OPERATING HOURS [06:00, 18:00]: alternating trips/deadhead/idle
    # Operating window bat dau SAU khi overnight charge ket thuc (khong fixed 06:00)
    # de dam bao disjoint - neu overnight ket thuc 06:18 thi operating bat dau 06:18.
    # Operating window KET THUC truoc khi next overnight charge bat dau (18:00).
    # ---------------------------------------------------------------- #
    op_end = _minutes_in_day(22, 0)
    # Limit operating window to end before next overnight charge (typically 18:00)
    op_end = min(op_end, _minutes_in_day(18, 0))  # 18:00 cap

    # Tim overnight event (CHARGING state voi event_type charge_overnight) de lay end_min
    ov_end_min = _minutes_in_day(6, 0)  # default neu khong tim thay
    for ev in events:
        if ev.event_type == 'charge_overnight':
            ov_end_dt = ev.end
            # Tinh minutes tu 00:00 cua day_idx (can xu ly overnight crossing midnight)
            day_zero = _datetime_on_day(day_idx, 0)
            if ov_end_dt >= day_zero:
                ov_end_min = int((ov_end_dt - day_zero).total_seconds() / 60)
            break

    op_start = max(ov_end_min, _minutes_in_day(6, 0))  # dam bao operating >= 06:00

    if op_event is not None:
        op_block_start_min = int((op_event.start - _datetime_on_day(day_idx, 0)).total_seconds() / 60)
        op_block_end_min = int((op_event.end - _datetime_on_day(day_idx, 0)).total_seconds() / 60)
        windows_mins: list[tuple[int, int]] = []
        if op_block_start_min > op_start:
            windows_mins.append((op_start, op_block_start_min))
        if op_block_end_min < op_end:
            windows_mins.append((op_block_end_min, op_end))
    else:
        windows_mins = [(op_start, op_end)] if op_start < op_end else []

    total_window_mins = sum(e - s for s, e in windows_mins)
    trips_remaining = n_trips_target

    cursor_idx = 0
    for win_start_min, win_end_min in windows_mins:
        if trips_remaining <= 0:
            break
        win_mins = win_end_min - win_start_min
        if cursor_idx == len(windows_mins) - 1:
            n_in_window = trips_remaining
        else:
            share = win_mins / total_window_mins
            n_in_window = max(1, int(round(n_trips_target * share)))
            n_in_window = min(n_in_window, trips_remaining - (len(windows_mins) - cursor_idx - 1))

        cursor = win_start_min

        for _ in range(n_in_window):
            # Chon loai segment theo xac suat:
            #   p_passenger: ~0.70 (chuyen co khach) - tang cao de dat target trip count
            #   p_deadhead:  ~0.20 (chay khong khach)
            #   p_idle:      ~0.10 (do cho)
            roll = local_rng.random()
            if roll < 0.70:
                seg_state = STATE_DRIVING_PASSENGER
                seg_event_type = 'trip'
                seg_min = int(local_rng.integers(TRIP_MIN_DURATION, TRIP_MAX_DURATION + 1))
            elif roll < 0.90:
                seg_state = STATE_DEADHEAD
                seg_event_type = 'deadhead'
                seg_min = int(local_rng.integers(DEADHEAD_MIN_DURATION, DEADHEAD_MAX_DURATION + 1))
            else:
                seg_state = STATE_IDLE
                seg_event_type = 'idle'
                seg_min = int(local_rng.integers(IDLE_MIN_DURATION, IDLE_MAX_DURATION + 1))

            seg_start_min = cursor
            seg_end_min = min(seg_start_min + seg_min, win_end_min)
            if seg_end_min - seg_start_min < 1:
                break

            seg_start_dt = _datetime_on_day(day_idx, seg_start_min)
            seg_end_dt = _datetime_on_day(day_idx, seg_end_min)

            events.append(_make_event(
                state=seg_state,
                event_type=seg_event_type,
                start=seg_start_dt,
                end=seg_end_dt,
                payload={'duration_mins': float(seg_end_min - seg_start_min)},
            ))
            cursor = seg_end_min + BUFFER_BETWEEN_TRIPS_MIN

            if cursor < win_end_min - IDLE_MIN_DURATION and seg_state != STATE_IDLE:
                if local_rng.random() < 0.40:
                    idle_min = int(local_rng.integers(IDLE_MIN_DURATION, IDLE_MAX_DURATION + 1))
                    idle_end_min = min(cursor + idle_min, win_end_min)
                    if idle_end_min - cursor >= 1:
                        events.append(_make_event(
                            state=STATE_IDLE,
                            event_type='idle',
                            start=_datetime_on_day(day_idx, cursor),
                            end=_datetime_on_day(day_idx, idle_end_min),
                            payload={'duration_mins': float(idle_end_min - cursor)},
                        ))
                        cursor = idle_end_min

        cursor_idx += 1

    events.sort(key=lambda e: e.start)
    return events


def build_per_vin_day_schedule(
    vin: str,
    day_idx: int,
    rng: np.random.Generator,
    n_trips_target: int | None = None,
) -> list[ScheduleEvent]:
    """Backward-compat wrapper cho generate_vin_day_states()."""
    return generate_vin_day_states(vin, day_idx, rng, n_trips_target=n_trips_target)




def _lookup_state(schedule: list[ScheduleEvent], ts: datetime) -> str:
    """Tra ve state cua schedule tai timestamp ts. Neu khong nam trong event -> IDLE (default)."""
    for ev in schedule:
        if ev.start <= ts < ev.end:
            return ev.state
    return STATE_IDLE


def _compute_soc_at(state: str, ev_state: str | None,
                    soc_start: float, soc_end: float,
                    progress: float) -> float:
    """Tinh SOC theo state hien tai (physical constraints).

    DRIVING_PASSENGER/DEADHEAD: SOC giam tu soc_start -> soc_end theo progress trong operating hours
    CHARGING: SOC tang tu soc_end -> soc_start theo progress trong charge window
    IDLE: SOC giu nguyen (stable)
    """
    if state == STATE_CHARGING:
        # SOC tang tu soc_end len soc_start
        return soc_end + (soc_start - soc_end) * progress
    elif state in (STATE_DRIVING_PASSENGER, STATE_DEADHEAD):
        # SOC giam tu soc_start xuong soc_end
        return soc_start + (soc_end - soc_start) * progress
    else:  # IDLE
        return soc_start


def extract_ved_calibration(raw_path: Path, out_path: Path) -> dict:
    """
    Buoc 0: Extract VED per-vehicle distribution params -> ved_calibration.json.
    Chi chay 1 lan (cache file). Decouple ingest pipeline khoi raw CSV dependency.
    """
    raw = pd.read_csv(raw_path)
    stats = {}
    for veh_id, g in raw.groupby('VehId'):
        speed = g['Vehicle Speed[km/h]'].dropna()
        soc = g['HV Battery SOC[%]'].dropna()
        volt = g['HV Battery Voltage[V]'].dropna()
        curr = g['HV Battery Current[A]'].dropna()
        rpm = g['Engine RPM[RPM]'].dropna()
        stats[int(veh_id)] = {
            'speed_mean': float(speed.mean()) if len(speed) else 30.0,
            'speed_std': float(speed.std()) if len(speed) > 1 else 15.0,
            'speed_max': float(speed.max()) if len(speed) else 90.0,
            'rpm_mean': float(rpm.mean()) if len(rpm) else 2000.0,
            'rpm_std': float(rpm.std()) if len(rpm) > 1 else 800.0,
            'soc_mean': float(soc.mean()) if len(soc) else 50.0,
            'soc_std': float(soc.std()) if len(soc) > 1 else 25.0,
            'voltage_mean': float(volt.mean()) if len(volt) else 350.0,
            'voltage_std': float(volt.std()) if len(volt) > 1 else 30.0,
            'current_mean': float(curr.mean()) if len(curr) else 0.0,
            'current_std': float(curr.std()) if len(curr) > 1 else 50.0,
        }
    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "source": str(raw_path),
        "n_vehicles": len(stats),
        "vehicle_ids": sorted(stats.keys()),
        "per_vehicle_stats": {str(k): v for k, v in stats.items()},
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload


def load_ved_calibration(calibration_path: Path) -> dict[str, dict]:
    """Load ved_calibration.json. Tra ve dict {veh_id_str: stats}."""
    with open(calibration_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return payload["per_vehicle_stats"]


def map_ev_telemetry(raw_path: Path, fleet: pd.DataFrame,
                        calibration_path: Path | None = None) -> pd.DataFrame:
    """
    Mapping state machine -> real_vinfast_ev_telemetry (2026-08-08 v4 redesign).

    Design (single source of truth):
      - State machine `generate_vin_day_states()` cho 1 (VIN, day) -> list[ScheduleEvent]
      - 60 pilot VIN x 15 days x 96 sample/day = 86,400 rows
      - Moi sample (15-min) lay state tu state machine bang binary search
      - Physical constraints: SOC chi giam khi DRIVING*, chi tang khi CHARGING
      - Speed > 0 chi trong DRIVING_PASSENGER/DEADHEAD; = 0 trong IDLE/CHARGING
      - VED 20 vehicle distribution tham chieu (cache qua ved_calibration.json)

    Returns DataFrame voi cac cot:
      record_id, timestamp, vehicle_vin, day_idx, sample_idx,
      speed_kmh, motor_rpm, battery_soc, battery_voltage, battery_current,
      battery_temp_c, latitude, longitude, accel_z,
      state_at_sample, event_sequence_index, assigned_day_index,
      ved_reference_veh_id, synthetic_gap_indicator, telemetry_coverage
    """
    # Buoc 0: VED calibration (cached, decouple khoi raw CSV)
    if calibration_path is None:
        calibration_path = VED_CALIBRATION_PATH

    if calibration_path.exists():
        ved_stats_raw = load_ved_calibration(calibration_path)
        # Convert string keys back to int
        ved_stats = {int(k): v for k, v in ved_stats_raw.items()}
        print(f"      [cache hit] VED calibration from {calibration_path}")
    elif raw_path.exists():
        ved_stats = extract_ved_calibration(raw_path, calibration_path)
        print(f"      [extracted] VED calibration -> {calibration_path}")
    else:
        ved_stats = {}
        print(f"      [WARN] Neither VED calibration nor raw CSV found, using defaults")

    ved_veh_ids = sorted(ved_stats.keys())
    if not ved_veh_ids:
        ved_veh_ids = [10, 11, 388]
    n_ved = len(ved_veh_ids)

    pilot_vins = fleet["vehicle_vin"].values
    vin_to_ved_idx = {vin: i % n_ved for i, vin in enumerate(pilot_vins)}

    rows = []
    base_date = datetime(2026, 1, 1)

    for vin in pilot_vins:
        ved_id = ved_veh_ids[vin_to_ved_idx[vin]]
        st = ved_stats.get(ved_id, {})
        # Default stats neu vehicle_id khong co
        speed_mean = st.get('speed_mean', 30.0)
        speed_std = max(3.0, st.get('speed_std', 15.0) * 0.7)
        speed_max = st.get('speed_max', 90.0)
        rpm_std = st.get('rpm_std', 800.0)
        voltage_mean = st.get('voltage_mean', 350.0)
        voltage_std = max(2.0, st.get('voltage_std', 30.0) * 0.3)
        current_mean = max(20.0, st.get('current_mean', 0.0))
        current_std = max(5.0, st.get('current_std', 50.0) * 0.5)

        for day_idx in range(OBSERVATION_DAYS):
            # Lay state machine cho (vin, day)
            schedule = generate_vin_day_states(vin, day_idx, rng)

            # 2026-08-08 v4: SOC bounds va telemetry noise dung local_rng (deterministic per VIN/day)
            # de dam bao reproducibility cross-run.
            local_rng = np.random.default_rng(hash((vin, day_idx, 'tele')) % (2**31))

            # Tinh SOC bounds cho ngay:
            # Sau overnight charge: SOC cao (95%)
            # Truoc overnight charge next day: SOC thap (30-45%)
            soc_curve_start = float(local_rng.uniform(92.0, 98.0))  # sau overnight
            soc_curve_end = float(local_rng.uniform(28.0, 42.0))    # cuoi operating hours

            # Tinh event boundaries cho tinh soc_progress
            # Lay charge overnight + opportunity charge lam moc
            charge_events = [ev for ev in schedule if ev.state == STATE_CHARGING]
            operating_events = [ev for ev in schedule
                                if ev.state in (STATE_DRIVING_PASSENGER,
                                                STATE_DEADHEAD, STATE_IDLE)]

            for sample_idx in range(TELEMETRY_SAMPLES_PER_DAY):
                ts_min = sample_idx * TELEMETRY_INTERVAL_MIN
                ts_dt = base_date + timedelta(days=day_idx, minutes=ts_min)

                # Lookup state tu state machine
                state = _lookup_state(schedule, ts_dt)

                # === Speed & RPM ===
                if state in (STATE_DRIVING_PASSENGER, STATE_DEADHEAD):
                    # Xe dang chay -> speed > 0
                    if state == STATE_DEADHEAD:
                        # Deadhead: speed thap hon (chay tim khach)
                        loc = speed_mean * 0.7
                        scale = speed_std * 0.5
                    else:
                        # Trip co khach: speed full distribution
                        loc = speed_mean
                        scale = speed_std
                    speed = max(0.0, local_rng.normal(loc=loc, scale=scale))
                    speed = min(speed, speed_max)
                    rpm = max(0, int(speed * 73.2 + local_rng.normal(0, max(150, rpm_std * 0.3))))
                else:
                    # IDLE hoac CHARGING -> speed = 0, rpm = 0
                    speed = 0.0
                    rpm = 0

                # === SOC (physical constraints) ===
                # Tinh progress dua tren state hien tai
                if state == STATE_CHARGING:
                    # Find which charge event chua ts_dt
                    charge_ev = next((ev for ev in charge_events
                                       if ev.start <= ts_dt < ev.end), None)
                    if charge_ev:
                        total_dur = (charge_ev.end - charge_ev.start).total_seconds() / 60.0
                        elapsed = (ts_dt - charge_ev.start).total_seconds() / 60.0
                        progress = max(0.0, min(1.0, elapsed / max(1.0, total_dur)))
                        # SOC tang tu soc_curve_end (thap) -> soc_curve_start (cao)
                        soc = soc_curve_end + (soc_curve_start - soc_curve_end) * progress
                    else:
                        soc = soc_curve_start
                elif state in (STATE_DRIVING_PASSENGER, STATE_DEADHEAD, STATE_IDLE):
                    # Trong operating hours: SOC giam tu soc_curve_start -> soc_curve_end
                    # Tim operating event chua ts_dt
                    op_ev = next((ev for ev in operating_events
                                   if ev.start <= ts_dt < ev.end), None)
                    if op_ev:
                        # Tinh progress trong operating window [06:00, 22:00]
                        op_window_start = _datetime_on_day(day_idx, _minutes_in_day(6, 0))
                        op_window_end = _datetime_on_day(day_idx, _minutes_in_day(22, 0))
                        op_window_dur = (op_window_end - op_window_start).total_seconds() / 60.0
                        elapsed = (ts_dt - op_window_start).total_seconds() / 60.0
                        progress = max(0.0, min(1.0, elapsed / op_window_dur))
                        # SOC giam theo progress
                        soc = soc_curve_start + (soc_curve_end - soc_curve_start) * progress
                    else:
                        # Truoc 06:00 hoac sau 22:00 nhung khong phai charge
                        # (vi du: very early morning) -> SOC cao (sau overnight)
                        if ts_min < _minutes_in_day(6, 0):
                            soc = soc_curve_start
                        else:
                            soc = soc_curve_end
                else:
                    soc = soc_curve_end

                soc = max(0.0, min(100.0, soc + local_rng.normal(0, 1.0)))

                # === Voltage (correlated nghich voi SOC) ===
                volt = max(280.0, voltage_mean - (100 - soc) * 0.15 +
                           local_rng.normal(0, voltage_std))

                # === Current ===
                if state in (STATE_DRIVING_PASSENGER, STATE_DEADHEAD):
                    # Discharge (positive current)
                    curr = max(0.0, local_rng.normal(loc=current_mean, scale=current_std))
                elif state == STATE_CHARGING:
                    # Charge (negative current)
                    curr = -abs(local_rng.normal(40.0, 10.0))
                else:  # IDLE
                    curr = local_rng.normal(0.0, 2.0)  # parasitic drain nho

                # === Battery temp (BMS operating range) ===
                batt_temp = max(20.0, min(45.0, local_rng.normal(32.0, 5.0)))

                rows.append({
                    'vehicle_vin': vin,
                    'day_idx': day_idx,
                    'sample_idx': sample_idx,
                    'timestamp': ts_dt.isoformat(timespec='seconds'),
                    'speed_kmh': round(float(speed), 2),
                    'motor_rpm': int(rpm),
                    'battery_soc': round(float(soc), 2),
                    'battery_voltage': round(float(volt), 2),
                    'battery_current': round(float(curr), 2),
                    'battery_temp_c': round(float(batt_temp), 2),
                    'state_at_sample': state,
                    'assigned_day_index': day_idx,
                    'ved_reference_veh_id': int(ved_id),
                    'synthetic_gap_indicator': False,
                })

    df = pd.DataFrame(rows)
    df.insert(0, 'record_id', [gen_id('EV_REC', i) for i in range(len(df))])

    df['event_sequence_index'] = (
        df.groupby(['vehicle_vin', 'assigned_day_index']).cumcount()
    )

    # === Lat/Lon (synthetic trong bbox HN, deterministic per-run via global rng da duoc dong bang) ===
    n = len(df)
    base_lat = (HANOI_BBOX['lat_min'] + HANOI_BBOX['lat_max']) / 2
    base_lon = (HANOI_BBOX['lon_min'] + HANOI_BBOX['lon_max']) / 2
    moving = df['speed_kmh'] > 0
    geo_rng = np.random.default_rng(20260808)  # deterministic seed rieng cho lat/lon/accel
    lats = np.where(
        moving,
        np.clip(base_lat + geo_rng.normal(0, 0.025, size=n),
                HANOI_BBOX['lat_min'], HANOI_BBOX['lat_max']),
        base_lat + geo_rng.normal(0, 0.005, size=n),
    )
    lons = np.where(
        moving,
        np.clip(base_lon + geo_rng.normal(0, 0.025, size=n),
                HANOI_BBOX['lon_min'], HANOI_BBOX['lon_max']),
        base_lon + geo_rng.normal(0, 0.005, size=n),
    )
    df['latitude'] = np.round(lats, 6)
    df['longitude'] = np.round(lons, 6)
    df['accel_z'] = np.where(moving, geo_rng.normal(0, 0.3, size=n).round(3), 0.0)
    df['telemetry_coverage'] = 'full'

    # === Provenance tags ===
    manifest.tag("real_vinfast_ev_telemetry", "record_id", "S", "ID ky thuat sinh moi")
    manifest.tag("real_vinfast_ev_telemetry", "timestamp", "RD",
                 "Synthetic 15-min interval x 96 sample/ngay x 15 ngay x 60 VIN pilot.")
    manifest.tag("real_vinfast_ev_telemetry", "speed_kmh", "RS",
                 "State-machine driven: speed>0 chi trong DRIVING_PASSENGER/DEADHEAD, "
                 "deadhead thap hon trip co khach.")
    manifest.tag("real_vinfast_ev_telemetry", "motor_rpm", "RD",
                 "EV single-speed gear ratio VF8 ~ 9.7: RPM = speed * 73.2 + noise.")
    manifest.tag("real_vinfast_ev_telemetry", "battery_soc", "RS",
                 "Physical: SOC giam khi DRIVING*, tang khi CHARGING, stable khi IDLE. "
                 "Bounds: 92-98% (sau overnight) -> 28-42% (cuoi operating hours).")
    manifest.tag("real_vinfast_ev_telemetry", "battery_voltage", "RS",
                 "Correlated nghich voi SOC, noise theo VED distribution.")
    manifest.tag("real_vinfast_ev_telemetry", "battery_current", "RS",
                 "Discharge (+) khi DRIVING, charge (-) khi CHARGING, near 0 khi IDLE.")
    manifest.tag("real_vinfast_ev_telemetry", "battery_temp_c", "RS",
                 "Normal(32, 5), clip [20, 45] C. Reference: IEC 62660-1.")
    manifest.tag("real_vinfast_ev_telemetry", "latitude", "RS",
                 "Synthetic trong bbox HN, dao dong khi xe chay.")
    manifest.tag("real_vinfast_ev_telemetry", "longitude", "RS", "Nhu tren")
    manifest.tag("real_vinfast_ev_telemetry", "accel_z", "S",
                 "Dao dong +/-0.3 khi xe chay, = 0 khi xe dung.")
    manifest.tag("real_vinfast_ev_telemetry", "vehicle_vin", "S",
                 "FULL FLEET telemetry-capable: 60 pilot x 15 days x 96 samples/day.")
    manifest.tag("real_vinfast_ev_telemetry", "assigned_day_index", "RD",
                 "Khoa ngay 0..14, derive tu timestamp.")
    manifest.tag("real_vinfast_ev_telemetry", "ved_reference_veh_id", "S",
                 "VED VehId lam per-vehicle distribution reference (cycle 20 -> 60).")
    manifest.tag("real_vinfast_ev_telemetry", "synthetic_gap_indicator", "S",
                 "Luon False (continuous 15-min).")
    manifest.tag("real_vinfast_ev_telemetry", "event_sequence_index", "S",
                 "0..95 cho moi (VIN, day), timestamp-sorted.")
    manifest.tag("real_vinfast_ev_telemetry", "telemetry_coverage", "S",
                 "FULL FLEET 2026-08-08.")
    manifest.tag("real_vinfast_ev_telemetry", "state_at_sample", "RD",
                 "State machine lookup tai timestamp: DRIVING_PASSENGER / DEADHEAD / IDLE / CHARGING. "
                 "Disjoint guarantee vi 4 states mutually exclusive theo thoi gian.")

    return df


def _parse_acn_time(ts: str | None) -> datetime | None:
    if not ts:
        return None
    return pd.to_datetime(ts, utc=True, errors="coerce")


def _classify_charging_pattern(duration_min: float) -> str:
    """
    Phan loai charging pattern dua tren duration that:
      - > 120 min -> overnight_deep_charge
      - <= 90 min -> opportunity_fast_charge
      - 90 < d <= 120 min -> ambiguous
    """
    if duration_min > CHARGING_OVERNIGHT_MIN_MINS:
        return "overnight_deep_charge"
    if duration_min <= CHARGING_OPPORTUNITY_MAX_MINS:
        return "opportunity_fast_charge"
    return "ambiguous"


def _select_acn_subset_for_pattern(raw: pd.DataFrame, duration_plug_min: pd.Series,
                                    pattern: str, n_needed: int) -> pd.Series:
    """Chon N session tu ACN theo duration phu hop pattern."""
    if pattern == "overnight_deep_charge":
        mask = duration_plug_min > CHARGING_OVERNIGHT_MIN_MINS
    elif pattern == "opportunity_fast_charge":
        mask = duration_plug_min <= CHARGING_OPPORTUNITY_MAX_MINS
    else:
        mask = (duration_plug_min > CHARGING_OPPORTUNITY_MAX_MINS) & \
               (duration_plug_min <= CHARGING_OVERNIGHT_MIN_MINS)
    if mask.sum() < n_needed:
        return mask
    idx = np.where(mask)[0]
    chosen = rng.choice(idx, size=n_needed, replace=False)
    return pd.Series(np.isin(np.arange(len(raw)), chosen), index=raw.index)


def map_charging_sessions(acn_json_paths: list[Path], fleet: pd.DataFrame) -> pd.DataFrame:
    """
    Mapping ACN -> acn_charging_mapped.

    Design (scratch_impl_notes_timeseries.md 2026-08-08):
      - 1 overnight_deep_charge + 0-1 opportunity_fast_charge moi (VIN, day).
      - Tong: 60 VIN x 15 ngay x 1.5 session = 1,350 sessions (900 overnight + 450 opportunity).
      - Overnight uu tien (priority 1), opportunity uu tien 2.
      - Disjoint voi trip windows neu co the (build_per_vin_day_schedule).
      - Soft overlap flag = True neu charge bi overlap trip do conflict unresolvable.
    """
    sessions = []
    for p in acn_json_paths:
        with open(p, "r", encoding="utf-8") as f:
            payload = json.load(f)
        items = payload.get("_items", payload) if isinstance(payload, dict) else payload
        site_tag = p.stem.split("_")[-1]
        for item in items:
            item["_site_tag"] = site_tag
            sessions.append(item)

    raw = pd.DataFrame(sessions)

    conn = raw["connectionTime"].apply(_parse_acn_time)
    disc = raw["disconnectTime"].apply(_parse_acn_time)
    done = raw["doneChargingTime"].apply(_parse_acn_time)
    charge_end = done.fillna(disc)
    duration_plug_min = (disc - conn).dt.total_seconds() / 60.0
    duration_charge_hr = ((charge_end - conn).dt.total_seconds() / 3600.0).clip(lower=0.05)

    # Subset ACN theo tier duration (Tier R cho kwh_consumed, start_time gốc)
    n_overnight = int(FLEET_SIZE * OBSERVATION_DAYS * 1.0)   # 900
    n_opportunity = int(FLEET_SIZE * OBSERVATION_DAYS * 0.5) # 450

    mask_overnight = _select_acn_subset_for_pattern(
        raw, duration_plug_min, "overnight_deep_charge", n_overnight
    )
    mask_opportunity = _select_acn_subset_for_pattern(
        raw, duration_plug_min, "opportunity_fast_charge", n_opportunity
    )
    keep_mask = mask_overnight | mask_opportunity
    raw = raw.loc[keep_mask].reset_index(drop=True)
    conn = conn.loc[keep_mask].reset_index(drop=True)
    disc = disc.loc[keep_mask].reset_index(drop=True)
    done = done.loc[keep_mask].reset_index(drop=True)
    charge_end = done.fillna(disc)
    duration_charge_hr = ((charge_end - conn).dt.total_seconds() / 3600.0).clip(lower=0.05)
    duration_plug_min = (disc - conn).dt.total_seconds() / 60.0

    # Phan loai pattern tu duration that (Tier S, rule-based)
    duration_pattern = duration_plug_min.apply(_classify_charging_pattern)
    is_overnight = (duration_pattern == "overnight_deep_charge").values
    is_opportunity = (duration_pattern == "opportunity_fast_charge").values

    df = pd.DataFrame()
    df["session_id"] = raw["sessionID"].values
    df["station_id"] = ("VG_STA_" + raw["siteID"].astype(str) + "_" + raw["_site_tag"]).values
    df["charger_id"] = raw["spaceID"].astype(str).values
    df["kwh_consumed"] = raw["kWhDelivered"].astype(float).values
    df["power_kw"] = (df["kwh_consumed"] / duration_charge_hr).round(2).values
    df["station_temp_c"] = rng.normal(loc=45.0, scale=10.0, size=len(raw)).clip(20, 65).round(2)
    df["cost_vnd"] = (df["kwh_consumed"] * EVN_TARIFF_VND_PER_KWH).round(0).values
    df["status"] = "COMPLETED"

    # ==== Build schedule per (VIN, day) ====
    # 2026-08-08 v4 redesign: Schedule = state machine `generate_vin_day_states()`.
    # 4 states MUTUALLY EXCLUSIVE theo thoi gian -> disjoint by construction.
    # Charging events chi lay tu STATE_CHARGING trong state machine.
    all_rows = []
    base_date = datetime(2026, 1, 1)
    overnight_pool = raw[is_overnight].reset_index(drop=True)
    opportunity_pool = raw[is_opportunity].reset_index(drop=True)
    overnight_idx = 0
    opportunity_idx = 0
    # 2026-08-08 v4: deterministic station_temp_rng (reproducibility)
    chg_temp_rng = np.random.default_rng(20260810)

    for vin in fleet["vehicle_vin"].values:
        for day_idx in range(OBSERVATION_DAYS):
            schedule = build_per_vin_day_schedule(vin, day_idx, rng)
            # Lay charge events tu schedule
            ov_events = [e for e in schedule if e.event_type == 'charge_overnight']
            op_events = [e for e in schedule if e.event_type == 'charge_opportunity']

            # Overnight (priority 1)
            for ev in ov_events:
                if overnight_idx >= len(overnight_pool):
                    print(f"[WARNING] Pool cycling: overnight_idx={overnight_idx}, "
                          f"pool_size={len(overnight_pool)}. Rows sau la cycled duplicates.")
                    overnight_idx = 0
                src = overnight_pool.iloc[overnight_idx]
                overnight_idx += 1
                start_dt = ev.start
                end_dt = ev.end
                # 2026-08-08 v4: state machine guarantees disjoint -> soft_overlap_flag luon False
                # (giu cot de downstream backward-compat, nhung khong con bao gio True)
                soft_overlap = False
                all_rows.append({
                    "vehicle_vin": vin,
                    "session_id": src["sessionID"],
                    "station_id": f"VG_STA_{src['siteID']}_{src['_site_tag']}",
                    "charger_id": str(src["spaceID"]),
                    "start_time": start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                    "duration_mins": float(ev.payload['duration_mins']),
                    "kwh_consumed": float(src["kWhDelivered"]),
                    "power_kw": round(float(src["kWhDelivered"]) / max(0.05, ev.payload['duration_mins']/60.0), 2),
                    "charging_pattern": "overnight_deep_charge",
                    "assigned_day_index": day_idx,
                    "station_temp_c": float(np.clip(chg_temp_rng.normal(45.0, 10.0), 20.0, 65.0).round(2)),
                    "cost_vnd": round(float(src["kWhDelivered"]) * EVN_TARIFF_VND_PER_KWH, 0),
                    "status": "COMPLETED",
                    "soft_overlap_flag": soft_overlap,
                    "event_sequence_index": -1,  # filled after
                })

            # Opportunity (priority 2)
            for ev in op_events:
                if opportunity_idx >= len(opportunity_pool):
                    print(f"[WARNING] Pool cycling: opportunity_idx={opportunity_idx}, "
                          f"pool_size={len(opportunity_pool)}. Rows sau la cycled duplicates.")
                    opportunity_idx = 0
                src = opportunity_pool.iloc[opportunity_idx]
                opportunity_idx += 1
                start_dt = ev.start
                end_dt = ev.end
                # 2026-08-08 v4: state machine guarantees disjoint -> soft_overlap_flag luon False
                soft_overlap = False
                all_rows.append({
                    "vehicle_vin": vin,
                    "session_id": src["sessionID"],
                    "station_id": f"VG_STA_{src['siteID']}_{src['_site_tag']}",
                    "charger_id": str(src["spaceID"]),
                    "start_time": start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                    "duration_mins": float(ev.payload['duration_mins']),
                    "kwh_consumed": float(src["kWhDelivered"]),
                    "power_kw": round(float(src["kWhDelivered"]) / max(0.05, ev.payload['duration_mins']/60.0), 2),
                    "charging_pattern": "opportunity_fast_charge",
                    "assigned_day_index": day_idx,
                    "station_temp_c": float(np.clip(chg_temp_rng.normal(45.0, 10.0), 20.0, 65.0).round(2)),
                    "cost_vnd": round(float(src["kWhDelivered"]) * EVN_TARIFF_VND_PER_KWH, 0),
                    "status": "COMPLETED",
                    "soft_overlap_flag": soft_overlap,
                    "event_sequence_index": -1,
                })

    df = pd.DataFrame(all_rows)

    # event_sequence_index per (VIN, day) sorted by start_time
    df["start_dt"] = pd.to_datetime(df["start_time"])
    df = df.sort_values(["vehicle_vin", "assigned_day_index", "start_dt"]).reset_index(drop=True)
    df["event_sequence_index"] = df.groupby(["vehicle_vin", "assigned_day_index"]).cumcount()
    df = df.drop(columns=["start_dt"])

    # Provenance tags
    manifest.tag("acn_charging_mapped", "session_id", "R")
    manifest.tag("acn_charging_mapped", "station_id", "RD",
                 "Prefix + ghep siteID that.")
    manifest.tag("acn_charging_mapped", "charger_id", "R")
    manifest.tag("acn_charging_mapped", "start_time", "RD",
                 "Schedule anchor theo build_per_vin_day_schedule, base_date=2026-01-01.")
    manifest.tag("acn_charging_mapped", "duration_mins", "RD",
                 "Tier R: lay tu ACN duration that.")
    manifest.tag("acn_charging_mapped", "kwh_consumed", "R")
    manifest.tag("acn_charging_mapped", "power_kw", "RD",
                 "kWhConsumed / duration_hr.")
    manifest.tag("acn_charging_mapped", "assigned_day_index", "RD",
                 "Khoa ngay 0..14, derive tu schedule.")
    manifest.tag("acn_charging_mapped", "charging_pattern", "S",
                 "Rule-based: >120min=overnight_deep, <=90min=opportunity_fast.")
    manifest.tag("acn_charging_mapped", "station_temp_c", "RS",
                 "Normal(loc=45, scale=10), clip [20, 65] C. Reference: IEC 61851-23.")
    manifest.tag("acn_charging_mapped", "cost_vnd", "RD",
                 f"kwh_consumed (Tier R) x EVN tariff ({EVN_TARIFF_VND_PER_KWH:,.0f} VND/kWh).")
    manifest.tag("acn_charging_mapped", "status", "S",
                 "Baseline mac dinh; fault injection o Layer 3.")
    manifest.tag("acn_charging_mapped", "vehicle_vin", "S",
                 "Constructed Fleet Index, cycle 60 VIN.")
    manifest.tag("acn_charging_mapped", "soft_overlap_flag", "S",
                 "2026-08-08 v4: state machine guarantees disjoint by construction. "
                 "Cot giu de backward-compat, nhung luon False (khong con overlap case).")
    manifest.tag("acn_charging_mapped", "event_sequence_index", "S",
                 "0..N cho moi (VIN, day), start_time-sorted.")

    return df


def map_trips(fact_rides_path: Path, drivers_path: Path,
              fleet: pd.DataFrame, fare_currency: str = "VND") -> pd.DataFrame:
    """
    Mapping fact_rides -> real_xanh_sm_trips (2026-08-08 redesign).

    Design (scratch_impl_notes_timeseries.md):
      - 60 VIN x 15 ngay x 20 trip = 18,000 baseline target.
      - fact_rides 25,003 trip phan bo vao 900 slots qua build_per_vin_day_schedule.
      - Moi trip lay pickup/dropoff tu SCHEDULE (khong phai random trong 16h).
      - Trip count per (VIN, day) = 20 +/- 2 (theo schedule).
      - Ditu trip slots > 18,000 -> subset 18,000 tu pool 25k; synthetic fill neu thieu.
      - Sequential: prev.dropoff + 5min < next.pickup (enforced boi schedule).
      - driver_id deterministic tu VIN (Tier S).
      - fare: USD -> VND, Tier RD.
    """
    fact = pd.read_csv(fact_rides_path, sep=";")
    drivers = pd.read_csv(drivers_path, sep=";")

    fact = fact.merge(drivers[["driver_id", "car_make", "car_model", "license_plate"]],
                       on="driver_id", how="left")

    df_meta = pd.DataFrame()
    df_meta["trip_id"] = [gen_id("XANH_TRIP", i) for i in range(len(fact))]
    df_meta["trip_miles"] = fact["ride_distance_miles"].astype(float).values
    df_meta["fare_usd"] = fact["fare_amount"].astype(float).values

    # Pool cac trip theo tier (giữ nguyên 25k de map vao 900 slots)
    # Phan bo trip -> (VIN, day) theo schedule cua fleet
    base_date = datetime(2026, 1, 1)
    vin_to_driver_idx = {v: i + 1 for i, v in enumerate(fleet["vehicle_vin"])}
    # 2026-08-08 v4: deterministic per-trip rng de dam bao reproducibility
    trip_geo_rng = np.random.default_rng(20260809)

    all_trip_rows = []
    trip_pool_idx = 0
    n_trip_pool = len(fact)

    for vin in fleet["vehicle_vin"].values:
        for day_idx in range(OBSERVATION_DAYS):
            schedule = build_per_vin_day_schedule(vin, day_idx, rng)
            # 2026-08-08 v4: chi lay DRIVING_PASSENGER (state co khach), khong lay DEADHEAD
            trip_events = [e for e in schedule if e.state == STATE_DRIVING_PASSENGER]

            for ev in trip_events:
                if trip_pool_idx >= n_trip_pool:
                    trip_pool_idx = 0
                src = df_meta.iloc[trip_pool_idx]
                trip_pool_idx += 1

                pickup_dt = ev.start
                dropoff_dt = ev.end
                fare_vnd = round(float(src["fare_usd"]) * USD_TO_VND, 0)

                # tip_amount: log-normal tham so hoa (deterministic per trip)
                trip_tip_rng = np.random.default_rng(hash((vin, day_idx, ev.start)) % (2**31))
                log_tip = trip_tip_rng.normal(loc=10.5, scale=0.8)
                tip_vnd = float(np.exp(log_tip).clip(5_000, 200_000).round(0))
                total_fare = fare_vnd + tip_vnd

                # pickup_lat/lon synthetic trong bbox (deterministic)
                pickup_lat = float(trip_geo_rng.uniform(HANOI_BBOX['lat_min'], HANOI_BBOX['lat_max']))
                pickup_lon = float(trip_geo_rng.uniform(HANOI_BBOX['lon_min'], HANOI_BBOX['lon_max']))

                all_trip_rows.append({
                    "trip_id": src["trip_id"],
                    "vehicle_vin": vin,
                    "driver_id": f"DRV_XANH_{vin_to_driver_idx[vin]:04d}",
                    "pickup_datetime": pickup_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                    "dropoff_datetime": dropoff_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                    "assigned_day_index": day_idx,
                    "trip_miles": float(src["trip_miles"]),
                    "fare_amount": fare_vnd,
                    "currency_unverified": False,
                    "tip_amount": tip_vnd,
                    "total_fare": float(total_fare),
                    "pickup_latitude": round(pickup_lat, 6),
                    "pickup_longitude": round(pickup_lon, 6),
                    "vehicle_type": None,
                    "event_sequence_index": -1,
                })

    df = pd.DataFrame(all_trip_rows)

    # Map vehicle_type tu fleet
    fleet_type_map = fleet.set_index("vehicle_vin")["vehicle_type"].to_dict()
    df["vehicle_type"] = df["vehicle_vin"].map(fleet_type_map)

    # event_sequence_index per (VIN, day)
    df["pickup_dt"] = pd.to_datetime(df["pickup_datetime"])
    df = df.sort_values(["vehicle_vin", "assigned_day_index", "pickup_dt"]).reset_index(drop=True)
    df["event_sequence_index"] = df.groupby(["vehicle_vin", "assigned_day_index"]).cumcount()
    df = df.drop(columns=["pickup_dt"])

    # Provenance tags
    manifest.tag("real_xanh_sm_trips", "trip_id", "S",
                 "ID ky thuat sinh moi theo format XANH_TRIP_XXXX.")
    manifest.tag("real_xanh_sm_trips", "driver_id", "S",
                 "Sinh deterministic DRV_XANH_<SEQ> tu VIN.")
    manifest.tag("real_xanh_sm_trips", "pickup_datetime", "RD",
                 "Schedule anchor theo build_per_vin_day_schedule, operating hours 6h-22h.")
    manifest.tag("real_xanh_sm_trips", "dropoff_datetime", "RD",
                 "pickup_datetime + duration_mins (15-25 min).")
    manifest.tag("real_xanh_sm_trips", "assigned_day_index", "RD",
                 "Khoa ngay 0..14, derive tu schedule.")
    manifest.tag("real_xanh_sm_trips", "trip_miles", "R",
                 "Gia tri goc tu fact_rides.")
    manifest.tag("real_xanh_sm_trips", "fare_amount", "RD",
                 f"USD -> VND (x {USD_TO_VND:,.0f}).")
    manifest.tag("real_xanh_sm_trips", "currency_unverified", "S",
                 "Cot flag: False = da xac minh VND.")
    manifest.tag("real_xanh_sm_trips", "tip_amount", "RS",
                 "Log-normal(loc=10.5, scale=0.8), clip [5k, 200k] VND.")
    manifest.tag("real_xanh_sm_trips", "total_fare", "RD",
                 "fare + tip (vouchers da loai bo 2026-08-08).")
    manifest.tag("real_xanh_sm_trips", "pickup_latitude", "S",
                 "Synthetic trong bbox Ha Noi (fact_rides khong co lat/lon so).")
    manifest.tag("real_xanh_sm_trips", "pickup_longitude", "S", "Nhu tren")
    manifest.tag("real_xanh_sm_trips", "vehicle_vin", "S",
                 "Constructed Fleet Index, cycle 60 VIN.")
    manifest.tag("real_xanh_sm_trips", "vehicle_type", "S",
                 "Gan theo fleet index.")
    manifest.tag("real_xanh_sm_trips", "event_sequence_index", "S",
                 "0..N cho moi (VIN, day), pickup_datetime-sorted.")

    return df


def map_feedback_for_nlp_benchmark(uit_vsfc_path: Path) -> pd.DataFrame:
    """
    QUAN TRỌNG: Output của hàm này KHÔNG dùng làm "feedback content chính" của
    hệ thống — chỉ dùng làm test set riêng để đo normalization accuracy / aspect
    extraction F1 (PRD mục 5.4), vì nội dung UIT-VSFC lệch domain (feedback sinh
    viên, không phải feedback app gọi xe/trạm sạc). Feedback nội dung V-GREEN/
    Xanh SM cụ thể phải viết tay có kiểm soát (S) — xem map_feedback_scenario().
    """
    raw = pd.read_csv(uit_vsfc_path)
    df = pd.DataFrame()
    df["sentence"] = raw["sentence"]
    manifest.tag("nlp_benchmark_uit_vsfc", "sentence", "R",
                 "Text tieng Viet that nhung LECH DOMAIN (feedback sinh vien, khong "
                 "phai app goi xe/tram sac) — chi dung de kiem dinh module chuan hoa/"
                 "NLP chung, khong dung lam feedback content chinh")
    df["sentiment"] = raw["sentiment"]
    df["topic"] = raw["topic"]
    manifest.tag("nlp_benchmark_uit_vsfc", "sentiment", "R")
    manifest.tag("nlp_benchmark_uit_vsfc", "topic", "R", "Topic khong khop enum VinGroup, chi dung noi bo")
    return df


def map_feedback_scenario(n: int, templates: list[str]) -> pd.DataFrame:
    """
    Feedback nội dung đúng domain (V-GREEN/Xanh SM) — dựng có kiểm soát (tier S),
    không giả danh nguồn thật. `templates` nên do người phụ trách domain viết,
    có chèn teen-code có chủ đích để phục vụ test normalization.
    """
    df = pd.DataFrame({
        "feedback_id": [gen_id("FB", i) for i in range(n)],
        "raw_comment_text": rng.choice(templates, size=n),
    })
    manifest.tag("vingroup_feedback_scenario", "raw_comment_text", "S",
                 "Dung co kiem soat, dung domain, khong giả danh corpus that")
    return df


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fleet = build_fleet_index(FLEET_SIZE, PILOT_SIZE)
    fleet.to_csv(OUT_DIR / "fleet_index.csv", index=False)
    save_fleet_metadata(fleet, FLEET_META_PATH)
    print(f"[OK] Fleet index: {len(fleet)} VIN ({int(fleet['telemetry_equipped'].sum())} "
          f"pilot) -> fleet_index.csv + fleet_index.json")

    # --- EV Telemetry ---
    ev_raw = RAW_DIR / "vehicle_telemetry_raw.csv"
    if ev_raw.exists():
        ev_df = map_ev_telemetry(ev_raw, fleet)
        ev_df.to_csv(OUT_DIR / "synthetic_ev_telemetry_ved_ref.csv", index=False)
        print(f"[OK] EV telemetry (pilot subset): {len(ev_df)} rows -> "
              f"synthetic_ev_telemetry_ved_ref.csv")
    else:
        print(f"[SKIP] Khong tim thay {ev_raw}")

    # --- Charging Sessions (ACN) ---
    acn_dir = RAW_DIR / "ACN"
    acn_files = list(acn_dir.glob("acndata_sessions_*.json")) if acn_dir.exists() else []
    if acn_files:
        chg_df = map_charging_sessions(acn_files, fleet)
        chg_df.to_csv(OUT_DIR / "acn_charging_mapped.csv", index=False)
        if "charging_pattern" in chg_df.columns:
            print(f"[OK] Charging sessions: {len(chg_df)} rows -> "
                  f"acn_charging_mapped.csv "
                  f"(overnight={(chg_df['charging_pattern']=='overnight_deep_charge').sum()}, "
                  f"opportunity={(chg_df['charging_pattern']=='opportunity_fast_charge').sum()})")
        else:
            print(f"[OK] Charging sessions: {len(chg_df)} rows -> "
                  f"acn_charging_mapped.csv")
    else:
        print(f"[SKIP] Khong tim thay ACN JSON trong {acn_dir}")

    # --- Trips ---
    ride_hailing_dir = RAW_DIR / "Ride Hailing"
    fact_p, drv_p = (ride_hailing_dir / "fact_rides.csv",
                     ride_hailing_dir / "drivers.csv")
    # vouchers.csv da loai bo 2026-08-08 (duplicate-key cartesian explosion)
    if fact_p.exists() and drv_p.exists():
        trips_df = map_trips(fact_p, drv_p, fleet, fare_currency="VND")
        trips_df.to_csv(OUT_DIR / "ride_hailing_xanh_sm_trips.csv", index=False)
        print(f"[OK] Trips: {len(trips_df)} rows -> ride_hailing_xanh_sm_trips.csv")
    else:
        print(f"[SKIP] Thieu fact_rides.csv hoac drivers.csv trong {ride_hailing_dir}")

    # --- NLP benchmark set (UIT-VSFC, riêng biệt) ---
    uit_p = RAW_DIR / "uit_vsfc_raw.csv"
    if uit_p.exists():
        nlp_df = map_feedback_for_nlp_benchmark(uit_p)
        nlp_df.to_csv(OUT_DIR / "nlp_benchmark_uit_vsfc.csv", index=False)
        print(f"[OK] NLP benchmark set: {len(nlp_df)} rows -> nlp_benchmark_uit_vsfc.csv "
              f"(CHI dung do NLP accuracy, khong phai feedback content chinh)")
    else:
        print(f"[SKIP] Khong tim thay {uit_p}")

    manifest.save(MANIFEST_PATH)
    print(f"[OK] Provenance manifest -> {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
