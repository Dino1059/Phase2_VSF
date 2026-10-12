import os
import pytest
from dotenv import load_dotenv

# Load .env if present
load_dotenv()


@pytest.fixture(autouse=True)
def ensure_datatrust_test_environment(monkeypatch):
    """Ensure minimal required environment variables exist for tests."""
    if not os.getenv("DATATRUST_PSEUDONYMIZATION_KEY"):
        monkeypatch.setenv("DATATRUST_PSEUDONYMIZATION_KEY", "test-datatrust-secret-key-12345")
