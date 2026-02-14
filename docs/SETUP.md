# Setup Guide

## Android (Browser) — Quick Start

### Requirements

- Android phone with Chrome 89+ (Web Serial support)
- Node.js 18+ on development machine
- Google Gemini API key ([Get one here](https://aistudio.google.com/apikey))
- (Optional) CH9329 USB-to-UART dongle for HID output

### Steps

```bash
# 1. Clone
git clone https://github.com/Domusgpt/Rongle.git
cd Rongle

# 2. Install
npm install

# 3. Set API key
echo "GEMINI_API_KEY=your_key_here" > .env.local

# 4. Run dev server
npm run dev
```

Open `http://<your-ip>:3000` on your Android phone (same WiFi network).

### Camera Setup

1. Grant camera permission when prompted
2. Point phone camera at the target computer's monitor
3. Position so the full screen is visible with minimal glare
4. The LiveView should show the camera feed with the green HUD overlay

### HID Output (Optional)

**Without HID dongle:** Rongle analyzes the screen and generates Ducky Script, but cannot inject input. Use clipboard mode to copy commands.

**With CH9329 dongle:**

1. Connect CH9329 dongle to target computer via USB
2. Connect dongle's UART pins to phone via USB OTG:
   - Use a USB-to-UART adapter (CP2102, FT232, etc.)
   - Or a direct UART OTG cable
3. In Rongle, click **USB Serial** in the HID Connection bar
4. Chrome will show a port selection dialog — choose the serial device
5. The HID status should change to "USB SERIAL" (green)

**CH9329 Wiring:**
```
Phone (USB OTG) ──► USB-UART adapter ──► CH9329 module ──► Target PC USB
                    TX → RX
                    RX → TX
                    GND → GND
```

Baud rate: 9600 (auto-configured by the HID bridge).

### Portal Mode (Optional)

To use the managed portal instead of a direct API key:

1. Start the portal server (see Portal section below)
2. In Rongle, tap the user icon to open the auth panel
3. Enter the portal URL (e.g., `http://192.168.1.100:8000`)
4. Register or log in
5. Create a device in the Device Manager panel
6. Enable "Route through Portal" in Config
7. VLM queries will now proxy through the portal with quota metering

---

## Raspberry Pi (Hardware Operator)

### Hardware Requirements

| Component | Specification | Purpose |
|-----------|--------------|---------|
| Raspberry Pi Zero 2 W | ARM Cortex-A53, 512MB | Operator device |
| HDMI-to-CSI adapter | Auvidea B101/B102 or similar | Screen capture |
| USB OTG cable | Micro-USB to USB-A | HID output to target |
| Momentary push button | Normally-closed, SPST | Emergency stop |
| MicroSD card | 16GB+ Class 10 | OS + operator software |
| Power supply | 5V 2.5A micro-USB | Reliable power |
| (Optional) HDMI cable | Standard HDMI | Target → capture card |

### Pi OS Setup

```bash
# Flash Raspberry Pi OS Lite (64-bit) to SD card
# Boot and SSH in

# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3-pip python3-venv libgpiod2 python3-opencv
```

### USB OTG HID Gadget Configuration

The Pi Zero 2 W's USB port can present itself as a USB HID device (keyboard + mouse) to the target computer.

```bash
# 1. Enable dwc2 overlay
echo "dtoverlay=dwc2" | sudo tee -a /boot/config.txt

# 2. Load modules on boot
echo "dwc2" | sudo tee -a /etc/modules
echo "libcomposite" | sudo tee -a /etc/modules

# 3. Create ConfigFS gadget setup script
sudo tee /usr/local/bin/setup-hid-gadget.sh << 'SCRIPT'
#!/bin/bash
set -e

GADGET=/sys/kernel/config/usb_gadget/rongle

# Create gadget
mkdir -p $GADGET
echo 0x1d6b > $GADGET/idVendor   # Linux Foundation
echo 0x0104 > $GADGET/idProduct  # Multifunction Composite Gadget
echo 0x0100 > $GADGET/bcdDevice
echo 0x0200 > $GADGET/bcdUSB

# Device strings
mkdir -p $GADGET/strings/0x409
echo "rongle001" > $GADGET/strings/0x409/serialnumber
echo "Rongle" > $GADGET/strings/0x409/manufacturer
echo "Agentic Operator" > $GADGET/strings/0x409/product

# Configuration
mkdir -p $GADGET/configs/c.1/strings/0x409
echo "Keyboard + Mouse" > $GADGET/configs/c.1/strings/0x409/configuration
echo 250 > $GADGET/configs/c.1/MaxPower

# --- Keyboard HID function ---
mkdir -p $GADGET/functions/hid.keyboard
echo 1 > $GADGET/functions/hid.keyboard/protocol
echo 1 > $GADGET/functions/hid.keyboard/subclass
echo 8 > $GADGET/functions/hid.keyboard/report_length
# Standard keyboard report descriptor
echo -ne "\x05\x01\x09\x06\xa1\x01\x05\x07\x19\xe0\x29\xe7\x15\x00\x25\x01\x75\x01\x95\x08\x81\x02\x95\x01\x75\x08\x81\x03\x95\x05\x75\x01\x05\x08\x19\x01\x29\x05\x91\x02\x95\x01\x75\x03\x91\x03\x95\x06\x75\x08\x15\x00\x25\x65\x05\x07\x19\x00\x29\x65\x81\x00\xc0" > $GADGET/functions/hid.keyboard/report_desc

# --- Mouse HID function ---
mkdir -p $GADGET/functions/hid.mouse
echo 2 > $GADGET/functions/hid.mouse/protocol
echo 1 > $GADGET/functions/hid.mouse/subclass
echo 4 > $GADGET/functions/hid.mouse/report_length
# Relative mouse report descriptor
echo -ne "\x05\x01\x09\x02\xa1\x01\x09\x01\xa1\x00\x05\x09\x19\x01\x29\x03\x15\x00\x25\x01\x95\x03\x75\x01\x81\x02\x95\x01\x75\x05\x81\x03\x05\x01\x09\x30\x09\x31\x09\x38\x15\x81\x25\x7f\x75\x08\x95\x03\x81\x06\xc0\xc0" > $GADGET/functions/hid.mouse/report_desc

# Link functions to configuration
ln -sf $GADGET/functions/hid.keyboard $GADGET/configs/c.1/
ln -sf $GADGET/functions/hid.mouse $GADGET/configs/c.1/

# Enable gadget
ls /sys/class/udc > $GADGET/UDC

echo "HID gadget configured: /dev/hidg0 (keyboard), /dev/hidg1 (mouse)"
SCRIPT

chmod +x /usr/local/bin/setup-hid-gadget.sh

# 4. Run on boot
sudo tee /etc/systemd/system/rongle-hid.service << 'SERVICE'
[Unit]
Description=Rongle HID Gadget Setup
After=sysinit.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/setup-hid-gadget.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
SERVICE

sudo systemctl enable rongle-hid
sudo reboot
```

After reboot, `/dev/hidg0` (keyboard) and `/dev/hidg1` (mouse) should exist.

### Emergency Stop Wiring

```
GPIO 17 (pin 11) ──── Normally-Closed Button ──── GND (pin 9)

  Button PRESSED  → circuit closed → GPIO reads LOW → operating
  Button RELEASED → circuit open   → GPIO reads HIGH → EMERGENCY STOP
```

The dead-man switch design means the operator must actively hold the button to allow operation. Releasing it (or disconnecting it) immediately halts all HID output.

### Install and Run Operator

```bash
cd Rongle

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install
pip install -r operator/requirements.txt

# Run
export GEMINI_API_KEY=your_key_here
python -m operator.main --goal "Open the terminal and type hello"

# Or development mode
python -m operator.main --dry-run --software-estop
```

### HDMI Capture Setup

Connect the HDMI output of the target computer to the CSI adapter on the Pi:

```
Target PC HDMI ──► HDMI-to-CSI adapter ──► Pi CSI ribbon cable
```

The frame grabber uses V4L2 (`/dev/video0`). Verify with:

```bash
v4l2-ctl --list-devices
v4l2-ctl --device=/dev/video0 --all
```

---

## Portal Server

### Requirements

- Python 3.11+
- (Production) PostgreSQL 15+
- Google Gemini API key

### Development Setup

```bash
cd Rongle

python3 -m venv .venv
source .venv/bin/activate
pip install -r portal/requirements.txt

export JWT_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")
export GEMINI_API_KEY=your_key_here

uvicorn portal.app:app --host 0.0.0.0 --port 8000 --reload
```

SQLite database auto-created at `./rongle.db`. API docs at `http://localhost:8000/docs`.

### Production Deployment

```bash
# Use PostgreSQL
export DATABASE_URL=postgresql+asyncpg://user:pass@db-host:5432/rongle

# Set secrets
export JWT_SECRET=<64-char-hex-string>
export ENCRYPTION_KEY=<32-char-hex-string>
export GEMINI_API_KEY=<key>

# Restrict CORS
export CORS_ORIGINS=https://rongle.yourdomain.com

# Run with uvicorn workers
uvicorn portal.app:app --host 0.0.0.0 --port 8000 --workers 4

# Or behind nginx/Caddy with TLS
```

### Systemd Service (Pi or Server)

```ini
[Unit]
Description=Rongle Portal API
After=network.target

[Service]
User=rongle
WorkingDirectory=/opt/rongle
ExecStart=/opt/rongle/.venv/bin/uvicorn portal.app:app --host 0.0.0.0 --port 8000
Restart=always
Environment=JWT_SECRET=<secret>
Environment=GEMINI_API_KEY=<key>
Environment=DATABASE_URL=sqlite+aiosqlite:///opt/rongle/data/rongle.db

[Install]
WantedBy=multi-user.target
```

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| Camera not working on Android | Permission denied or wrong facing mode | Check Chrome camera permissions. Rongle uses `facingMode: 'environment'` (back camera). |
| Web Serial not available | Browser doesn't support it | Use Chrome 89+ on Android. Firefox/Safari don't support Web Serial. |
| `/dev/hidg0` doesn't exist | OTG gadget not configured | Run `setup-hid-gadget.sh` and verify `dwc2` overlay is enabled. |
| Calibration fails | Cursor not detected | Ensure HDMI capture is active and frame grabber can read `/dev/video0`. Check resolution settings. |
| Portal returns 401 | Token expired | Frontend auto-refreshes, but if refresh token also expired, re-login. |
| VLM returns low confidence | Poor camera angle or glare | Adjust phone position. Reduce ambient light reflections on monitor. |
| CNN shows 0 detections | Random weights (no trained model) | Expected without pre-trained weights. Load trained model via `loadModelFromURL()`. |
| Rate limit 429 | Too many requests | Wait for window reset (60 seconds) or increase `RATE_LIMIT_PER_MINUTE`. |
