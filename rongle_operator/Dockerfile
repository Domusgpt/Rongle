# Dockerfile for Rongle Operator
FROM python:3.11-slim-bookworm

WORKDIR /app

# Install system dependencies
# - usbutils: for lsusb (debugging)
# - libglib2.0-0, libsm6, libxext6, libxrender-dev: common OpenCV deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    usbutils \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY rongle_operator/requirements.txt ./requirements.txt

# Install Python deps
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY rongle_operator ./rongle_operator

# Environment variables
ENV PYTHONUNBUFFERED=1
# Default to dry run in container unless devices mapped
ENV RONGLE_DRY_RUN=true

# Entrypoint
# We assume the main entry point is python -m rongle_operator.main or similar
# Based on previous analysis, there is a main.py inside rongle_operator.
CMD ["python", "-m", "rongle_operator.main"]
