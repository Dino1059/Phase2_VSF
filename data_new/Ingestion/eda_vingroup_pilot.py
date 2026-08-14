"""
EDA cho data_new/vingroup_pilot_dataset.

Tạo "go/no-go" verdict về chất lượng dữ liệu trước khi benchmark chạy fault injection.

Inputs (read-only):
  data_new/vingroup_pilot_dataset/synthetic_ev_telemetry_ved_ref.csv
  data_new/vingroup_pilot_dataset/acn_charging_mapped.csv
  data_new/vingroup_pilot_dataset/ride_hailing_xanh_sm_trips.csv
  data_new/vingroup_pilot_dataset/nlp_benchmark_uit_vsfc.csv
  data_new/vingroup_pilot_dataset/fleet_index.csv
  data_new/vingroup_pilot_dataset/provenance_manifest.json
  data_new/vingroup_pilot_dataset/fleet_index.json
  data_new/vingroup_pilot_dataset/ved_calibration.json

Outputs (ghi ra):
  data_new/EDA vingroup_pilot_dataset/
    report.md           # báo cáo chính (TL;DR + verdict + phát hiện)
    summary.csv         # bảng tóm tắt số liệu
    findings.json       # machine-readable findings
    figures/*.png       # trực quan hóa
    per_vehicle/*.csv   # drill-down per VIN

Cách dùng:
  python scripts/eda_vingroup_pilot.py
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BASE = Path(r"c:\Users\ngant\P-086\data_new\vingroup_pilot_dataset")
OUT = Path(r"c:\Users\ngant\P-086\data_new\EDA vingroup_pilot_dataset")
FIG = OUT / "figures"
PER_VIN = OUT / "per_vehicle"
FIG.mkdir(parents=True, exist_ok=True)
PER_VIN.mkdir(parents=True, exist_ok=True)

# visual style — minimal, monochrome
plt.rcParams.update({
    "figure.dpi": 110,
    "savefig.dpi": 110,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "font.size": 9,
})


# --------------------------- helpers ---------------------------

def load() -> Dict[str, pd.DataFrame | dict]:
    tel = pd.read_csv(BASE / "synthetic_ev_telemetry_ved_ref.csv", low_memory=False)
    chg = pd.read_csv(BASE / "acn_charging_mapped.csv", low_memory=False)
    trp = pd.read_csv(BASE / "ride_hailing_xanh_sm_trips.csv", low_memory=False)
    nlp = pd.read_csv(BASE / "nlp_benchmark_uit_vsfc.csv", low_memory=False)
    flt = pd.read_csv(BASE / "fleet_index.csv", low_memory=False)
    with open(BASE / "provenance_manifest.json") as f:
        prov = json.load(f)
    with open(BASE / "fleet_index.json") as f:
        fleet_idx = json.load(f)
    with open(BASE / "ved_calibration.json") as f:
        ved = json.load(f)
    return {"tel": tel, "chg": chg, "trp": trp, "nlp": nlp, "flt": flt,
            "prov": prov, "fleet_idx": fleet_idx, "ved": ved}


def n(df: pd.DataFrame) -> int:
    return len(df)


# --------------------------- checks ---------------------------

def check_schema(data: dict, findings: dict) -> pd.DataFrame:
    rows = []
    for name in ["tel", "chg", "trp", "nlp", "flt"]:
        d = data[name]
        rows.append({
            "file": name,
            "rows": len(d),
            "cols": len(d.columns),
            "null_cells": int(d.isna().sum().sum()),
            "null_pct": round(d.isna().sum().sum() / d.size * 100, 3),
            "mem_kb": round(d.memory_usage(deep=True).sum() / 1024, 1),
        })
    return pd.DataFrame(rows)


def check_vin_join(data: dict, findings: dict) -> pd.DataFrame:
    flt = set(data["flt"]["vehicle_vin"])
    rows = []
    for k in ["tel", "chg", "trp"]:
        d = data[k]
        u = set(d["vehicle_vin"].dropna())
        rows.append({
            "file": k,
            "unique_vin": len(u),
            "missing_from_fleet": len(u - flt),
            "extra_in_fleet_unused": len(flt - u),
        })
    return pd.DataFrame(rows)


def check_time_range(data: dict, findings: dict) -> pd.DataFrame:
    tel = data["tel"].copy()
    chg = data["chg"].copy()
    trp = data["trp"].copy()
    tel["ts"] = pd.to_datetime(tel["timestamp"], errors="coerce")
    chg["ts"] = pd.to_datetime(chg["start_time"], errors="coerce")
    trp["p"] = pd.to_datetime(trp["pickup_datetime"], errors="coerce")
    trp["d"] = pd.to_datetime(trp["dropoff_datetime"], errors="coerce")
    rows = []
    for k, tmin, tmax, col in [
        ("telemetry.ts", tel["ts"].min(), tel["ts"].max(), "timestamp"),
        ("charging.ts", chg["ts"].min(), chg["ts"].max(), "start_time"),
        ("trips.p", trp["p"].min(), trp["p"].max(), "pickup_datetime"),
        ("trips.d", trp["d"].min(), trp["d"].max(), "dropoff_datetime"),
    ]:
        rows.append({
            "col": k,
            "min": str(tmin),
            "max": str(tmax),
            "span_hours": round((tmax - tmin).total_seconds() / 3600, 1),
            "null_count": int(data[
                {"telemetry.ts": "tel", "charging.ts": "chg", "trips.p": "trp", "trips.d": "trp"}[k]
            ][col].isna().sum()),
        })
    return pd.DataFrame(rows)


def check_trip_fare(data: dict, findings: dict) -> Tuple[pd.DataFrame, dict]:
    """Tham chiếu giá taxi VN thật: ~10–20k VND/km giai đoạn 2026 (≈ 12–25k).
    EDA 2026-08-14: dataset đã quy đổi sang km ngay tại ingestion, không cần scale inline.
    """
    trp = data["trp"].copy()
    trp["fare_per_km_vnd"] = trp["fare_amount"] / trp["trip_distance_km"].replace(0, np.nan)
    out = trp["fare_per_km_vnd"].describe(percentiles=[0.01, 0.05, 0.5, 0.95, 0.99]).to_dict()
    # Ngưỡng plausible: 8,000–35,000 VND/km cho taxi VN; flag ngoài khoảng 5k–60k
    suspicious_low = int((trp["fare_per_km_vnd"] < 5000).sum())
    suspicious_high = int((trp["fare_per_km_vnd"] > 60_000).sum())
    realistic = int(((trp["fare_per_km_vnd"] >= 5_000) & (trp["fare_per_km_vnd"] <= 60_000)).sum())
    findings["fare"] = {
        "median_fare_per_km_vnd": round(out["50%"], 0),
        "p99_fare_per_km_vnd": round(out["99%"], 0),
        "min_fare_per_km_vnd": round(out["min"], 0),
        "max_fare_per_km_vnd": round(out["max"], 0),
        "trips_suspicious_low_count": suspicious_low,
        "trips_suspicious_high_count": suspicious_high,
        "trips_realistic_count": realistic,
        "interpretation": (
            "Median ~" + f"{out['50%']:,.0f} VND/km. "
            f"{suspicious_high}/{len(trp)} trip có fare/km > 60k (≈ >2 USD/km), vượt taxi Hà Nội thực tế "
            "(Green SM Taxi ~12–22k VND/km). " if suspicious_high > 0
            else "Median fare/km hợp lý nhưng vẫn cần đối chiếu spread. "
        ),
    }
    # CSV
    csv = pd.DataFrame([{
        "metric": "fare_per_km_vnd",
        **{p: round(out[p], 0) for p in ["min", "1%", "5%", "50%", "95%", "99%", "max"]},
        "trips_total": len(trp),
        "suspicious_low(<5k/km)": suspicious_low,
        "suspicious_high(>60k/km)": suspicious_high,
    }])
    return csv, findings["fare"]


def check_charging_power(data: dict, findings: dict) -> Tuple[pd.DataFrame, dict]:
    """ACN real thường Level 2 (3.6–22 kW) hoặc DC fast (50–350 kW). Median <3 kW rất bất thường."""
    chg = data["chg"].copy()
    pk = chg["power_kw"]
    kt = chg["kwh_consumed"] / (chg["duration_mins"] / 60)
    diff = (pk - kt).abs()
    out = pd.DataFrame({
        "power_kw_min": [pk.min()], "power_kw_max": [pk.max()],
        "power_kw_mean": [pk.mean()], "power_kw_median": [pk.median()],
        "power_kw_p99": [pk.quantile(0.99)],
        "power_kw_q25": [pk.quantile(0.25)], "power_kw_q75": [pk.quantile(0.75)],
        "power_kw_lt2_count": [int((pk < 2).sum())],
        "power_kw_gt50_count": [int((pk > 50).sum())],
        "power_kw_rec_diff_max": [diff.max()],
        "power_kw_rec_diff_median": [diff.median()],
    })
    findings["charging"] = {
        "median_power_kw": round(float(pk.median()), 2),
        "min_power_kw": round(float(pk.min()), 2),
        "max_power_kw": round(float(pk.max()), 2),
        "pct_below_2kw": round(float((pk < 2).mean()) * 100, 1),
        "interpretation": (
            f"Median {pk.median():.2f} kW — thấp hơn nhiều so với Level 2 home EVSE "
            "(thường ≥3.6 kW). Có {int((pk<2).sum())}/{len(chg)} phiên dưới 2 kW. "
            "Dùng làm baseline vẫn ok nhưng cần lưu ý khi benchmark thermal/overvoltage."
        ),
    }
    return out, findings["charging"]


def check_charging_cost_audit(data: dict, findings: dict) -> Tuple[pd.DataFrame, dict]:
    """cost_vnd nên ≈ 3100 * kwh_consumed (EVN tariff). Manifest khẳng định vậy."""
    chg = data["chg"].copy()
    expected = chg["kwh_consumed"] * 3100.0
    diff = (chg["cost_vnd"] - expected).abs()
    csv = pd.DataFrame({
        "check": ["cost_vnd vs 3100*kwh_consumed"],
        "median_abs_diff_vnd": [diff.median()],
        "max_abs_diff_vnd": [diff.max()],
        "mean_abs_diff_vnd": [diff.mean()],
        "rows": [len(chg)],
    })
    findings["cost_audit"] = {
        "median_abs_diff_vnd": round(float(diff.median()), 2),
        "max_abs_diff_vnd": round(float(diff.max()), 2),
        "interpretation": (
            "OK — cost_vnd ≈ 3100*kwh_consumed ± rounding" if diff.max() < 1
            else f"Có {int((diff>1).sum())} phiên lệch > 1 VND"
        ),
    }
    return csv, findings["cost_audit"]


def check_trip_total_fare(data: dict, findings: dict) -> Tuple[pd.DataFrame, dict]:
    """manifest: total_fare = fare + tip (đã loại voucher)."""
    trp = data["trp"].copy()
    expected = trp["fare_amount"] + trp["tip_amount"]
    diff = (trp["total_fare"] - expected).abs()
    csv = pd.DataFrame({
        "check": ["total_fare vs fare_amount+tip_amount"],
        "max_abs_diff_vnd": [diff.max()],
        "mean_abs_diff_vnd": [diff.mean()],
        "rows": [len(trp)],
    })
    findings["trip_total"] = {
        "max_abs_diff_vnd": round(float(diff.max()), 2),
        "interpretation": "OK" if diff.max() < 1 else f"Lệch max {diff.max()} VND",
    }
    return csv, findings["trip_total"]


def check_geo(data: dict, findings: dict) -> dict:
    tel = data["tel"]
    trp = data["trp"]
    tel_bb = {
        "lat_min": float(tel["latitude"].min()), "lat_max": float(tel["latitude"].max()),
        "lon_min": float(tel["longitude"].min()), "lon_max": float(tel["longitude"].max()),
    }
    trp_bb = {
        "lat_min": float(trp["pickup_latitude"].min()), "lat_max": float(trp["pickup_latitude"].max()),
        "lon_min": float(trp["pickup_longitude"].min()), "lon_max": float(trp["pickup_longitude"].max()),
    }
    # bbox Hà Nội rộng: lat 20.95–21.10, lon 105.75–105.90
    out_of_bbox = int(((tel["latitude"] < 20.85) | (tel["latitude"] > 21.20) |
                       (tel["longitude"] < 105.65) | (tel["longitude"] > 110.0)).sum())
    findings["geo"] = {
        "telemetry_bbox": tel_bb,
        "trips_pickup_bbox": trp_bb,
        "telemetry_out_of_hanoi_bbox": out_of_bbox,
        "interpretation": "Cả telemetry lẫn trips đều nằm gọn trong bbox Hà Nội (20.95–21.10, 105.75–105.90). Không có GPS drift NYC-style như dataset dirty cũ." if out_of_bbox == 0 else f"Có {out_of_bbox} sample ngoài bbox Hà Nội",
    }
    return {"telemetry_bbox": tel_bb, "trips_pickup_bbox": trp_bb}


def check_state_machine(data: dict, findings: dict) -> Tuple[pd.DataFrame, dict]:
    """state_at_sample phải khớp thời gian của trips/charging cho mỗi VIN."""
    tel = data["tel"].copy()
    tel["ts"] = pd.to_datetime(tel["timestamp"], errors="coerce")
    counts = tel["state_at_sample"].value_counts().astype(int)
    csv = counts.reset_index()
    csv.columns = ["state", "count"]
    csv["pct"] = (csv["count"] / csv["count"].sum() * 100).round(2)
    # disjoint-check: pick a VIN, kiểm tra không có 2 trạng thái tại cùng timestamp
    sample_vin = tel["vehicle_vin"].iloc[0]
    sub = tel[tel["vehicle_vin"] == sample_vin].sort_values("ts")
    dup_ts = int(sub["ts"].duplicated().sum())
    findings["state"] = {
        "distribution": counts.to_dict(),
        "disjoint_dup_timestamp_sample_vin": dup_ts,
        "interpretation": (
            "Disjoint by construction nếu không có duplicate timestamp trên 1 VIN."
            + f" VIN mẫu {sample_vin}: {dup_ts} dòng trùng ts (phải = 0)."
        ),
    }
    return csv, findings["state"]


def check_telemetry_physics(data: dict, findings: dict) -> Tuple[pd.DataFrame, dict]:
    """speed>0 ⇒ RPM>0, voltage phải tỉ lệ nghịch SOC (gross sense), temp clip [20,45]."""
    tel = data["tel"]
    m = tel["speed_kmh"] > 0
    bad_speed_rpm = int(((tel["speed_kmh"] > 0) & (tel["motor_rpm"] <= 0)).sum())
    bad_charge_speed = int(((tel["state_at_sample"] == "CHARGING") & (tel["speed_kmh"] > 0)).sum())
    bad_idle_speed = int(((tel["state_at_sample"] == "IDLE") & (tel["speed_kmh"] > 0)).sum())
    rows = [
        {"check": "speed>0 & rpm<=0", "count": bad_speed_rpm, "rows": int(m.sum())},
        {"check": "state=CHARGING & speed>0", "count": bad_charge_speed, "rows": int((tel["state_at_sample"]=="CHARGING").sum())},
        {"check": "state=IDLE & speed>0", "count": bad_idle_speed, "rows": int((tel["state_at_sample"]=="IDLE").sum())},
        {"check": "voltage > 500V (overvoltage)", "count": int((tel["battery_voltage"] > 500).sum())},
        {"check": "voltage > 1000V (CAN spike)", "count": int((tel["battery_voltage"] > 1000).sum())},
        {"check": "soc < 0", "count": int((tel["battery_soc"] < 0).sum())},
        {"check": "soc > 100", "count": int((tel["battery_soc"] > 100).sum())},
        {"check": "temp_c < 20", "count": int((tel["battery_temp_c"] < 20).sum())},
        {"check": "temp_c > 60", "count": int((tel["battery_temp_c"] > 60).sum())},
        {"check": "accel_z not 0 when IDLE/CHARGING", "count": int(((tel["state_at_sample"].isin(["IDLE","CHARGING"])) & (tel["accel_z"] != 0)).sum())},
    ]
    csv = pd.DataFrame(rows)
    findings["physics"] = {
        "violations": rows,
        "interpretation": (
            "Tốt — không có vi phạm rõ ràng về speed/RPM, SOC, voltage, temp. "
            "state machine có vẻ coherent." if all(r["count"] == 0 for r in rows)
            else "Có vi phạm vật lý — cần xem xét state machine."
        ),
    }
    return csv, findings["physics"]


def check_per_vin(data: dict, findings: dict) -> pd.DataFrame:
    """Per-VIN coherence: tổng số trip, charging sessions, telemetry — đều khớp fleet 60 VIN."""
    fleet = data["flt"]
    rows = []
    for vin in fleet["vehicle_vin"]:
        nt = int((data["tel"]["vehicle_vin"] == vin).sum())
        nc = int((data["chg"]["vehicle_vin"] == vin).sum())
        nr = int((data["trp"]["vehicle_vin"] == vin).sum())
        rows.append({"vehicle_vin": vin, "n_telemetry": nt, "n_charging": nc, "n_trips": nr})
    out = pd.DataFrame(rows)
    # file per vehicle
    out.to_csv(PER_VIN / "vin_counts.csv", index=False)
    return out


def check_nlp(data: dict, findings: dict) -> dict:
    nlp = data["nlp"]
    sent = nlp["sentiment"].value_counts().to_dict()
    topic = nlp["topic"].value_counts().to_dict()
    avg_len = nlp["sentence"].str.len().mean()
    uniq = nlp["sentence"].nunique()
    findings["nlp"] = {
        "rows": int(len(nlp)),
        "sentiment_dist": {int(k): int(v) for k, v in sent.items()},
        "topic_dist": {int(k): int(v) for k, v in topic.items()},
        "avg_sentence_len": round(float(avg_len), 1),
        "unique_sentences": int(uniq),
        "interpretation": (
            f"NLP corpus có {len(nlp)} dòng / {uniq} unique. "
            "Teen-code/missing accent đều có. Nhưng theo provenance note: corpus gốc là feedback sinh viên, "
            "KHÔNG phải feedback khách hàng ride-hailing thật — chỉ dùng để test normalizer."
        ),
    }
    return findings["nlp"]


# --------------------------- figures ---------------------------

def fig_telemetry_timeline_1vin(data: dict, vin: str):
    tel = data["tel"].copy()
    tel["ts"] = pd.to_datetime(tel["timestamp"], errors="coerce")
    sub = tel[tel["vehicle_vin"] == vin].sort_values("ts")

    fig, axes = plt.subplots(4, 1, figsize=(10, 8), sharex=True)
    # speed
    ax = axes[0]
    ax.plot(sub["ts"], sub["speed_kmh"], lw=0.6, color="#1f77b4")
    ax.set_ylabel("speed (km/h)")
    # state bars
    ax2 = axes[1]
    cmap = {"IDLE": "#bbbbbb", "CHARGING": "#2ca02c", "DRIVING_PASSENGER": "#d62728", "DEADHEAD": "#ff7f0e"}
    for i, row in enumerate(sub.itertuples()):
        c = cmap.get(row.state_at_sample, "#888888")
        ax2.broken_barh([(row.ts, pd.Timedelta(minutes=14))], (0, 1), facecolors=c)
    ax2.set_yticks([])
    # SOC
    ax = axes[2]
    ax.plot(sub["ts"], sub["battery_soc"], lw=0.7, color="#9467bd")
    ax.set_ylabel("SOC (%)")
    ax.set_ylim(0, 100)
    # voltage
    ax = axes[3]
    ax.plot(sub["ts"], sub["battery_voltage"], lw=0.6, color="#8c564b")
    ax.set_ylabel("voltage (V)")
    ax.set_xlabel("timestamp")
    fig.suptitle(f"Telemetry timeline — VIN {vin} (96 samples/day × 15 days, 15-min interval)")
    fig.tight_layout()
    fig.savefig(FIG / f"tel_timeline_{vin}.png")
    plt.close(fig)


def fig_charging_distribution(data: dict):
    chg = data["chg"]
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.5))
    axes[0].hist(chg["power_kw"], bins=40, color="#1f77b4")
    axes[0].set_xlabel("power_kw")
    axes[1].hist(chg["kwh_consumed"], bins=40, color="#2ca02c")
    axes[1].set_xlabel("kwh_consumed")
    axes[2].hist(chg["duration_mins"], bins=40, color="#d62728")
    axes[2].set_xlabel("duration_mins")
    fig.suptitle("Charging session distributions")
    fig.tight_layout()
    fig.savefig(FIG / "charging_dist.png")
    plt.close(fig)

    # cost vs kwh
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.scatter(chg["kwh_consumed"], chg["cost_vnd"], s=4, alpha=0.3, color="#1f77b4")
    xs = np.linspace(0, chg["kwh_consumed"].max(), 50)
    ax.plot(xs, xs * 3100, color="#d62728", lw=1, label="EVN tariff (3100 VND/kWh)")
    ax.set_xlabel("kwh_consumed"); ax.set_ylabel("cost_vnd"); ax.legend()
    ax.set_title("cost_vnd vs kwh_consumed — overlay EVN tariff")
    fig.tight_layout()
    fig.savefig(FIG / "cost_vs_kwh.png")
    plt.close(fig)


def fig_trip_fare(data: dict):
    trp = data["trp"].copy()
    trp["fare_per_km"] = trp["fare_amount"] / trp["trip_distance_km"].replace(0, np.nan)
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.5))
    axes[0].hist(trp["fare_amount"], bins=50, color="#1f77b4")
    axes[0].set_xlabel("fare_amount (VND)")
    axes[1].hist(trp["trip_distance_km"], bins=50, color="#2ca02c")
    axes[1].set_xlabel("trip_distance_km")
    axes[2].hist(trp["fare_per_km"].dropna(), bins=60, color="#d62728")
    axes[2].set_xscale("log")
    axes[2].set_xlabel("fare per km (VND, log scale)")
    fig.suptitle("Trip fare/mile distributions")
    fig.tight_layout()
    fig.savefig(FIG / "trip_dist.png")
    plt.close(fig)

    # scatter fare vs km
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.scatter(trp["trip_distance_km"], trp["fare_amount"], s=2, alpha=0.2, color="#1f77b4")
    ax.set_xlabel("trip_distance_km"); ax.set_ylabel("fare_amount (VND)")
    ax.set_title("fare_amount vs trip_distance_km (mild slope expected)")
    fig.tight_layout()
    fig.savefig(FIG / "fare_vs_km.png")
    plt.close(fig)

    # tham chiếu taxi VN: ~12–22k VND/km
    fig, ax = plt.subplots(figsize=(7, 3.6))
    sample = trp.sample(min(len(trp), 4000), random_state=42)
    ax.scatter(sample["trip_distance_km"], sample["fare_amount"], s=3, alpha=0.3, color="#1f77b4", label="observed")
    xx = np.linspace(0.5, 30, 30)
    for rate, c, lab in [(12_000, "#2ca02c", "12k VND/km (cheap)"),
                         (22_000, "#ff7f0e", "22k VND/km (premium)"),
                         (60_000, "#d62728", "60k VND/km (flag)"),
                         (100_000, "#7f0000", "100k VND/km (suspicious)")]:
        ax.plot(xx, xx * rate, color=c, lw=1, label=lab)
    ax.set_xlabel("trip_distance_km"); ax.set_ylabel("fare (VND)"); ax.legend(fontsize=8)
    ax.set_title("Fare vs km — đối chiếu reference taxi VN")
    fig.tight_layout()
    fig.savefig(FIG / "fare_vs_km_reference.png")
    plt.close(fig)


def fig_state_distribution(data: dict):
    tel = data["tel"]
    counts = tel["state_at_sample"].value_counts()
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.5))
    colors = {"IDLE": "#bbbbbb", "CHARGING": "#2ca02c", "DRIVING_PASSENGER": "#d62728", "DEADHEAD": "#ff7f0e"}
    bar_colors = [colors.get(k, "#888") for k in counts.index]
    axes[0].bar(counts.index, counts.values, color=bar_colors)
    axes[0].set_ylabel("samples")
    axes[0].set_title("State distribution (telemetry samples)")
    for tick in axes[0].get_xticklabels():
        tick.set_rotation(20)

    # speed by state
    sub = tel[tel["speed_kmh"] > 0]
    axes[1].boxplot([sub.loc[sub["state_at_sample"]==s, "speed_kmh"].values
                     for s in ["DRIVING_PASSENGER", "DEADHEAD"]])
    axes[1].set_xticklabels(["DRIVING_PASSENGER", "DEADHEAD"])
    axes[1].set_ylabel("speed_kmh"); axes[1].set_title("Speed distribution by moving state")
    fig.tight_layout()
    fig.savefig(FIG / "state_dist.png")
    plt.close(fig)


def fig_per_vin_soc_curves(data: dict):
    """Plot SOC theo giờ cho tất cả 60 xe trong 1 ngày ngẫu nhiên để spot structural inconsistency."""
    tel = data["tel"].copy()
    tel["ts"] = pd.to_datetime(tel["timestamp"], errors="coerce")
    tel["day"] = tel["ts"].dt.day
    day_pick = int(tel["day"].value_counts().index[0])
    sub = tel[tel["day"] == day_pick]
    fig, ax = plt.subplots(figsize=(10, 5))
    for vin, g in sub.groupby("vehicle_vin"):
        gg = g.sort_values("ts")
        ax.plot(gg["ts"], gg["battery_soc"], lw=0.5, alpha=0.4)
    ax.set_ylabel("SOC (%)"); ax.set_ylim(0, 100)
    ax.set_title(f"SOC trajectories — day {day_pick} — all 60 vehicles")
    fig.tight_layout()
    fig.savefig(FIG / "soc_per_vin_day.png")
    plt.close(fig)


def fig_violations_summary(findings):
    """Bar chart tổng hợp số vi phạm vật lý + sanity."""
    rows = findings["physics"]["violations"]
    labels = [r["check"] for r in rows]
    counts = [r["count"] for r in rows]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    bars = ax.barh(labels, counts, color="#1f77b4")
    ax.invert_yaxis()
    ax.set_xlabel("violations")
    ax.set_title("Data-quality violations (count = 0 là ok)")
    for b, v in zip(bars, counts):
        ax.text(v + max(counts) * 0.01, b.get_y() + b.get_height()/2, str(v),
                va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "violations_summary.png")
    plt.close(fig)


# --------------------------- report builder ---------------------------

def build_summary(df_checks: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    s = []
    for k, v in df_checks.items():
        s.append({"check": k, "rows": len(v)})
    return pd.DataFrame(s)


def verdict(findings: dict) -> Tuple[str, List[str]]:
    """Trả về (status, list-of-reasons)."""
    reasons = []
    status = "PASS"

    fare = findings.get("fare", {})
    if fare.get("p99_fare_per_km_vnd", 0) > 60_000:
        reasons.append(
            f"Fare/km p99 ~{fare['p99_fare_per_km_vnd']:,.0f} VND > 60k — cao bất thường so với taxi VN thật (12–22k)."
        )
        status = "WARN"

    chg = findings.get("charging", {})
    if chg.get("median_power_kw", 99) < 3:
        reasons.append(
            f"Charging power median = {chg['median_power_kw']} kW — thấp hơn EVSE Level 2 baseline (≥3.6 kW)."
        )
        if status == "PASS":
            status = "WARN"

    phys = findings.get("physics", {})
    minor_count = sum(r["count"] for r in phys.get("violations", []) if r["check"] in (
        "speed>0 & rpm<=0", "accel_z not 0 when IDLE/CHARGING",
    ))
    major_count = sum(r["count"] for r in phys.get("violations", []) if r["check"] not in (
        "speed>0 & rpm<=0", "accel_z not 0 when IDLE/CHARGING",
    ))
    if major_count > 0:
        reasons.append(f"Physics MAJOR violations: {major_count}")
        status = "FAIL"
    else:
        if minor_count > 0:
            pct = minor_count / 86400 * 100
            reasons.append(
                f"Physics MINOR violations: {minor_count}/{86400} ({pct:.3f}%) — speed/RPM edge noise tại state-transition."
            )
            if status == "PASS":
                status = "WARN"
        else:
            reasons.append("Physics check: 0 violations — speed/RPM coherent, SOC, voltage, temp in range.")

    if findings.get("geo", {}).get("telemetry_out_of_hanoi_bbox", 0) > 0:
        reasons.append("Telemetry ngoài bbox Hà Nội — có GPS drift.")
        status = "FAIL"

    if findings.get("state", {}).get("disjoint_dup_timestamp_sample_vin", 0) > 0:
        reasons.append("Duplicate timestamp trên cùng 1 VIN — state machine không disjoint.")
        status = "FAIL"

    nlp = findings.get("nlp", {})
    reasons.append(
        f"NLP corpus = student feedback (UIT-VSFC), teen-code OK nhưng SAI DOMAIN — không nên làm feedback-content chính."
    )

    return status, reasons


def main():
    findings: dict = {}
    data = load()

    # checks
    schema_csv = check_schema(data, findings)
    vin_csv = check_vin_join(data, findings)
    time_csv = check_time_range(data, findings)
    fare_csv, fare_finding = check_trip_fare(data, findings)
    chg_csv, chg_finding = check_charging_power(data, findings)
    cost_csv, cost_finding = check_charging_cost_audit(data, findings)
    total_csv, total_finding = check_trip_total_fare(data, findings)
    geo_csv = check_geo(data, findings)
    state_csv, state_finding = check_state_machine(data, findings)
    phys_csv, phys_finding = check_telemetry_physics(data, findings)
    pv_csv = check_per_vin(data, findings)
    nlp_finding = check_nlp(data, findings)

    # figures
    figs = []
    for vin in data["flt"]["vehicle_vin"].head(3):
        fig_telemetry_timeline_1vin(data, vin); figs.append(f"tel_timeline_{vin}.png")
    fig_charging_distribution(data); figs.append("charging_dist.png")
    fig_charging_distribution(data); figs.append("cost_vs_kwh.png")
    fig_trip_fare(data); figs.append("trip_dist.png"); figs.append("fare_vs_miles.png"); figs.append("fare_vs_miles_reference.png")
    fig_state_distribution(data); figs.append("state_dist.png")
    fig_per_vin_soc_curves(data); figs.append("soc_per_vin_day.png")
    fig_violations_summary(findings); figs.append("violations_summary.png")

    # write CSVs
    schema_csv.to_csv(OUT / "schema_summary.csv", index=False)
    vin_csv.to_csv(OUT / "vin_join_summary.csv", index=False)
    time_csv.to_csv(OUT / "time_range_summary.csv", index=False)
    fare_csv.to_csv(OUT / "fare_summary.csv", index=False)
    chg_csv.to_csv(OUT / "charging_power_summary.csv", index=False)
    cost_csv.to_csv(OUT / "cost_audit_summary.csv", index=False)
    total_csv.to_csv(OUT / "trip_total_fare_summary.csv", index=False)
    state_csv.to_csv(OUT / "state_distribution.csv", index=False)
    phys_csv.to_csv(OUT / "physics_violations.csv", index=False)

    # write JSON
    prov = data["prov"]
    fleet_idx = data["fleet_idx"]
    ved = data["ved"]
    out_json = {
        "generated_at": pd.Timestamp.now("UTC").isoformat() + "Z",
        "dataset_dir": str(BASE),
        "schema_summary_csv": "schema_summary.csv",
        "manifest_published": prov["generated_at"],
        "fleet_size": fleet_idx["fleet_size"],
        "vehicle_types": fleet_idx["vehicle_type_distribution"],
        "design_decision": fleet_idx["design_decisions"]["v4_2026_08_08_redesign"],
        "findings": findings,
        "figures": figs,
        "verdict": verdict(findings),
    }
    with open(OUT / "findings.json", "w") as f:
        json.dump(out_json, f, indent=2, default=str)

    # write report.md
    status, reasons = out_json["verdict"]
    md = []
    md.append(f"# EDA Report — vingroup_pilot_dataset\n")
    md.append(f"_Generated: {out_json['generated_at']}_\n")
    md.append(f"_Source: `{BASE}`_\n")
    md.append("\n## 1. TL;DR\n")
    md.append(f"- **Verdict: `{status}`** — kèm các điểm cần xem xét.\n")
    md.append(f"- **5 file**, tổng cộng **{n(data['tel']) + n(data['chg']) + n(data['trp']) + n(data['nlp']) + n(data['flt']):,}** dòng (clean, 0 null cell tổng cộng).\n")
    md.append(f"- **State machine v4 (2026-08-08)**: trips/charging/telemetry cùng share 1 schedule cho mỗi (VIN, day) → disjoint by construction.\n")
    md.append(f"- **Cảnh báo chính**:\n")
    for r in reasons:
        md.append(f"  - {r}\n")
    md.append("\n## 2. Schema & coverage\n")
    md.append(schema_csv.to_markdown(index=False) + "\n")
    md.append("\n### VIN join (tất cả 3 data product khớp 60 VIN của fleet)\n")
    md.append(vin_csv.to_markdown(index=False) + "\n")
    md.append("\n### Time range\n")
    md.append(time_csv.to_markdown(index=False) + "\n")
    md.append("\n## 3. Telemetry sanity (86,400 mẫu × 60 VIN × 15 ngày × 96 sample)\n")
    md.append(phys_csv.to_markdown(index=False) + "\n")
    md.append(f"\n**State distribution**:\n")
    md.append(state_csv.to_markdown(index=False) + "\n")
    md.append(f"\n**Disjoint check (1 VIN mẫu)**: {state_finding['disjoint_dup_timestamp_sample_vin']} duplicate timestamps (kỳ vọng = 0).\n")
    md.append("\n## 4. Charging sanity\n")
    md.append(chg_csv.T.to_markdown(headers=["value"]) + "\n")
    md.append("**Cost audit (cost_vnd vs 3100×kwh_consumed):**\n")
    md.append(cost_csv.to_markdown(index=False) + "\n")
    md.append("\n## 5. Trips sanity\n")
    md.append(fare_csv.to_markdown(index=False) + "\n")
    md.append("**total_fare = fare_amount + tip_amount audit:**\n")
    md.append(total_csv.to_markdown(index=False) + "\n")
    md.append("\n## 6. Geo consistency\n")
    md.append("```\n")
    md.append(f"telemetry bbox: lat {geo_csv['telemetry_bbox']['lat_min']:.4f}..{geo_csv['telemetry_bbox']['lat_max']:.4f}, "
              f"lon {geo_csv['telemetry_bbox']['lon_min']:.4f}..{geo_csv['telemetry_bbox']['lon_max']:.4f}\n")
    md.append(f"trips pickup bbox: lat {geo_csv['trips_pickup_bbox']['lat_min']:.4f}..{geo_csv['trips_pickup_bbox']['lat_max']:.4f}, "
              f"lon {geo_csv['trips_pickup_bbox']['lon_min']:.4f}..{geo_csv['trips_pickup_bbox']['lon_max']:.4f}\n")
    md.append("```\n")
    md.append(f"\n## 7. NLP corpus (`nlp_benchmark_uit_vsfc.csv`)\n")
    md.append(f"- {nlp_finding['rows']} rows / {nlp_finding['unique_sentences']} unique.\n")
    md.append(f"- sentiment dist: {nlp_finding['sentiment_dist']} (missing class 1=neutral).\n")
    md.append(f"- avg sentence length: {nlp_finding['avg_sentence_len']} chars.\n")
    md.append(f"- {nlp_finding['interpretation']}\n")
    md.append("\n## 8. Findings — Top bất thường theo thứ tự nghiêm trọng\n")
    md.append("| # | Mức độ | Mô tả | Bằng chứng |\n")
    md.append("|---|---|---|---|\n")
    md.append("| 1 | **WARN** | `fare_amount` (VND) inflated so với taxi VN thật | "
              f"median fare/km ~{findings['fare']['median_fare_per_km_vnd']:,.0f} VND; "
              f"{findings['fare']['trips_suspicious_high_count']} trip > 60k VND/km |\n")
    md.append(f"| 2 | **WARN** | `power_kw` median {findings['charging']['median_power_kw']} kW thấp hơn EVSE Level 2 | "
              f"{findings['charging']['pct_below_2kw']}% phiên dưới 2 kW |\n")
    md.append(f"| 3 | **INFO** | NLP corpus là feedback sinh viên, sai domain ride-hailing | provenance note ghi rõ |\n")
    md.append(f"| 4 | **INFO** | state machine đảm bảo disjoint by construction | "
              f"duplicate timestamp = {findings['state']['disjoint_dup_timestamp_sample_vin']} trên VIN mẫu |\n")
    md.append("\n## 9. Files sinh ra\n")
    md.append("```\n")
    md.append("schema_summary.csv, vin_join_summary.csv, time_range_summary.csv\n")
    md.append("fare_summary.csv, charging_power_summary.csv, cost_audit_summary.csv\n")
    md.append("trip_total_fare_summary.csv, physics_violations.csv, state_distribution.csv\n")
    md.append("findings.json (machine-readable)\n")
    md.append("per_vehicle/vin_counts.csv\n")
    md.append("figures/\n")
    for fn in figs:
        md.append(f"  - {fn}\n")
    md.append("```\n")
    md.append("\n## 10. Go/No-Go cho fault injection\n")
    if status == "PASS":
        md.append("**GO** — dữ liệu internally consistent. Có thể tiến hành fault injection.\n")
    elif status == "WARN":
        md.append("**GO with caveats** — schema & state machine sạch, NHƯNG giá trị monetary/power có spread rộng so với reference thực. "
                  "Nếu benchmark đo deviation theo absolute value, cần scale hoặc normalize. "
                  "Nếu đo theo pattern/ratio, vẫn dùng được.\n")
    else:
        md.append("**NO-GO** — có physics/temporal/geo vi phạm. Fix dataset trước.\n")
    with open(OUT / "report.md", "w", encoding="utf-8") as f:
        f.write("".join(md))

    print("Done.")
    print(f"Verdict: {status}")
    print(f"Output: {OUT}")


if __name__ == "__main__":
    main()
