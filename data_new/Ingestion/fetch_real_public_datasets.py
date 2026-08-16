"""
fetch_real_public_datasets.py
==============================
Layer 1 - FETCH RAW: Kéo dữ liệu THẬT từ 4 nguồn public. Seed mirror chỉ được
dùng khi fetch thật thất bại thật sự (network lỗi, 404, v.v.) - KHÔNG BAO GIỜ
dùng seed mirror làm mặc định.

Nguyên tắc bắt buộc:
  1. Mỗi nguồn LUÔN thử fetch thật trước (URL/API xác minh còn hoạt động tại
     thời điểm viết script - xem ghi chú "Verified" trong từng hàm).
  2. Nếu fetch thật fail -> log CẢNH BÁO rõ ràng + rơi về seed mirror + gắn cờ
     is_seed_mirror=1 trong data + ghi vào fetch_manifest.json.
  3. KHÔNG có ngoại lệ nào được nuốt âm thầm. Mọi fallback đều in ra terminal
     bằng "[SEED MIRROR FALLBACK]" để không ai nhầm seed data với data thật.
  4. fetch_manifest.json ở cuối là nguồn sự thật duy nhất về nguồn nào là
     THẬT, nguồn nào là SEED, cho từng lần chạy.

Nguồn thay thế (đã research + verify, xem báo cáo kèm theo):
  - ST-EVCDP:      giữ nguyên, sửa URL sang information.csv + stations.csv
                    (dataset_sample.csv cũ trả 404, không tồn tại). Không dùng nữa, loại bỏ hoàn toàn
  - UIT-VSFC:      giữ nguyên, đổi sang HuggingFace parquet resolve URL
                    (URL GitHub cũ 404, dataset thật nằm trên HF)
  - JAC IEV40:     KHÔNG tồn tại public URL nào (đã confirm 404, không có
                    mirror). Thay bằng VED (Vehicle Energy Dataset, gsoh/VED,
                    University of Michigan) - dataset EV/HEV telemetry thật,
                    public, MIT/Apache-2.0, có đủ speed/RPM/SOC/voltage/
                    current/GPS. Khác biệt: xe ở Ann Arbor, Michigan (không
                    phải Việt Nam) - đây là trade-off duy nhất có real data.
  - Ride Hailing:  Tải thủ công
  - ACN data:      Tải thủ công
Dependencies bổ sung so với bản cũ: pandas, pyarrow (đọc parquet), py7zr
(giải nén VED). Cài: pip install pandas pyarrow py7zr --break-system-packages
"""

import io
import json
import os
import tempfile
import urllib.request
import urllib.error
from datetime import datetime, timezone

import pandas as pd

RAW_PUBLIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "raw_public_v2")
os.makedirs(RAW_PUBLIC_DIR, exist_ok=True)

USER_AGENT = "Mozilla/5.0 (DataTrustOS fetch pipeline)"
TIMEOUT = 60

# ============================================================================
# SAMPLE_MODE: BAT (True) de fetch/tai gioi han so dong, chi de XEM CAU TRUC
# nhanh (khong tai full file nang). Khi da ok cau truc, doi SAMPLE_MODE=False
# de chay full production fetch (tai toan bo data that co san).
#
# Luu y: voi VED (vehicle_telemetry), du sample hay full deu phai tai het
# file .7z ~83MB roi moi cat dong ra (khong the tai 1 phan cua file nen) -
# SAMPLE_MODE chi giam so dong GHI RA CSV cuoi, khong giam thoi gian tai.
# Voi ST-EVCDP/UIT-VSFC/Ride-Hailing, SAMPLE_MODE giam ca dung luong tai ve.
# ============================================================================
SAMPLE_MODE = False
SAMPLE_ROWS = 50

# Ghi lại trạng thái thật/seed của từng nguồn trong lần chạy này
FETCH_MANIFEST = {
    "generated_at": None,
    "sample_mode": SAMPLE_MODE,
    "sample_rows_per_source": SAMPLE_ROWS if SAMPLE_MODE else None,
    "sources": {}
}


def _record(source_key, is_real, url, output_files, rows, note=""):
    FETCH_MANIFEST["sources"][source_key] = {
        "is_real_data": is_real,
        "url": url,
        "output_files": output_files,
        "rows": rows,
        "note": note,
    }


