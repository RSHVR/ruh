# Use Python 3.13 slim image
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies using uv
RUN uv pip install --system --no-cache fastapi uvicorn[standard] anthropic pydantic pydantic-settings psycopg[binary] redis celery python-dotenv httpx

# Copy application code
COPY . .

# Expose port (Cloud Run will set PORT env var)
EXPOSE 8080

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Health check - using httpx.Client for synchronous request
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import httpx; client = httpx.Client(); response = client.get('http://localhost:${PORT:-8080}/api/health', timeout=5.0); exit(0 if response.status_code == 200 else 1)" || exit 1

# Run uvicorn
CMD uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT}
