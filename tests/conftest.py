import os
import pytest
from dotenv import load_dotenv

# Test không được phụ thuộc cấu hình tích hợp SoD Flow trong .env cục bộ: tắt trước khi load .env
# (load_dotenv không ghi đè biến đã có). Test tích hợp tự bật lại bằng monkeypatch.
os.environ["SOD_URL"] = ""

# Load .env if present
load_dotenv()


@pytest.fixture(autouse=True)
def ensure_datatrust_test_environment(monkeypatch):
    """Ensure minimal required environment variables exist for tests."""
    if not os.getenv("DATATRUST_PSEUDONYMIZATION_KEY"):
        monkeypatch.setenv("DATATRUST_PSEUDONYMIZATION_KEY", "test-datatrust-secret-key-12345")
