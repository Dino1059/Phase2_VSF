FROM python:3.13-slim

WORKDIR /app

# Install uv cleanly
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-install-project --no-dev

# Copy source code and project directories
COPY src/ ./src/
COPY data_new/ ./data_new/
COPY schemas/ ./schemas/
COPY scripts/ ./scripts/

# Install project
RUN uv sync --frozen --no-dev

# Expose port
EXPOSE 8000

# Entrypoint
CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
