"""
DataTrust OS: PII Guardrails & Pre-LLM Sanitizer
Compliant with Luật 91/2025/QH15 & GDPR Article 5(1)(c).
Ensures sensitive data (Phone, Email, VIN, GPS coordinates) are redacted
or masked BEFORE prompt payloads are sent to any LLM.
"""

import re
from typing import Dict, Any, Tuple, Optional


# Regex patterns for sensitive identifiers
PHONE_VN_REGEX = re.compile(r"(?:\+84|0)(?:3|5|7|8|9)\d{8}\b")
EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b")
VIN_REGEX = re.compile(r"\b(?:VF[0-9A-Z]{15}|VF[0-9A-Z_]{6,15})\b", re.IGNORECASE)
GPS_COORD_REGEX = re.compile(r"[-+]?\b\d{1,2}\.\d{4,8}\s*,\s*[-+]?\d{1,3}\.\d{4,8}\b")


def mask_phone(phone: str, prefix_len: int = 3, suffix_len: int = 2, mask_char: str = "*") -> str:
    """Mask phone number keeping prefix and suffix (e.g. 091*****89)."""
    if not phone or len(phone) <= prefix_len + suffix_len:
        return mask_char * len(str(phone))
    return phone[:prefix_len] + (mask_char * (len(phone) - prefix_len - suffix_len)) + phone[-suffix_len:]


def mask_email(email: str, mask_char: str = "*") -> str:
    """Mask email handle keeping initial character and domain."""
    if not email or "@" not in email:
        return mask_char * len(str(email))
    name, domain = email.split("@", 1)
    if len(name) <= 2:
        masked_name = name[0] + mask_char
    else:
        masked_name = name[0] + (mask_char * (len(name) - 2)) + name[-1]
    return f"{masked_name}@{domain}"


def mask_vin(vin: str) -> str:
    """Mask vehicle VIN keeping prefix and last 4 characters."""
    if not vin or len(vin) < 8:
        return "[VIN_REDACTED]"
    return f"{vin[:4]}****{vin[-4:]}"


def mask_gps(lat: float, lon: float, decimals: int = 2) -> Tuple[float, float]:
    """Generalize GPS coordinates to specified decimal places."""
    return round(float(lat), decimals), round(float(lon), decimals)


def pre_llm_guard(
    prompt: str,
    context_data: Optional[Dict[str, Any]] = None
) -> Tuple[str, Dict[str, Any]]:
    """
    Sanitize prompt and structured context before transmission to LLMs.
    Returns:
        (sanitized_prompt, guardrail_report)
    """
    redaction_counts = {
        "phones_masked": 0,
        "emails_masked": 0,
        "vins_masked": 0,
        "gps_generalized": 0
    }

    sanitized_prompt = prompt

    # 1. Mask Phone Numbers
    def _sub_phone(match):
        redaction_counts["phones_masked"] += 1
        return mask_phone(match.group(0))
    sanitized_prompt = PHONE_VN_REGEX.sub(_sub_phone, sanitized_prompt)

    # 2. Mask Emails
    def _sub_email(match):
        redaction_counts["emails_masked"] += 1
        return mask_email(match.group(0))
    sanitized_prompt = EMAIL_REGEX.sub(_sub_email, sanitized_prompt)

    # 3. Mask VINs
    def _sub_vin(match):
        redaction_counts["vins_masked"] += 1
        return mask_vin(match.group(0))
    sanitized_prompt = VIN_REGEX.sub(_sub_vin, sanitized_prompt)

    # 4. Mask GPS in prompt
    def _sub_gps(match):
        redaction_counts["gps_generalized"] += 1
        coords = match.group(0).split(",")
        lat, lon = float(coords[0].strip()), float(coords[1].strip())
        glat, glon = mask_gps(lat, lon, 2)
        return f"{glat}, {glon}"
    sanitized_prompt = GPS_COORD_REGEX.sub(_sub_gps, sanitized_prompt)

    # Sanitize context_data dictionary recursively if present
    sanitized_context = {}
    if context_data:
        sanitized_context = _sanitize_dict(context_data, redaction_counts)

    report = {
        "is_sanitized": sum(redaction_counts.values()) > 0,
        "law_references": ["Luật 91/2025/QH15", "GDPR Article 5(1)(c)"],
        "redactions": redaction_counts,
        "sanitized_context": sanitized_context
    }

    return sanitized_prompt, report


def _sanitize_dict(data: Any, counts: Dict[str, int]) -> Any:
    """Helper to recursively sanitize nested dictionary/list data."""
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            key_lower = k.lower()
            if any(p in key_lower for p in ["phone", "tel", "mobile"]):
                if isinstance(v, str):
                    sanitized[k] = mask_phone(v)
                    counts["phones_masked"] += 1
                else:
                    sanitized[k] = v
            elif "email" in key_lower:
                if isinstance(v, str):
                    sanitized[k] = mask_email(v)
                    counts["emails_masked"] += 1
                else:
                    sanitized[k] = v
            elif "vin" in key_lower:
                if isinstance(v, str):
                    sanitized[k] = mask_vin(v)
                    counts["vins_masked"] += 1
                else:
                    sanitized[k] = v
            elif any(g in key_lower for g in ["lat", "latitude", "gps"]):
                if isinstance(v, (int, float)):
                    sanitized[k] = round(float(v), 2)
                    counts["gps_generalized"] += 1
                else:
                    sanitized[k] = v
            elif any(g in key_lower for g in ["lon", "lng", "longitude"]):
                if isinstance(v, (int, float)):
                    sanitized[k] = round(float(v), 2)
                    counts["gps_generalized"] += 1
                else:
                    sanitized[k] = v
            else:
                sanitized[k] = _sanitize_dict(v, counts)
        return sanitized
    elif isinstance(data, list):
        return [_sanitize_dict(item, counts) for item in data]
    return data
