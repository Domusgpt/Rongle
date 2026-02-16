# Production Deployment Guide

This guide explains how to deploy the Rongle Operator to a dedicated hardware device, such as a Raspberry Pi Zero 2 W, 4, or 5.

## Prerequisites

1.  **Hardware:**
    *   Raspberry Pi Zero 2 W (Recommended for stealth).
    *   MicroSD Card (16GB+).
    *   USB Micro-B to USB-A cable (Data enabled).
    *   HDMI-to-CSI Capture Card (e.g., TC358743).

2.  **OS:**
    *   Raspberry Pi OS Lite (64-bit recommended).
    *   SSH enabled.

## Step 1: Prepare the Pi

1.  Flash the OS to the SD card.
2.  Add `ssh` file to the boot partition to enable SSH.
3.  Configure Wi-Fi via `wpa_supplicant.conf` or `imager`.
4.  Boot the Pi and SSH into it: `ssh pi@raspberrypi.local`.

## Step 2: Clone Repository

```bash
sudo apt update && sudo apt install -y git
git clone https://github.com/Domusgpt/Rongle.git
cd Rongle
```

## Step 3: Run Deployment Script

We provide a script that handles:
*   Installing system dependencies (OpenCV, GPIO, etc.).
*   Configuring the Linux USB Gadget (`libcomposite`) to emulate a Keyboard and Mouse.
*   Setting up `systemd` services to start the agent on boot.

```bash
# Must be run as root
sudo ./scripts/deploy_production.sh
```

## Step 4: Configuration

Edit the settings file on the Pi:

```bash
sudo nano /opt/rongle/rng_operator/config/settings.json
```

Ensure `video_device` is set correctly (usually `/dev/video0` for CSI bridge).

## Step 5: Reboot & Verify

1.  Reboot the Pi: `sudo reboot`.
2.  Connect the Pi's USB data port (the one closer to the center on a Zero) to the Target Computer.
3.  The Target Computer should recognize a new USB Keyboard/Mouse device ("DomusGPT Rongle").
4.  Check status:
    ```bash
    systemctl status rongle-operator
    ```

## Hardware E-Stop

For safety in production, you **must** wire a physical button between **GPIO 17** and **GND**.
*   **Pressed (Closed):** Agent runs.
*   **Released (Open):** Agent halts immediately.
*   *Note: If you don't have a button yet, use `--software-estop` in the systemd unit file temporarily.*
