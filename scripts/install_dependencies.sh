#!/bin/bash
# Rongle Dependency Installer
# Installs system libs, sets up Python venv, and installs Node modules.

set -e

# Detect OS
OS="$(uname -s)"
echo "Detected OS: $OS"

# 1. System Dependencies (Linux/Debian-based)
if [ "$OS" == "Linux" ]; then
    if [ -f /etc/debian_version ]; then
        echo "Installing system dependencies via apt..."
        sudo apt-get update
        sudo apt-get install -y \
            python3-venv \
            python3-pip \
            libgl1-mesa-glx \
            libglib2.0-0 \
            libgpiod-dev \
            npm \
            v4l-utils
    fi
fi

# 2. Python Environment
echo "Setting up Python environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Created venv."
fi

source venv/bin/activate
pip install --upgrade pip
pip install -r rng_operator/requirements.txt
# Install training deps if needed
if [ -f rng_operator/training/requirements.txt ]; then
    pip install -r rng_operator/training/requirements.txt
fi

# 3. Node Modules
echo "Installing Node modules..."
if [ -f "package.json" ]; then
    npm install
fi

echo "✅ Setup Complete. Run 'source venv/bin/activate' to enter the environment."
