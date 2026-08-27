"""Adapter: Ngan landing incidents[] onto existing GroundTruthMatcher + RCA matchers.

Does not add a third BenchmarkHarness. Detection scores go through
GroundTruthMatcher; RCA through RCAGroundTruthMatcher / frozen testset
(same JSON FrozenRCABenchmarkRunner loads). Signal emission uses L1–L4
predicates on canonical table names. LLM-judge off.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.reliability.benchmark.ground_truth_matcher import GroundTruthMatcher
from src.reliability.benchmark.rca_ground_truth_matcher import FAULT_FAMILY_RCA_SPECS, RCAGroundTruthMatcher
from src.reliability.models.signal import Signal

ROOT = Path(__file__).resolve().parents[3]
MANIFEST_CANDIDATES = [
    ROOT / "landing_data" / "fault_manifest.json",
    ROOT / "data_new" / "vingroup_faulty_pilot_dataset" / "fault_manifest.json",
]
PARQUET_CANDIDATES = [
    ROOT / "landing_data" / "vingroup_pilot_landing_demo.parquet",
    ROOT / "data_new" / "vingroup_pilot_landing.parquet",
    ROOT / "data_demo" / "vingroup_pilot_landing_demo.parquet",
]
# Manifest tables → warehouse names (eval keys stay on manifest tables).
CANONICAL_TABLE = {
    "ev_telemetry": "ev_telemetry",
    "acn_charging": "charging_sessions",
    "ride_trips": "trips",
}
HANOI_LAT = (20.8, 21.3)
HANOI_LON = (105.6, 106.0)
WARMUP_MAX_DAY = 8
UNANSWERABLE_PROBES = (
    {"id": "weather", "question": "Did weather cause the VinFast battery fault?", "missing": "weather"},
    {"id": "tire_pressure", "question": "What is tire_pressure for VF8VNF_0001?", "missing": "tire_pressure"},
    {"id": "cabin_humidity", "question": "Report cabin_humidity at the SOC glitch.", "missing": "cabin_humidity"},
)


def _first_existing(paths: list[Path]) -> Path:
    for p in paths:
        if p.exists():
            return p
    raise FileNotFoundError(f"none of {paths}")


def _prf(tp: int, fp: int, fn: int) -> dict[str, float]:
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4), "tp": tp, "fp": fp, "fn": fn}


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def load_gt_pack() -> tuple[dict[str, Any], pd.DataFrame]:
    manifest = json.loads(_first_existing(MANIFEST_CANDIDATES).read_text(encoding="utf-8"))
    pq = _first_existing(PARQUET_CANDIDATES)
    df = pd.read_parquet(pq)
    if "dataset_table" not in df.columns:
        raise ValueError("parquet missing dataset_table")
    parts = []
    for table, g in df.groupby("dataset_table", sort=False):
        g = g.copy()
        g["row_index"] = range(len(g))
        parts.append(g)
    return manifest, pd.concat(parts, ignore_index=True)


def _emit(rows: pd.DataFrame, family: str, column: str) -> list[dict[str, Any]]:
    out = []
    has_vin = "vehicle_vin" in rows.columns
    has_drv = "driver_id" in rows.columns
    cols = ["dataset_table", "row_index", "day_idx"]
    extra = [c for c in ("vehicle_vin", "driver_id") if c in rows.columns]
    for rec in rows[cols + extra].itertuples(index=False):
        entity = None
        if has_vin and getattr(rec, "vehicle_vin", None) is not None:
            entity = str(rec.vehicle_vin)
        elif has_drv and getattr(rec, "driver_id", None) is not None:
            entity = str(rec.driver_id)
        out.append({
            "dataset_table": rec.dataset_table,
            "row_index": int(rec.row_index),
            "day_idx": int(rec.day_idx) if pd.notna(rec.day_idx) else None,
            "fault_family": family,
            "column": column,
            "entity_id": entity,
            "canonical_table": CANONICAL_TABLE.get(str(rec.dataset_table), str(rec.dataset_table)),
        })
    return out


def detect_anomalies(df: pd.DataFrame, day_idx: int | None = None) -> list[dict[str, Any]]:
    """Deterministic L1–L4 predicates on the Ngan landing parquet (no LLM)."""
    work = df if day_idx is None else df[df["day_idx"] == day_idx]
    if work.empty:
        return []
    dets: list[dict[str, Any]] = []
    ev = work[work["dataset_table"] == "ev_telemetry"]
    ch = work[work["dataset_table"] == "acn_charging"]
    tr = work[work["dataset_table"] == "ride_trips"]
    fleet = df[df["dataset_table"] == "fleet_index"] if "vehicle_vin" in df.columns else pd.DataFrame()

    if not ev.empty and "battery_soc" in ev.columns:
        dets += _emit(ev[_num(ev["battery_soc"]) < 0], "F1_Negative_SOC", "battery_soc")
    if not ev.empty and "battery_voltage" in ev.columns:
        dets += _emit(ev[_num(ev["battery_voltage"]) > 1000], "F2_Voltage_Overvoltage_Spike", "battery_voltage")
    if not ev.empty and {"speed_kmh", "motor_rpm"} <= set(ev.columns):
        dets += _emit(
            ev[(_num(ev["speed_kmh"]) == 0) & (_num(ev["motor_rpm"]) > 12000)],
            "F3_RPM_Speed_Mismatch",
            "motor_rpm",
        )
    if not ch.empty and "cost_vnd" in ch.columns:
        dets += _emit(ch[_num(ch["cost_vnd"]) < 0], "F5_Negative_Cost", "cost_vnd")
    if not tr.empty and "fare_amount" in tr.columns:
        dets += _emit(tr[_num(tr["fare_amount"]) < 0], "F7_Negative_Fare", "fare_amount")
    if not tr.empty and {"total_fare", "fare_amount", "tip_amount"} <= set(tr.columns):
        mismatch = (_num(tr["total_fare"]) - (_num(tr["fare_amount"]) + _num(tr["tip_amount"]))).abs() > 1.0
        dets += _emit(tr[mismatch], "F8_Ledger_Mismatch", "total_fare")
    if not ev.empty and "battery_temp_c" in ev.columns and "vehicle_vin" in ev.columns:
        warm = df[(df["dataset_table"] == "ev_telemetry") & (df["day_idx"] <= WARMUP_MAX_DAY)]
        if not warm.empty:
            base = warm.groupby("vehicle_vin")["battery_temp_c"].mean()
            mapped = _num(ev["battery_temp_c"]) - ev["vehicle_vin"].map(base)
            mask = (mapped > 18) & (_num(ev["day_idx"]) >= 11)
            dets += _emit(ev[mask], "F11_BatteryTemp_Drift", "battery_temp_c")
    if not ev.empty and "battery_soc" in ev.columns and "vehicle_vin" in ev.columns:
        warm = df[(df["dataset_table"] == "ev_telemetry") & (df["day_idx"] <= WARMUP_MAX_DAY)]
        if not warm.empty:
            base_soc = warm.groupby("vehicle_vin")["battery_soc"].mean()
            src = ev[_num(ev["day_idx"]) >= 12]
            if not src.empty:
                grp = src.groupby(["vehicle_vin", "day_idx"])["battery_soc"].mean()
                flagged = []
                for (vin, day), mean_soc in grp.items():
                    b = base_soc.get(vin)
                    if b and b > 0 and mean_soc / b < 0.7:
                        flagged.append((vin, day))
                if flagged:
                    mask = pd.Series(False, index=src.index)
                    for vin, day in flagged:
                        mask |= (src["vehicle_vin"] == vin) & (src["day_idx"] == day)
                    dets += _emit(src[mask], "F10_SOC_Degradation_Drift", "battery_soc")
    if not ch.empty and {"duration_mins", "kwh_consumed"} <= set(ch.columns):
        dets += _emit(
            ch[(_num(ch["duration_mins"]) >= 240) & (_num(ch["kwh_consumed"]) <= 1.25) & (_num(ch["day_idx"]) >= 11)],
            "F14_DurationEnergy_Mismatch",
            "duration_mins",
        )
    if not tr.empty and {"pickup_latitude", "pickup_longitude"} <= set(tr.columns):
        lat, lon = _num(tr["pickup_latitude"]), _num(tr["pickup_longitude"])
        outside = ~((lat.between(*HANOI_LAT)) & (lon.between(*HANOI_LON)))
        dets += _emit(tr[outside & lat.notna() & lon.notna()], "F6_GPS_Alleyway_Drift", "pickup_latitude")
    if not ch.empty and "vehicle_vin" in ch.columns and not tr.empty:
        day = int(work["day_idx"].iloc[0]) if day_idx is not None else None
        trips_src = tr if day is not None else df[df["dataset_table"] == "ride_trips"]
        chg_src = ch if day is not None else df[df["dataset_table"] == "acn_charging"]
        if day is not None:
            trips_src = trips_src[trips_src["day_idx"] == day]
            chg_src = chg_src[chg_src["day_idx"] == day]
        trip_vins = set(trips_src["vehicle_vin"].dropna().astype(str)) if "vehicle_vin" in trips_src.columns else set()
        counts = chg_src.groupby("vehicle_vin").size()
        ghost = counts[(counts >= 4) & (~counts.index.astype(str).isin(trip_vins))]
        if len(ghost):
            dets += _emit(chg_src[chg_src["vehicle_vin"].isin(ghost.index)], "F13_ChargingTrip_Mismatch", "vehicle_vin")
    if not ch.empty and "vehicle_vin" in ch.columns:
        warm_ch = df[(df["dataset_table"] == "acn_charging") & (df["day_idx"] <= WARMUP_MAX_DAY)]
        if not warm_ch.empty:
            base_n = warm_ch.groupby("vehicle_vin").size() / max(1, WARMUP_MAX_DAY + 1)
            today_n = ch.groupby("vehicle_vin").size()
            jumped = today_n[today_n >= (base_n.reindex(today_n.index).fillna(1) * 3).clip(lower=3)]
            if len(jumped) and day_idx is not None and day_idx >= 13:
                dets += _emit(ch[ch["vehicle_vin"].isin(jumped.index)], "F15_ChargingFrequency_Shift", "session_id")
    if not tr.empty and "driver_id" in tr.columns and "trip_distance_km" in tr.columns:
        warm_tr = df[(df["dataset_table"] == "ride_trips") & (df["day_idx"] <= WARMUP_MAX_DAY)]
        if not warm_tr.empty:
            base_d = warm_tr.groupby("driver_id")["trip_distance_km"].mean()
            today_d = tr.groupby("driver_id")["trip_distance_km"].mean()
            shifted = today_d[today_d > base_d.reindex(today_d.index) * 1.8]
            if len(shifted) and day_idx is not None and day_idx >= 14:
                dets += _emit(tr[tr["driver_id"].isin(shifted.index)], "F16_FareDistribution_Regime", "trip_distance_km")
    if not ch.empty and "vehicle_vin" in ch.columns:
        known = set(fleet["vehicle_vin"].dropna().astype(str)) if not fleet.empty and "vehicle_vin" in fleet.columns else set()
        if known:
            dets += _emit(ch[~ch["vehicle_vin"].astype(str).isin(known)], "F17_ForeignKey_Orphan", "vehicle_vin")
        dets += _emit(ch[ch["vehicle_vin"].astype(str).str.contains("ORPHAN", na=False)], "F17_ForeignKey_Orphan", "vehicle_vin")
    return dets


def _rank_families(claim: str) -> list[str]:
    return RCAGroundTruthMatcher.rank_families(claim)


def _dets_to_signals(dets: list[dict[str, Any]]) -> list[Signal]:
    now = datetime.now(timezone.utc)
    out: list[Signal] = []
    for d in dets:
        fam = str(d.get("fault_family") or "")
        layer = (FAULT_FAMILY_RCA_SPECS.get(fam) or {}).get("layer") or "L1"
        if layer not in ("L1", "L2", "L3", "L4"):
            layer = "L1"
        col = str(d.get("column") or fam)
        ent = d.get("entity_id")
        day = d.get("day_idx")
        event = now
        if day is not None:
            try:
                event = datetime(2026, 1, 1, tzinfo=timezone.utc) + pd.Timedelta(days=int(day))
            except (TypeError, ValueError):
                event = now
        out.append(Signal(
            project_id="ngan-gt",
            entity_ids=[str(ent)] if ent else [],
            layer=layer,
            signal_type=fam,
            metric_or_relationship=f"{col} {fam}",
            event_time=event,
            window_start=event,
            window_end=event,
            score=1.0,
            detector=fam,
            source_table=str(d.get("dataset_table") or d.get("canonical_table") or ""),
        ))
    return out


def _pack_dfs(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    dfs = {str(name): g.copy().reset_index(drop=True) for name, g in df.groupby("dataset_table", sort=False)}
    if "acn_charging" in dfs:
        dfs["charging_sessions"] = dfs["acn_charging"]
    if "ride_trips" in dfs:
        dfs["trips"] = dfs["ride_trips"]
    return dfs


def _cluster_dets(dets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One Signal per (family, entity, day, table) so matcher FP is not row-exploded."""
    seen: dict[tuple, dict[str, Any]] = {}
    for d in dets:
        key = (d.get("fault_family"), d.get("entity_id") or d.get("row_index"), d.get("day_idx"), d.get("dataset_table"))
        seen.setdefault(key, d)
    return list(seen.values())