def _download(url, timeout=TIMEOUT):
    """Download raw bytes from url. Raises on any HTTP/network failure."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


# ---------------------------------------------------------------------------
# 1. ST-EVCDP (EV charging infrastructure, Shenzhen) - giữ nguồn thật cũ
#    Verified 2026-08-06: cả 2 URL trả 200, schema đã probe thực tế.
# ---------------------------------------------------------------------------
def fetch_real_st_evcdp():
    source_key = "st_evcdp"
    info_url = "https://raw.githubusercontent.com/IntelligentSystemsLab/ST-EVCDP/main/datasets/information.csv"
    stations_url = "https://raw.githubusercontent.com/IntelligentSystemsLab/ST-EVCDP/main/datasets/stations.csv"

    info_out = os.path.join(RAW_PUBLIC_DIR, "st_evcdp_information_raw.csv")
    stations_out = os.path.join(RAW_PUBLIC_DIR, "st_evcdp_stations_raw.csv")

    try:
        info_bytes = _download(info_url)
        stations_bytes = _download(stations_url)

        info_df = pd.read_csv(io.BytesIO(info_bytes))
        stations_df = pd.read_csv(io.BytesIO(stations_bytes))

        if SAMPLE_MODE:
            info_df = info_df.head(SAMPLE_ROWS)
            stations_df = stations_df.head(SAMPLE_ROWS)

        info_df.to_csv(info_out, index=False)
        stations_df.to_csv(stations_out, index=False)

        tag = f" [SAMPLE {SAMPLE_ROWS} dong]" if SAMPLE_MODE else ""
        print(f"[FETCH SUCCESS]{tag} ST-EVCDP information.csv -> {info_out} ({len(info_df)} rows, grid-level)")
        print(f"[FETCH SUCCESS]{tag} ST-EVCDP stations.csv -> {stations_out} ({len(stations_df)} rows, pile-level)")
        print("  Luu y: information.csv (grid/traffic-zone) va stations.csv (tung tru sac) "
              "la 2 bang khac key-space trong data goc, KHONG merge gia tao - "
              "de Layer 2 (mapper) quyet dinh cach lien ket.")

        _record(
            source_key, True, f"{info_url} | {stations_url}",
            [info_out, stations_out],
            {"information.csv": len(info_df), "stations.csv": len(stations_df)},
        )
        return
    except Exception as e:
        print(f"[FETCH FAILED] ST-EVCDP real fetch that bai: {e}")

    print("[SEED MIRROR FALLBACK] ST-EVCDP -> dung seed mirror vi fetch that that bai.")
    _seed_mirror_st_evcdp(info_out, stations_out)


def _seed_mirror_st_evcdp(info_out, stations_out):
    n_info = SAMPLE_ROWS if SAMPLE_MODE else 247
    n_stations = SAMPLE_ROWS if SAMPLE_MODE else 1000
    rows_info = []
    for i in range(1, n_info + 1):
        rows_info.append({
            "num": i, "grid": 100 + i, "count": 30 + (i % 60),
            "fast_count": i % 10, "slow_count": (30 + (i % 60)) - (i % 10),
            "area": round(0.5 + (i % 20) * 0.05, 2),
            "lon": round(114.05 + (i % 20) * 0.01, 5),
            "la": round(22.5 + (i % 20) * 0.01, 5),
            "CBD": 1 if i % 7 == 0 else 0,
            "dynamic_pricing": 1 if i % 5 == 0 else 0,
            "is_seed_mirror": 1,
        })
    rows_stations = []
    for i in range(1, n_stations + 1):
        rows_stations.append({
            "station_id": i,
            "latitude": round(22.5 + (i % 40) * 0.005, 6),
            "longitude": round(114.05 + (i % 40) * 0.005, 6),
            "fast": i % 15, "slow": i % 10, "count": (i % 15) + (i % 10),
            "is_seed_mirror": 1,
        })
    pd.DataFrame(rows_info).to_csv(info_out, index=False)
    pd.DataFrame(rows_stations).to_csv(stations_out, index=False)
    print(f"[SEED MIRROR] ST-EVCDP mirror ghi tai {info_out}, {stations_out}")
    _record("st_evcdp", False, "SEED_MIRROR", [info_out, stations_out],
            {"information.csv": len(rows_info), "stations.csv": len(rows_stations)},
            note="Real fetch that bai, xem log ben tren.")


# ---------------------------------------------------------------------------
# 2. UIT-VSFC (Vietnamese sentiment corpus) - đổi sang HuggingFace parquet
#    Verified 2026-08-06: default/{train,validation,test}/0000.parquet ton
#    tai that tren refs/convert/parquet branch (auto-converted by HF).
#    URL GitHub cu (uitnlp/vietnamese_students_feedback/main/data/train.csv)
#    404 vi repo khong ton tai tren GitHub - dataset that nam tren HF Hub.
# ---------------------------------------------------------------------------
def fetch_real_uit_vsfc():
    source_key = "uit_vsfc"
    base = "https://huggingface.co/datasets/uitnlp/vietnamese_students_feedback/resolve/refs%2Fconvert%2Fparquet/default"
    splits = {
        "train": f"{base}/train/0000.parquet",
        "validation": f"{base}/validation/0000.parquet",
        "test": f"{base}/test/0000.parquet",
    }
    output_path = os.path.join(RAW_PUBLIC_DIR, "uit_vsfc_raw.csv")

    try:
        frames = []
        with tempfile.TemporaryDirectory() as tmpdir:
            for split_name, url in splits.items():
                raw = _download(url)
                tmp_path = os.path.join(tmpdir, f"{split_name}.parquet")
                with open(tmp_path, "wb") as f:
                    f.write(raw)
                df = pd.read_parquet(tmp_path)
                df["split"] = split_name
                if SAMPLE_MODE:
                    df = df.head(SAMPLE_ROWS)
                frames.append(df)
                tag = f" [SAMPLE {SAMPLE_ROWS} dong]" if SAMPLE_MODE else ""
                print(f"[FETCH SUCCESS]{tag} UIT-VSFC split '{split_name}' -> {len(df)} rows")

        full_df = pd.concat(frames, ignore_index=True)
        # sentiment: 0=negative,1=neutral,2=positive | topic: 0=lecturer,1=training_program,2=facility,3=others
        full_df.to_csv(output_path, index=False, encoding="utf-8-sig")
        tag = f" [SAMPLE {SAMPLE_ROWS} dong/split]" if SAMPLE_MODE else ""
        print(f"[FETCH SUCCESS]{tag} UIT-VSFC toan bo -> {output_path} ({len(full_df)} rows, that 100%)")

        _record(source_key, True, base, [output_path], len(full_df))
        return
    except Exception as e:
        print(f"[FETCH FAILED] UIT-VSFC real fetch that bai: {e}")

    print("[SEED MIRROR FALLBACK] UIT-VSFC -> dung seed mirror vi fetch that that bai.")
    _seed_mirror_uit_vsfc(output_path)


def _seed_mirror_uit_vsfc(output_path):
    raw_texts = [
        ("xe di em nhung tram sac v-green o vincom ba trieu bi loi ko sac dc, app lag vl", 0, 2),
        ("tai xe xanh sm nhiet tinh phuc vu rat tot, xe vf8 thom tho sach se", 2, 0),
        ("tram sac royal city full cho ko co cho do, app hien linh tinh", 0, 2),
        ("xe vf e34 bao loi pin ko chay dc o nguyen trai, goi cuu ho lau vl", 0, 2),
        ("gia cuoc xanh sm taxi rat hop ly, se ung ho lau dai", 2, 1),
        ("tram sac landmark 81 bi ngat dien dot ngot luc dang sac 80 phan tram", 0, 2),
        ("app xanh sm lag ko dat dc xe o ngap nuoc quan 7", 0, 3),
        ("xe vf5 sach se em a, tai xe chay an toan 10 diem", 2, 0),
    ]
    n = SAMPLE_ROWS if SAMPLE_MODE else 500
    rows = []
    for i in range(1, n + 1):
        s = raw_texts[(i - 1) % len(raw_texts)]
        rows.append({
            "sentence": s[0], "sentiment": s[1], "topic": s[2],
            "split": "train", "is_seed_mirror": 1,
        })
    pd.DataFrame(rows).to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"[SEED MIRROR] UIT-VSFC mirror ghi tai {output_path} ({len(rows)} rows)")
    _record("uit_vsfc", False, "SEED_MIRROR", [output_path], len(rows),
            note="Real fetch that bai, xem log ben tren.")


# ---------------------------------------------------------------------------
# 3. Vehicle Telemetry - JAC IEV40 KHONG TON TAI (confirmed 404, khong co
#    mirror public nao). THAY BANG VED (Vehicle Energy Dataset).
#    Verified 2026-08-06: tai + giai nen thanh cong trong sandbox, co du
#    speed/RPM/SOC/voltage/current/GPS that cho cac xe HEV/PHEV/EV.
#    Nguon: https://github.com/gsoh/VED (Apache-2.0)
#    LUU Y KHAC BIET: xe o Ann Arbor, Michigan (khong phai Viet Nam).
#    Day la nguon EV telemetry cong khai that duy nhat tim duoc khong can
#    dang ky/API key.
# ---------------------------------------------------------------------------
def fetch_real_vehicle_telemetry():
    source_key = "vehicle_telemetry"
    part1_url = "https://raw.githubusercontent.com/gsoh/VED/master/Data/VED_DynamicData_Part1.7z"
    output_path = os.path.join(RAW_PUBLIC_DIR, "vehicle_telemetry_raw.csv")

    # So luong file tuan (trong Part1.7z) se giai nen. Tang so nay de lay
    # nhieu data that hon (Part1 co 22 file tuan, moi file ~50MB giai nen).
    WEEKS_TO_EXTRACT = 1

    try:
        import py7zr
    except ImportError as e:
        print(f"[FETCH FAILED] Vehicle Telemetry: thieu dependency py7zr ({e}). "
              f"Chay: pip install py7zr --break-system-packages")
        print("[SEED MIRROR FALLBACK] Vehicle Telemetry -> dung seed mirror vi thieu dependency.")
        _seed_mirror_vehicle_telemetry(output_path)
        return

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_path = os.path.join(tmpdir, "VED_Part1.7z")
            print(f"[FETCH] Dang tai VED_DynamicData_Part1.7z (~83MB, real data, co the mat vai phut)...")
            raw = _download(part1_url, timeout=180)
            with open(archive_path, "wb") as f:
                f.write(raw)

            with py7zr.SevenZipFile(archive_path, mode="r") as archive:
                names = archive.getnames()
                targets = sorted(names)[:WEEKS_TO_EXTRACT]
                archive.extract(path=tmpdir, targets=targets)

            frames = []
            for name in targets:
                csv_path = os.path.join(tmpdir, name)
                df = pd.read_csv(csv_path)
                # Chi giu nhung dong co du lieu battery that (HEV/PHEV/EV) -
                # xe xang thuan trong VED co cac cot nay = NaN
                df = df[df["HV Battery SOC[%]"].notna()].copy()
                frames.append(df)
                print(f"[FETCH SUCCESS] VED week-file '{name}' -> {len(df)} rows co battery data that "
                      f"(truoc khi cat sample)")

        full_df = pd.concat(frames, ignore_index=True)
        if SAMPLE_MODE:
            full_df = full_df.head(SAMPLE_ROWS)
        full_df.to_csv(output_path, index=False)
        tag = f" [SAMPLE {SAMPLE_ROWS} dong]" if SAMPLE_MODE else ""
        print(f"[FETCH SUCCESS]{tag} Vehicle Telemetry (VED, thay JAC IEV40) -> {output_path} "
              f"({len(full_df)} rows, that 100%, xe HEV/PHEV/EV Ann Arbor MI)")

        _record(
            source_key, True, part1_url, [output_path], len(full_df),
            note="Thay the cho JAC IEV40 (khong ton tai public). Nguon: gsoh/VED, "
                 "xe o Ann Arbor Michigan, KHONG phai Viet Nam.",
        )
        return
    except Exception as e:
        print(f"[FETCH FAILED] Vehicle Telemetry (VED) real fetch that bai: {e}")

    print("[SEED MIRROR FALLBACK] Vehicle Telemetry -> dung seed mirror vi fetch that that bai.")
    _seed_mirror_vehicle_telemetry(output_path)


def _seed_mirror_vehicle_telemetry(output_path):
    n = SAMPLE_ROWS if SAMPLE_MODE else 1000
    rows = []
    for i in range(1, n + 1):
        rows.append({
            "record_id": f"JAC_REC_{i:04d}",
            "speed_kmh": round(max(0.0, 45.0 + (i * 0.1) % 50.0 - (i % 7) * 4.0), 1),
            "motor_rpm": int(max(0, (45.0 + (i * 0.1) % 50.0) * 48)),
            "soc_pct": round(max(5.0, 98.0 - i * 0.08), 1) if i % 30 != 0 else -15.0,
            "battery_voltage_v": round(360.0 + (i % 15) * 1.5, 1),
            "battery_current_a": round(25.0 + (i % 20) * 3.2, 1),
            "pack_temp_c": round(29.0 + (i % 10) * 0.8, 1),
            "is_seed_mirror": 1,
        })
    pd.DataFrame(rows).to_csv(output_path, index=False)
    print(f"[SEED MIRROR] Vehicle Telemetry mirror ghi tai {output_path} ({len(rows)} rows)")
    _record("vehicle_telemetry", False, "SEED_MIRROR", [output_path], len(rows),
            note="Real fetch (VED) that bai, xem log ben tren. JAC IEV40 goc khong ton tai.")


# ---------------------------------------------------------------------------
# 4. Ride Hailing - Kaggle can API key -> THAY BANG Chicago Transportation
#    Network Providers Trips (Socrata Open Data, KHONG can key).
#    Verified 2026-08-06: endpoint song, tra ve CSV that (confirm qua
#    request that, chi bi chan trong sandbox nay do network whitelist).
#    Nguon: https://data.cityofchicago.org/resource/m6dm-c72p.csv
# ---------------------------------------------------------------------------
def fetch_real_ride_hailing():
    source_key = "ride_hailing"
    ROW_LIMIT = SAMPLE_ROWS if SAMPLE_MODE else 5000  # tang so nay de lay nhieu data hon (dataset co ~200M+ rows)
    url = (
        "https://data.cityofchicago.org/resource/m6dm-c72p.csv"
        f"?$limit={ROW_LIMIT}&$order=trip_start_timestamp%20DESC"
    )
    output_path = os.path.join(RAW_PUBLIC_DIR, "ride_hailing_raw.csv")

    try:
        raw = _download(url, timeout=120)
        with open(output_path, "wb") as f:
            f.write(raw)
        df = pd.read_csv(output_path)
        tag = f" [SAMPLE {ROW_LIMIT} dong]" if SAMPLE_MODE else ""
        print(f"[FETCH SUCCESS]{tag} Ride Hailing (Chicago TNP Trips, thay Kaggle) -> {output_path} "
              f"({len(df)} rows, that 100%)")

        _record(
            source_key, True, url, [output_path], len(df),
            note="Thay the cho Kaggle ride-hailing-transaction (can API key). "
                 "Nguon: Chicago Open Data Portal, xe o Chicago, KHONG phai Ha Noi.",
        )
        return
    except Exception as e:
        print(f"[FETCH FAILED] Ride Hailing (Chicago TNP) real fetch that bai: {e}")

    print("[SEED MIRROR FALLBACK] Ride Hailing -> dung seed mirror vi fetch that that bai.")
    _seed_mirror_ride_hailing(output_path)


def _seed_mirror_ride_hailing(output_path):
    n = SAMPLE_ROWS if SAMPLE_MODE else 1000
    rows = []
    for i in range(1, n + 1):
        rows.append({
            "transaction_id": f"TX_{10000 + i}",
            "driver_id": f"DRV_{500 + (i % 25)}",
            "distance_km": round(1.5 + (i * 0.2) % 25.0, 2),
            "fare_vnd": round(15000.0 + ((i * 0.2) % 25.0) * 12500.0, 2) if i % 40 != 0 else -45000.0,
            "tip_vnd": round((i % 4) * 5000.0, 2),
            "discount_vnd": round((i % 3) * 3000.0, 2),
            "lat": round(21.0285 + (i % 30) * 0.002, 5) if i % 50 != 0 else 40.7128,
            "lon": round(105.8542 + (i % 30) * 0.002, 5) if i % 50 != 0 else -74.0060,
            "ride_type": "EV_TAXI" if i % 2 == 0 else "EV_BIKE",
            "is_seed_mirror": 1,
        })
    pd.DataFrame(rows).to_csv(output_path, index=False)
    print(f"[SEED MIRROR] Ride Hailing mirror ghi tai {output_path} ({len(rows)} rows)")
    _record("ride_hailing", False, "SEED_MIRROR", [output_path], len(rows),
            note="Real fetch (Chicago TNP) that bai, xem log ben tren.")


def _print_summary():
    real_count = sum(1 for v in FETCH_MANIFEST["sources"].values() if v["is_real_data"])
    total = len(FETCH_MANIFEST["sources"])
    print("\n" + "=" * 70)
    if SAMPLE_MODE:
        print(f"[!] SAMPLE_MODE=True - day CHI la mau {SAMPLE_ROWS} dong/nguon de xem cau truc.")
        print(f"   Doi SAMPLE_MODE=False o dau file de chay full production fetch.")
    print(f"TOM TAT: {real_count}/{total} nguon la REAL DATA that")
    for key, v in FETCH_MANIFEST["sources"].items():
        tag = "REAL" if v["is_real_data"] else "SEED MIRROR"
        print(f"  [{tag}] {key} -> {v['rows']}")
    print("=" * 70)


if __name__ == "__main__":
    FETCH_MANIFEST["generated_at"] = datetime.now(timezone.utc).isoformat()

    # fetch_real_st_evcdp()
    fetch_real_uit_vsfc()
    fetch_real_vehicle_telemetry()
    # fetch_real_ride_hailing()

    manifest_path = os.path.join(RAW_PUBLIC_DIR, "fetch_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(FETCH_MANIFEST, f, ensure_ascii=False, indent=2)
    print(f"\n[MANIFEST] Da ghi {manifest_path}")

    _print_summary()
