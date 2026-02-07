# Dockerfile for Rongle Portal (FastAPI)
FROM python:3.11-slim-bookworm

WORKDIR /app

# Install system dependencies
# - curl: for healthchecks
# - libpq-dev: for postgres (psycopg2/asyncpg build if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY portal/requirements.txt ./portal/requirements.txt
COPY rongle_operator/requirements.txt ./rongle_operator/requirements.txt

# Install Python deps
# We install portal deps first
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r portal/requirements.txt && \
    # Install asyncpg explicitly for Postgres support
    pip install --no-cache-dir asyncpg

# Copy source code
# We copy the whole context to support potential shared libs later,
# but specifically we need 'portal' package.
COPY portal ./portal

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV HOST=0.0.0.0

# Run
CMD ["uvicorn", "portal.app:app", "--host", "0.0.0.0", "--port", "8000"]