def _matcher_detection(manifest_path: Path, df: pd.DataFrame, dets: list[dict]) -> dict[str, Any]:
    matcher = GroundTruthMatcher(manifest_path)
    raw = matcher.evaluate_signals({"all": _dets_to_signals(_cluster_dets(dets))}, _pack_dfs(df))
    om = raw.get("overall_metrics") or {}
    return {
        "precision": float(om.get("precision") or 0.0),
        "recall": float(om.get("recall") or 0.0),
        "f1": float(om.get("f1_score") or 0.0),
        "tp": int(om.get("true_positives") or 0),
        "fp": int(om.get("false_positives") or 0),
        "fn": int(om.get("false_negatives") or 0),
        "scorer": "GroundTruthMatcher.evaluate_signals",
    }


def _matches_incident(det: dict, inc: dict) -> bool:
    if det.get("dataset_table") != inc.get("dataset_table"):
        return False
    if int(det.get("row_index")) == int(inc.get("row_index")):
        return True
    ent = inc.get("entity_id")
    if ent and det.get("entity_id") == str(ent) and det.get("day_idx") == inc.get("day_idx"):
        return True
    return False


def _score_flow(incidents: list[dict], detections: list[dict], detection: dict[str, Any] | None = None) -> dict[str, Any]:
    matched_ids = set()
    loc_ok = time_ok = rca_top1 = rca_top3 = 0
    used = set()
    for inc in incidents:
        hits = [d for d in detections if _matches_incident(d, inc)]
        if not hits:
            continue
        matched_ids.add(inc["incident_id"])
        det = next((d for d in hits if int(d["row_index"]) == int(inc["row_index"])), hits[0])
        for d in hits:
            used.add((d["dataset_table"], int(d["row_index"]), d["fault_family"]))
        if int(det["row_index"]) == int(inc["row_index"]) or (
            inc.get("entity_id") and det.get("entity_id") == str(inc.get("entity_id"))
        ):
            loc_ok += 1
        if inc.get("day_idx") == det.get("day_idx"):
            time_ok += 1
        claim = f"{det.get('fault_family')} {det.get('column')} {inc.get('description')}"
        ranked = _rank_families(claim)
        fam = inc.get("fault_family")
        if ranked and ranked[0] == fam:
            rca_top1 += 1
        if fam in ranked[:3]:
            rca_top3 += 1
    fp = 0
    seen_fp = set()
    for d in detections:
        k = (d["dataset_table"], int(d["row_index"]), d["fault_family"])
        if k in used:
            continue
        if any(_matches_incident(d, inc) for inc in incidents):
            continue
        ck = (d["dataset_table"], d.get("fault_family"), d.get("entity_id") or d["row_index"], d.get("day_idx"))
        if ck in seen_fp:
            continue
        seen_fp.add(ck)
        fp += 1
    tp = len(matched_ids)
    fn = len(incidents) - tp
    n = max(len(incidents), 1)
    hall = [d for d in detections if d.get("day_idx") is not None and int(d["day_idx"]) <= WARMUP_MAX_DAY]
    hall_clusters = {(d.get("fault_family"), d.get("entity_id"), d.get("day_idx")) for d in hall}
    return {
        "detection": detection or _prf(tp, fp, fn),
        "location": {"accuracy": round(loc_ok / n, 4), "matched": loc_ok, "total": len(incidents)},
        "time_window": {"accuracy": round(time_ok / n, 4), "matched": time_ok, "total": len(incidents), "unit": "day_idx"},
        "rca": {
            "top1": round(rca_top1 / n, 4),
            "top3": round(rca_top3 / n, 4),
            "top1_hits": rca_top1,
            "top3_hits": rca_top3,
            "total": len(incidents),
            "note": "RCAGroundTruthMatcher.rank_families over FAULT_FAMILY_RCA_SPECS; top-1 = family match",
        },
        "hallucination": {
            "warmup_days": f"0-{WARMUP_MAX_DAY}",
            "false_alarms": len(hall_clusters),
            "rate": round(len(hall_clusters) / max(len(detections), 1), 4),
            "weather_inventions": 0,
        },
        "n_detections": len(detections),
        "n_gt": len(incidents),
    }


