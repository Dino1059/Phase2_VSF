"""
Build Lane B PII test set on top of a trips source (days 0..9 = 2026-01-01..10).

Scenarios (ground truth in pii_injection_manifest.json):
  S3 join re-identification: trips.customer_id -> dim_customers / driver_id -> dim_drivers
  S1 PII in uncatalogued column: trips.customer_contact (email/phone on a sample)
  S2 PII in free text: feedback_pii.csv raw_comment_text

Customer linkage: trips.trip_id suffix = row index in fact_rides.csv -> raw customer_id.
Each user belongs to exactly one zone (user_id % 3), raw customer is re-keyed into the
pool of the trip's zone so no customer spans zones.

Two independent outputs, neither overwrites the other:
  (default)  clean trips (no L1-L4 faults) -> vingroup_pii_testset_3zone/         [Lane B only]
  --faulty   trips with F1-F16 injected    -> vingroup_pii_faulty_testset_3zone/  [Lane A + Lane B]
`trip_id` ordering is identical in both trip sources, so the same customer/driver
linkage applies unchanged.
"""
import argparse
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLEAN_DIR = ROOT / "vingroup_clean_3zone_pilot"
FAULTY_DIR = ROOT / "vingroup_pilot_dataset_3zone copy"
RAW_DIR = ROOT / "raw_public" / "Ride Hailing"
CLEAN_OUT_DIR = ROOT / "vingroup_pii_testset_3zone"
FAULTY_OUT_DIR = ROOT / "vingroup_pii_faulty_testset_3zone"

# Faulty-dir files carried over as-is (filtered to the same day window) so the
# merged output is a complete drop-in set for Lane A + Lane B, not trips-only.
FAULTY_DAY_FILTERED_FILES = {
    "synthetic_ev_telemetry_ved_ref.csv": "assigned_day_index",
    "acn_charging_mapped.csv": "assigned_day_index",
    "synthetic_feedback_scenario_driven.csv": "assigned_day_index",
}
FAULTY_COPY_ASIS_FILES = [
    "fleet_index.csv", "fleet_index.json", "zone_manifest.json",
    "fault_manifest.json", "provenance_manifest.json", "ved_calibration.json",
]

MAX_DAY_INDEX = 9
ZONES = ["EU", "VN", "US"]
PII_COLS = ["first_name", "last_name", "email", "phone_number", "created_at"]
S1_RATE = 0.05
S2_ROWS = 30
SEED = 42

S2_TEMPLATES = [
    ("service", "tài xế thái độ kém, liên hệ lại cho tôi qua số {phone}"),
    ("service", "tôi là {first} {last}, bị tính cước sai, email: {email}"),
    ("app", "app không gửi hóa đơn về {email}, nhờ kiểm tra giúp"),
    ("vehicle", "xe có mùi khó chịu, gọi {phone} nếu cần thêm thông tin"),
    ("service", "khách {first} {last} để quên đồ trên xe, sđt {phone}"),
]


def read_raw(name: str) -> pd.DataFrame:
    return pd.read_csv(RAW_DIR / name, sep=";", dtype=str)


def to_date(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, format="%m/%d/%Y")


def copy_faulty_domain_files(out_dir: Path) -> None:
    for name, day_col in FAULTY_DAY_FILTERED_FILES.items():
        df = pd.read_csv(FAULTY_DIR / name)
        df[df[day_col] <= MAX_DAY_INDEX].to_csv(out_dir / name, index=False)
    for name in FAULTY_COPY_ASIS_FILES:
        shutil.copy2(FAULTY_DIR / name, out_dir / name)


