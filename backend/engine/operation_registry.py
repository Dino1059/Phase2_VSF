import hashlib
import hmac
import os
import re
from typing import Any, Dict, Optional, Callable


class OperationRegistry:
    """
    Generic Config-Driven Operation Registry for Privacy & Standardization Transformations.
    Supports MASK, HASH, ROUND, GENERALIZE, and REMOVE.
    """

    @staticmethod
    def mask_value(val: Any, prefix_len: int = 3, suffix_len: int = 2, mask_char: str = "*") -> str:
        """Che mờ chuỗi ký tự (giữ prefix_len đầu và suffix_len cuối)."""
        s = str(val or "").strip()
        if not s:
            return ""
        if len(s) <= prefix_len + suffix_len:
            return mask_char * len(s)
        return s[:prefix_len] + (mask_char * (len(s) - prefix_len - suffix_len)) + s[-suffix_len:]

    @staticmethod
    def hash_value(val: Any, algorithm: str = "sha256", salt_ref: str = "gsm_driver_salt_2026") -> str:
        """Băm bảo mật 1 chiều có salt bảo mật."""
        s = str(val or "").strip()
        if not s:
            return ""
        salt = os.getenv(salt_ref, salt_ref)
        hasher = hashlib.new(algorithm)
        hasher.update(f"{s}_{salt}".encode("utf-8"))
        return hasher.hexdigest()

    @staticmethod
    def hmac_sha256(val: Any, secret_ref: str) -> str:
        s = str(val or "").strip()
        if not s:
            return ""
        if not secret_ref:
            raise ValueError("HMAC_SHA256 requires secret_ref")
        secret = os.getenv(secret_ref)
        if not secret:
            raise ValueError(f"HMAC secret is unavailable for reference '{secret_ref}'")
        return hmac.new(secret.encode("utf-8"), s.encode("utf-8"), hashlib.sha256).hexdigest()

    @staticmethod
    def mask_email(val: Any, mask_char: str = "*", keep_domain: bool = True) -> str:
        value = str(val or "").strip()
        if not value:
            return ""
        if "@" not in value:
            return mask_char * len(value)
        local, domain = value.split("@", 1)
        masked = (local[:1] + mask_char * max(len(local) - 1, 1)) if local else mask_char
        return f"{masked}@{domain if keep_domain else mask_char * len(domain)}"

    @classmethod
    def mask_contact(cls, val: Any, **params: Any) -> str:
        value = str(val or "").strip()
        if "@" in value:
            return cls.mask_email(value, str(params.get("mask_char", "*")), bool(params.get("keep_domain", True)))
        return cls.mask_value(
            value,
            int(params.get("phone_prefix_len", params.get("prefix_len", 3))),
            int(params.get("phone_suffix_len", params.get("suffix_len", 2))),
            str(params.get("mask_char", "*")),
        )

    @staticmethod
    def mask_name(
        val: Any, mask_char: str = "*", keep_initials: bool = True,
        keep_first: Optional[bool] = None, **_: Any
    ) -> str:
        value = str(val or "").strip()
        if not value:
            return ""
        tokens = value.split()
        if keep_first is not None:
            keep_initials = bool(keep_first)
        if keep_initials:
            return " ".join(token[:1] + mask_char * max(len(token) - 1, 1) for token in tokens)
        return mask_char * len(value)

    @staticmethod
    def redact_pii_text(
        val: Any, replacement: str = "[REDACTED]", **_: Any
    ) -> str:
        value = str(val or "")
        value = re.sub(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?!\w)", replacement, value)
        return re.sub(r"(?<!\w)(?:\+?\d[\d .()-]{6,}\d)(?!\w)", replacement, value)

    @staticmethod
    def round_numeric(val: Any, decimals: int = 2) -> Optional[float]:
        """Làm tròn số thực (ví dụ tọa độ GPS đón khách)."""
        if val is None or val == "":
            return None
        try:
            return round(float(val), int(decimals))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def generalize_value(val: Any, method: str = "bucket", level: int = 10) -> str:
        """Tổng quát hóa giá trị số thành khoảng dải (k-anonymity)."""
        if val is None or val == "":
            return "UNKNOWN"
        try:
            num = float(val)
            lower = int(num // level) * level
            return f"{lower}-{lower + level - 1}"
        except (ValueError, TypeError):
            return str(val)

    @staticmethod
    def remove_value(val: Any = None) -> None:
        """Loại bỏ hoàn toàn trường dữ liệu."""
        return None

    @classmethod
    def get_handler(cls, operation_id: str) -> Callable:
        normalized = operation_id.strip().upper()
        mapping = {
            "MASK": cls.mask_value,
            "MASK_PHONE": cls.mask_value,
            "MASK_EMAIL": cls.mask_email,
            "MASK_CONTACT": cls.mask_contact,
            "MASK_NAME": cls.mask_name,
            "HASH": cls.hash_value,
            "HASH_SHA256": cls.hash_value,
            "HMAC_SHA256": cls.hmac_sha256,
            "ROUND": cls.round_numeric,
            "ROUND_DECIMAL": cls.round_numeric,
            "GENERALIZE": cls.generalize_value,
            "BUCKETIZE": cls.generalize_value,
            "REMOVE": cls.remove_value,
            "REDACT": cls.remove_value,
            "REDACT_PII_TEXT": cls.redact_pii_text,
        }
        handler = mapping.get(normalized)
        if not handler:
            raise ValueError(f"Unknown operation_id in OperationRegistry: '{operation_id}'")
        return handler

    @classmethod
    def execute(cls, operation_id: str, value: Any, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Validates parameters and executes the registered transformation operation.
        """
        handler = cls.get_handler(operation_id)
        valid_params = params or {}

        try:
            # Map parameters dynamically
            if operation_id.strip().upper() in ["MASK", "MASK_PHONE"]:
                p_len = int(valid_params.get("prefix_len", valid_params.get("prefix", 3)))
                s_len = int(valid_params.get("suffix_len", valid_params.get("suffix", 2)))
                m_char = str(valid_params.get("mask_char", "*"))
                return handler(value, prefix_len=p_len, suffix_len=s_len, mask_char=m_char)

            elif operation_id.strip().upper() == "MASK_EMAIL":
                return handler(value, mask_char=str(valid_params.get("mask_char", "*")), keep_domain=bool(valid_params.get("keep_domain", True)))

            elif operation_id.strip().upper() in ["MASK_CONTACT", "MASK_NAME", "REDACT_PII_TEXT"]:
                return handler(value, **valid_params)

            elif operation_id.strip().upper() == "HMAC_SHA256":
                secret_ref = str(valid_params.get("secret_ref") or valid_params.get("key_ref") or "")
                return handler(value, secret_ref=secret_ref)

            elif operation_id.strip().upper() in ["HASH", "HASH_SHA256"]:
                algo = str(valid_params.get("algorithm", "sha256"))
                salt_ref = str(valid_params.get("salt_ref", valid_params.get("salt", "gsm_driver_salt_2026")))
                return handler(value, algorithm=algo, salt_ref=salt_ref)

            elif operation_id.strip().upper() in ["ROUND", "ROUND_DECIMAL"]:
                decimals = int(valid_params.get("decimals", 2))
                return handler(value, decimals=decimals)

            elif operation_id.strip().upper() in ["GENERALIZE", "BUCKETIZE"]:
                method = str(valid_params.get("method", "bucket"))
                lvl = int(valid_params.get("level", valid_params.get("step", 10)))
                return handler(value, method=method, level=lvl)

            elif operation_id.strip().upper() in ["REMOVE", "REDACT"]:
                return handler(value)

            return handler(value, **valid_params)
        except Exception as exc:
            raise RuntimeError(f"Error executing operation '{operation_id}' on value: {exc}")
