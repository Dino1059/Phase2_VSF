import re
from typing import Dict, Any, List

# Teen code / Slang dictionary for Vietnamese customer feedback
TEEN_CODE_MAP = {
    "ko": "không",
    "k": "không",
    "khong": "không",
    "dc": "được",
    "duk": "được",
    "hok": "không",
    "tram sac": "trạm sạc",
    "v-green": "V-GREEN",
    "vincom": "Vincom",
    "app lag": "ứng dụng có độ trễ",
    "vl": "rất nhiều",
    "vll": "rất nhiều",
    "full": "đầy",
    "goc": "ngắt",
    "em": "êm",
    "sach se": "sạch sẽ",
    "nhiet tinh": "nhiệt tình",
    "dat xe": "đặt xe",
}

def normalize_vietnamese_text(text: str) -> str:
    """Normalizes Vietnamese teen code, abbreviations, and missing accents."""
    words = text.split()
    normalized_words = []
    for w in words:
        w_lower = w.lower().strip(".,!?")
        if w_lower in TEEN_CODE_MAP:
            normalized_words.append(TEEN_CODE_MAP[w_lower])
        else:
            normalized_words.append(w)
    return " ".join(normalized_words)

def extract_aspect_entities(text: str) -> Dict[str, Any]:
    """Extracts Location, Component, Error Type, and Sentiment Level from text."""
    normalized = normalize_vietnamese_text(text)
    lower_norm = text.lower() + " " + normalized.lower()
    
    # Location Extraction
    location = "Toàn quốc"
    if "vincom" in lower_norm or "ba trieu" in lower_norm:
        location = "Vincom Bà Triệu"
    elif "royal" in lower_norm:
        location = "Royal City"
    elif "landmark" in lower_norm:
        location = "Landmark 81"
    elif "ocean" in lower_norm:
        location = "Ocean Park"
    elif "nguyen trai" in lower_norm:
        location = "Nguyễn Trãi"
    elif "quan 7" in lower_norm:
        location = "Quận 7"
    elif "da nang" in lower_norm:
        location = "Đà Nẵng"
    elif "hcm" in lower_norm or "tphcm" in lower_norm:
        location = "TPHCM"
    elif "ha noi" in lower_norm:
        location = "Hà Nội"

    # Component Extraction
    component = "Dịch vụ chung"
    if "tram sac" in lower_norm or "v-green" in lower_norm:
        component = "Trạm sạc V-GREEN"
    elif "pin" in lower_norm or "soc" in lower_norm:
        component = "Pin xe VinFast"
    elif "tai xe" in lower_norm or "lai xe" in lower_norm:
        component = "Dịch vụ tài xế"
    elif "app" in lower_norm or "ung dung" in lower_norm:
        component = "Ứng dụng di động"
    elif "vf5" in lower_norm:
        component = "Xe VinFast VF5"
    elif "vf8" in lower_norm:
        component = "Xe VinFast VF8"
    elif "cuoc" in lower_norm or "gia" in lower_norm:
        component = "Giá cước"

    # Error classification
    error_type = "Bình thường / Khen ngợi"
    severity = "INFO"
    
    if any(k in lower_norm for k in ["lỗi", "không sạc", "ko sac", "hỏng", "ngắt", "báo lỗi pin", "quá nhiệt"]):
        error_type = "Lỗi thiết bị / Phần cứng trạm sạc"
        severity = "CRITICAL"
    elif any(k in lower_norm for k in ["lag", "không đặt được", "ko dat dc", "hiển thị linh tinh", "chậm"]):
        error_type = "Lỗi ứng dụng di động / Phần mềm"
        severity = "WARNING"
    elif any(k in lower_norm for k in ["đầy chỗ", "hết chỗ", "full", "lâu"]):
        error_type = "Lỗi tắc nghẽn hạ tầng"
        severity = "WARNING"

    return {
        "raw_text": text,
        "normalized_text": normalized,
        "location": location,
        "component": component,
        "error_type": error_type,
        "severity": severity
    }

def cross_validate_with_telemetry(aspect_data: Dict[str, Any], vgreen_logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Cross-validates unstructured customer feedback with structured V-GREEN telemetry logs."""
    loc = aspect_data.get("location")
    matched_log = None
    if vgreen_logs:
        for log in vgreen_logs:
            station_id = str(log.get("station_id", ""))
            if loc and (loc.lower().replace(" ", "_") in station_id.lower() or "vincom" in station_id.lower()):
                if log.get("status") in ("THERMAL_FAULT", "POWER_DROP") or float(log.get("station_temp_c", 0)) > 80:
                    matched_log = log
                    break

    validated = dict(aspect_data)
    if matched_log:
        validated["telemetry_verified"] = True
        validated["matched_station"] = matched_log.get("station_id")
        validated["matched_charger"] = matched_log.get("charger_id")
        validated["telemetry_evidence"] = f"Station temperature {matched_log.get('station_temp_c')}°C, status {matched_log.get('status')}"
    else:
        validated["telemetry_verified"] = False
        validated["telemetry_evidence"] = "No matching telemetry fault in selected timeframe"

    return validated
