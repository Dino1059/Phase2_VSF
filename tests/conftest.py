import os
# Ensure pytest always uses isolated test database before any src modules are imported
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ["DUCKDB_PATH"] = os.path.join(_project_root, "data", "datatrust_test.duckdb")
os.environ.pop("GOOGLE_AI_API_KEY", None)
os.environ.pop("OPENAI_API_KEY", None)

from unittest.mock import AsyncMock
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.db.connection import get_db, DuckDBManager

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Session-level isolated DuckDB database for pytest."""
    db = get_db()
    db.init_schema()
    yield db

@pytest_asyncio.fixture
async def client():
    """Async HTTP client for testing API endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_llm():
    """Mock LLM to avoid calling OpenAI during tests.

    Usage in test:
        def test_something(mock_llm):
            # LLM calls will return mock response instead of hitting OpenAI
            ...
    """
    mock = AsyncMock()
    mock.ainvoke.return_value = AsyncMock(content="Mocked LLM response")
    return mock
