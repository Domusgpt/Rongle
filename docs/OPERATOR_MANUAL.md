# Operator Manual: Hardware Setup

This manual guides you through setting up the **Rongle Operator** on a Raspberry Pi 4/5 or similar Linux Single Board Computer (SBC).

## Prerequisites

*   **Hardware:**
    *   Raspberry Pi 4 or 5 (4GB+ RAM recommended).
    *   HDMI Capture Card (USB).
    *   USB-C Data/Power Splitter (to enable Gadget Mode + Power).
*   **OS:** Raspberry Pi OS (Bookworm or newer).

## Step 1: Enable USB Gadget Mode

The Pi needs to act as a keyboard/mouse.

1.  Edit `/boot/firmware/config.txt` (or `/boot/config.txt`):
    ```ini
    dtoverlay=dwc2
    ```
2.  Edit `/etc/modules`:
    ```
    dwc2
    libcomposite
    ```
3.  Reboot.

## Step 2: Install Rongle Operator

1.  Clone the repository:
    ```bash
    git clone https://github.com/Domusgpt/Rongle.git
    cd Rongle
    ```
2.  Run the installer:
    ```bash
    ./scripts/install_operator.sh
    ```
    *This installs Python dependencies, sets up the virtualenv, and configures the `rongle-operator` systemd service.*

## Step 3: Configuration

Edit `rng_operator/config/settings.json`:

```json
{
  "camera_index": 0,
  "auth_token": "generate-a-secure-uuid-here",
  "policy": "strict"
}
```

## Step 4: Verification

1.  Start the service:
    ```bash
    sudo systemctl start rongle-operator
    ```
2.  Check logs:
    ```bash
    journalctl -u rongle-operator -f
    ```
3.  Connect your phone (Frontend) to the Pi's IP address.

## Maintenance

*   **Update:** `git pull && ./scripts/update.sh`
*   **Logs:** stored in `/var/log/rongle/`
