# Hardware Configuration Examples

## Raspberry Pi 4 / 5 (Linux Gadget Mode)

**File:** `/boot/config.txt`
```ini
[all]
dtoverlay=dwc2
```

**File:** `/etc/modules`
```
dwc2
libcomposite
```

**Setup Script (`scripts/setup_gadget.sh`):**
```bash
#!/bin/bash
cd /sys/kernel/config/usb_gadget/
mkdir -p g1
cd g1
echo 0x1d6b > idVendor # Linux Foundation
echo 0x0104 > idProduct # Multifunction Composite Gadget
echo 0x0100 > bcdDevice
echo 0x0200 > bcdUSB
mkdir -p strings/0x409
echo "fedcba9876543210" > strings/0x409/serialnumber
echo "Rongle AI" > strings/0x409/manufacturer
echo "Rongle Agent" > strings/0x409/product
# ... (Config functions for HID) ...
```

## NVIDIA Jetson Orin Nano

Jetson requires slightly different device tree overlays.

**Command:**
```bash
sudo /opt/nvidia/jetson-io/jetson-io.py
# Enable USB Gadget Mode via TUI
```

## Android (via USB Gadget Tool)

If running the Operator directly on a rooted Android phone (e.g., NetHunter).

**Termux Command:**
```bash
setprop sys.usb.config hid,adb
```
