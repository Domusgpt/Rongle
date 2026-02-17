# rng_operator/Dockerfile

FROM python:3.12-slim

# Install system dependencies for OpenCV and HID
# libgl1-mesa-glx is needed for cv2
# libgpiod-dev is needed for hardware estop
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libgpiod2 \
    usbutils \
    v4l-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Entrypoint
CMD ["python", "-m", "rng_operator.main"]