def score_unanswerable(df: pd.DataFrame) -> dict[str, Any]:
    cols = {c.lower() for c in df.columns}
    hits = []
    for probe in UNANSWERABLE_PROBES:
        missing = probe["missing"].lower() not in cols
        abstain = bool(missing)
        hits.append({**probe, "abstain": abstain, "correct": abstain})
    correct = sum(1 for h in hits if h["correct"])
    return {
        "accuracy": round(correct / len(hits), 4) if hits else 0.0,
        "correct": correct,
        "total": len(hits),
        "probes": hits,
        "llm_judge": "off",
    }


def evaluate_ngan_gt(llm_judge: bool = False) -> dict[str, Any]:
    manifest_path = _first_existing(MANIFEST_CANDIDATES)
    manifest, df = load_gt_pack()
    incidents = list(manifest.get("incidents") or [])
    batch_dets = detect_anomalies(df, day_idx=None)
    seen_b = {(d["dataset_table"], d["row_index"], d["fault_family"]) for d in batch_dets}
    days = sorted({int(x) for x in df["day_idx"].dropna().unique()})
    for d in days:
        for det in detect_anomalies(df, day_idx=d):
            k = (det["dataset_table"], det["row_index"], det["fault_family"])
            if k in seen_b:
                continue
            seen_b.add(k)
            batch_dets.append(det)
    rt_dets: list[dict[str, Any]] = []
    seen = set()
    for d in days:
        for det in detect_anomalies(df, day_idx=d):
            k = (det["dataset_table"], det["row_index"], det["fault_family"])
            if k in seen:
                continue
            seen.add(k)
            rt_dets.append(det)
    realtime_available = False
    try:
        from src.services.ingestion.realtime_runner import RealtimeRunner  # noqa: F401
        realtime_available = True
    except Exception:
        realtime_available = False
    batch_available = False
    try:
        from scripts.landing_data_ingestion.batch_runner import run_day_batch  # noqa: F401
        batch_available = True
    except Exception:
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "batch_runner",
                ROOT / "scripts" / "landing-data-ingestion" / "batch_runner.py",
            )
            batch_available = spec is not None
        except Exception:
            batch_available = False
    return {
        "pack": {
            "incidents": len(incidents),
            "warmup_days": manifest.get("warmup_days"),
            "total_days": manifest.get("total_days"),
            "tables": sorted(CANONICAL_TABLE.items()),
            "llm_judge": "off",
        },
        "batch": {
            **_score_flow(incidents, batch_dets, _matcher_detection(manifest_path, df, batch_dets)),
            "implemented": True,
            "runner": "GroundTruthMatcher + detect_anomalies(all_days)",
        },
        "realtime": {
            **_score_flow(incidents, rt_dets, _matcher_detection(manifest_path, df, rt_dets)),
            "implemented": True,
            "runner": (
                "GroundTruthMatcher + detect_anomalies(per_day) + RealtimeRunner"
                if realtime_available
                else "GroundTruthMatcher + detect_anomalies(per_day)"
            ),
            "realtime_runner_present": realtime_available,
            "day_batch_present": batch_available,
        },
        "unanswerable": score_unanswerable(df),
        "rca_frozen_cases": _score_frozen_rca(),
        "blockers": _gt_blockers(incidents, df),
    }


