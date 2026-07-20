# Ruh backend — FastAPI on Cloudflare Containers / Cloud Run
FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install locked dependencies first for layer caching.
# Playwright browsers intentionally NOT installed: extraction_service (the only
# Playwright consumer) is not in the boot path; primary analysis uses client HTML.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PORT=8080

EXPOSE 8080

CMD uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT}