def main(trips_dir: Path, out_dir: Path, with_faulty_domain_files: bool) -> None:
    rng = np.random.default_rng(SEED)

    trips = pd.read_csv(trips_dir / "ride_hailing_xanh_sm_trips.csv")
    trips = trips[trips["assigned_day_index"] <= MAX_DAY_INDEX].reset_index(drop=True)
    n_trips = len(trips)

    fact = read_raw("fact_rides.csv")[["customer_id"]]
    users = read_raw("users.csv")[["user_id", *PII_COLS]]
    drivers = read_raw("drivers.csv")[["driver_id", *PII_COLS]]

    # S3a: customers, zone-scoped
    raw_cust = fact["customer_id"].iloc[trips["trip_id"].str.split("_").str[-1].astype(int)]
    trips["_raw_customer_id"] = raw_cust.astype(int).values
    users["user_id"] = users["user_id"].astype(int)
    users["subject_zone"] = users["user_id"].map(lambda u: ZONES[u % 3])
    pools = {z: users.loc[users["subject_zone"] == z, "user_id"].sort_values().to_numpy() for z in ZONES}
    trips["_user_id"] = [
        pools[z][c % len(pools[z])] for z, c in zip(trips["subject_zone"], trips["_raw_customer_id"])
    ]
    trips["customer_id"] = trips["_user_id"].map(lambda u: f"CUS_{u:05d}")

    dim_customers = (
        users[users["user_id"].isin(trips["_user_id"])]
        .assign(customer_id=lambda d: d["user_id"].map(lambda u: f"CUS_{u:05d}"),
                created_at=lambda d: to_date(d["created_at"]).dt.strftime("%Y-%m-%d"))
        [["customer_id", *PII_COLS, "subject_zone"]]
        .sort_values("customer_id")
    )

    # S3b: drivers, DRV_XANH_000k <- drivers.csv driver_id k
    drv_map = trips.drop_duplicates("driver_id")[["driver_id", "vehicle_vin", "subject_zone"]]
    drv_map["_k"] = drv_map["driver_id"].str.split("_").str[-1].astype(int).astype(str)
    dim_drivers = (
        drv_map.merge(drivers, left_on="_k", right_on="driver_id", suffixes=("", "_raw"))
        .assign(created_at=lambda d: to_date(d["created_at"]).dt.strftime("%Y-%m-%d"))
        [["driver_id", "vehicle_vin", *PII_COLS, "subject_zone"]]
        .sort_values("driver_id")
    )

    # S1: PII in uncatalogued column
    cust_lookup = dim_customers.set_index("customer_id")
    s1_idx = np.sort(rng.choice(n_trips, size=int(n_trips * S1_RATE), replace=False))
    trips["customer_contact"] = ""
    use_email = rng.random(len(s1_idx)) < 0.5
    for i, e in zip(s1_idx, use_email):
        c = cust_lookup.loc[trips.at[i, "customer_id"]]
        primary, fallback = (c["email"], c["phone_number"]) if e else (c["phone_number"], c["email"])
        trips.at[i, "customer_contact"] = primary if pd.notna(primary) else fallback

    # S2: PII in free text
    s2_idx = np.sort(rng.choice(n_trips, size=S2_ROWS, replace=False))
    fb_rows = []
    for n, i in enumerate(s2_idx, 1):
        t = trips.loc[i]
        c = cust_lookup.loc[t["customer_id"]]
        topic, tpl = S2_TEMPLATES[n % len(S2_TEMPLATES)]
        fb_rows.append({
            "feedback_id": f"FB_PII_{n:04d}",
            "vehicle_vin": t["vehicle_vin"],
            "scenario_date": t["pickup_datetime"][:10],
            "assigned_day_index": int(t["assigned_day_index"]),
            "topic": topic,
            "sentiment": 0,
            "raw_comment_text": tpl.format(phone=c["phone_number"], email=c["email"],
                                           first=c["first_name"], last=c["last_name"]),
            "subject_zone": t["subject_zone"],
            "trip_id": t["trip_id"],
            "customer_id": t["customer_id"],
        })
    feedback = pd.DataFrame(fb_rows)

    # Gates
    cust_zones = trips.groupby("customer_id")["subject_zone"].nunique()
    created = trips["customer_id"].map(cust_lookup["created_at"])
    checks = {
        "row_count_preserved": len(trips) == n_trips,
        "trip_id_unique": trips["trip_id"].is_unique,
        "customer_fk_complete": trips["customer_id"].isin(dim_customers["customer_id"]).all(),
        "driver_fk_complete": trips["driver_id"].isin(dim_drivers["driver_id"]).all(),
        "customer_single_zone": bool((cust_zones == 1).all()),
        "customer_zone_matches_dim": (trips["subject_zone"] == trips["customer_id"].map(cust_lookup["subject_zone"])).all(),
        "drivers_one_per_vin": dim_drivers["driver_id"].is_unique and dim_drivers["vehicle_vin"].is_unique and len(dim_drivers) == 60,
        "created_at_before_pickup": (pd.to_datetime(created) <= pd.to_datetime(trips["pickup_datetime"])).all(),
        "max_pickup_in_window": trips["pickup_datetime"].max() < "2026-01-11",
        "s1_rows_all_have_contact": trips.loc[s1_idx, "customer_contact"].notna().all(),
    }
    failed = [k for k, v in checks.items() if not v]
    if failed:
        raise SystemExit(f"[FAIL] gates: {failed}")

    out_dir.mkdir(exist_ok=True)
    trips.drop(columns=["_raw_customer_id", "_user_id"]).to_csv(out_dir / "ride_hailing_xanh_sm_trips.csv", index=False)
    dim_customers.to_csv(out_dir / "dim_customers.csv", index=False)
    dim_drivers.to_csv(out_dir / "dim_drivers.csv", index=False)
    feedback.to_csv(out_dir / "feedback_pii.csv", index=False)
    if with_faulty_domain_files:
        copy_faulty_domain_files(out_dir)

    manifest = {
        "source": {"trips": str(trips_dir.relative_to(ROOT)), "raw": str(RAW_DIR.relative_to(ROOT))},
        "window": {"assigned_day_index": [0, MAX_DAY_INDEX], "dates": ["2026-01-01", "2026-01-10"]},
        "seed": SEED,
        "customer_zone_rule": "user_id % 3 -> EU/VN/US; raw customer_id % pool_size within trip zone",
        "scenarios": {
            "S3_join_reidentification": {
                "trips_key": ["customer_id", "driver_id"],
                "dim_files": ["dim_customers.csv", "dim_drivers.csv"],
                "expected": "join trips x dim_* exposes identity; Lane B should flag re-identification risk",
            },
            "S1_uncatalogued_column": {
                "file": "ride_hailing_xanh_sm_trips.csv",
                "column": "customer_contact",
                "rows": trips.loc[s1_idx, "trip_id"].tolist(),
                "expected": "column not in catalog -> 'Unclear' -> blocked for every dest",
            },
            "S2_free_text": {
                "file": "feedback_pii.csv",
                "column": "raw_comment_text",
                "rows": feedback["feedback_id"].tolist(),
                "expected": "raw PII in text -> not raw to any llm/export dest",
            },
        },
        "checks": {k: bool(v) for k, v in checks.items()},
        "counts": {"trips": n_trips, "customers": len(dim_customers), "drivers": len(dim_drivers),
                   "s1_rows": len(s1_idx), "s2_rows": len(feedback)},
    }
    manifest["fault_injection"] = "L1-L4 faults present (source=vingroup_pilot_dataset_3zone copy)" \
        if with_faulty_domain_files else "none (source=clean)"
    (out_dir / "pii_injection_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"[OK] -> {out_dir.relative_to(ROOT)}")
    print(json.dumps(manifest["counts"] | manifest["checks"], indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--faulty", action="store_true",
                         help="Source trips from the F1-F16 fault-injected copy and carry over "
                              "its telemetry/charging/feedback/manifests, for a combined Lane A+B testset.")
    args = parser.parse_args()
    if args.faulty:
        main(FAULTY_DIR, FAULTY_OUT_DIR, with_faulty_domain_files=True)
    else:
        main(CLEAN_DIR, CLEAN_OUT_DIR, with_faulty_domain_files=False)