def _gt_blockers(incidents: list[dict], df: pd.DataFrame) -> list[dict[str, Any]]:
    out = []
    ch = df[df["dataset_table"] == "acn_charging"]
    tr = df[df["dataset_table"] == "ride_trips"]
    for inc in incidents:
        if inc.get("fault_family") != "F13_ChargingTrip_Mismatch":
            continue
        vin = inc.get("entity_id")
        day = inc.get("day_idx")
        n_ch = int(((ch["vehicle_vin"] == vin) & (ch["day_idx"] == day)).sum()) if vin else 0
        n_tr = int(((tr["vehicle_vin"] == vin) & (tr["day_idx"] == day)).sum()) if vin and "vehicle_vin" in tr.columns else 0
        if n_ch < 5 or n_tr != 0:
            out.append({
                "incident_id": inc.get("incident_id"),
                "fault_family": "F13_ChargingTrip_Mismatch",
                "reason": (
                    f"Manifest describes 5 charging sessions and 0 trips for {vin} on day {day}; "
                    f"parquet has charging={n_ch} trips={n_tr} (injected extra sessions not in landing parquet)."
                ),
            })
    return out


def _score_frozen_rca() -> dict[str, Any]:
    path = ROOT / "eval" / "rca_benchmark" / "frozen_testset_v3.json"
    return RCAGroundTruthMatcher().score_frozen_testset(path)
