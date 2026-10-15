"""
Client gọi SoD Flow (hệ thống duyệt phiếu). Hai hệ thống nói chuyện qua HTTP có ký HMAC-SHA256 bằng bí mật dùng chung
DATATRUST_SHARED_SECRET. Chuỗi được ký: "{timestamp}\\n{METHOD}\\n{pathname}\\n{body}" (khớp lib/integrations/datatrust.ts của SoD).

Nguyên tắc: lỗi kết nối hoặc SoD lỗi 5xx -> SodUnavailable (đề xuất ở lại trạng thái chờ gửi, KHÔNG BAO GIỜ tự duyệt);
SoD từ chối 4xx -> SodRejected (kèm lý do để hiển thị).
"""

import os
import json
import time
import hmac
import hashlib
import urllib.request
import urllib.error
from typing import Any, Dict, Optional

from dotenv import load_dotenv

load_dotenv()

API_PREFIX = "/api/integrations/datatrust/tickets"
MAX_SKEW_SECONDS = 300


class SodUnavailable(Exception):
    """SoD Flow không trả lời được (mạng, timeout, 5xx)."""


class SodRejected(Exception):
    """SoD Flow từ chối yêu cầu (4xx)."""

    def __init__(self, status: int, payload: Dict[str, Any]):
        self.status = status
        self.payload = payload
        super().__init__(f"SoD Flow từ chối (HTTP {status}): {payload.get('message') or payload.get('error') or payload}")


def _secret() -> str:
    return os.getenv("DATATRUST_SHARED_SECRET", "")


def _base_url() -> str:
    return os.getenv("SOD_URL", "").rstrip("/")


def is_configured() -> bool:
    """Chỉ bật luồng duyệt qua SoD khi đã cấu hình địa chỉ và bí mật (>= 32 ký tự)."""
    return bool(_base_url()) and len(_secret()) >= 32


def sign(secret: str, timestamp: str, method: str, pathname: str, body: str) -> str:
    message = f"{timestamp}\n{method.upper()}\n{pathname}\n{body}"
    return hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def verify(secret: str, timestamp: str, signature: str, method: str, pathname: str, body: str,
           now: Optional[float] = None) -> Optional[str]:
    """Kiểm chữ ký của một request SoD gửi tới. Trả về None nếu hợp lệ, hoặc mã lý do từ chối."""
    if len(secret) < 32:
        return "integration_not_configured"
    try:
        age = abs((now if now is not None else time.time()) - float(timestamp))
    except (TypeError, ValueError):
        return "stale_or_missing_timestamp"
    if not timestamp.isdigit() or age > MAX_SKEW_SECONDS:
        return "stale_or_missing_timestamp"
    expected = sign(secret, timestamp, method, pathname, body)
    if not hmac.compare_digest(expected, signature or ""):
        return "bad_signature"
    return None


def _request(method: str, pathname: str, body: Optional[Dict[str, Any]] = None, timeout: float = 5.0,
             retries: int = 2) -> Dict[str, Any]:
    if not is_configured():
        raise SodUnavailable("Chưa cấu hình SOD_URL / DATATRUST_SHARED_SECRET.")
    raw = json.dumps(body, separators=(",", ":"), ensure_ascii=False) if body is not None else ""
    last: Optional[Exception] = None
    for attempt in range(retries + 1):
        # Ký lại mỗi lần thử để timestamp luôn mới
        ts = str(int(time.time()))
        req = urllib.request.Request(
            _base_url() + pathname,
            data=raw.encode("utf-8") if body is not None else None,
            method=method,
            headers={
                "Content-Type": "application/json",
                "X-Timestamp": ts,
                "X-Signature": sign(_secret(), ts, method, pathname, raw),
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as e:
            payload: Dict[str, Any] = {}
            try:
                payload = json.loads(e.read() or b"{}")
            except Exception:
                pass
            if 400 <= e.code < 500:
                raise SodRejected(e.code, payload)
            last = e  # 5xx: thử lại
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            last = e
        if attempt < retries:
            time.sleep(0.5 * (attempt + 1))
    raise SodUnavailable(f"SoD Flow không phản hồi: {last}")


def create_ticket(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Gửi đề xuất sang SoD để duyệt. Trả về {ticket_code, status, created, steps}."""
    return _request("POST", API_PREFIX, payload)


def get_ticket(ticket_code: str) -> Dict[str, Any]:
    """Lấy trạng thái phiếu và các quyết định duyệt."""
    return _request("GET", f"{API_PREFIX}/{ticket_code}")


def report_executed(ticket_code: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Báo SoD đã thực thi (ghi nhật ký kiểm toán bên SoD, không đổi trạng thái phiếu)."""
    return _request("POST", f"{API_PREFIX}/{ticket_code}/executed", payload)
