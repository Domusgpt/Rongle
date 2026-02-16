#!/bin/bash
# Rongle Production Deployment Script
# Targets: Raspberry Pi Zero 2 W / 4 / 5 (Debian Bookworm)

set -e

if [ "$(id -u)" -ne 0 ]; then
    echo "Error: This script must be run as root."
    exit 1
fi

echo "🦆 Rongle Production Deployment"
echo "--------------------------------"

APP_DIR="/opt/rongle"
USER="rongle"

# 1. Create User
if ! id "$USER" &>/dev/null; then
    echo "Creating user '$USER'..."
    useradd -m -s /bin/bash $USER
    usermod -aG video,gpio,input $USER
fi

# 2. Install System Deps
echo "Installing system dependencies..."
apt-get update
apt-get install -y python3-venv python3-pip libgl1-mesa-glx libglib2.0-0 libgpiod-dev v4l-utils git

# 3. Setup USB Gadget Script
echo "Configuring USB Gadget..."
GADGET_SCRIPT="/usr/local/bin/rongle_usb_gadget.sh"
cat << 'EOF' > $GADGET_SCRIPT
#!/bin/bash
# ConfigFS USB Gadget for Rongle (Keyboard + Mouse)

modprobe libcomposite
cd /sys/kernel/config/usb_gadget/
mkdir -p rongle && cd rongle

echo 0x1d6b > idVendor  # Linux Foundation
echo 0x0104 > idProduct # Multifunction Composite Gadget
echo 0x0100 > bcdDevice
echo 0x0200 > bcdUSB

mkdir -p strings/0x409
echo "fedcba9876543210" > strings/0x409/serialnumber
echo "DomusGPT" > strings/0x409/manufacturer
echo "Rongle Operator" > strings/0x409/product

# Keyboard
mkdir -p functions/hid.usb0
echo 1 > functions/hid.usb0/protocol
echo 1 > functions/hid.usb0/subclass
echo 8 > functions/hid.usb0/report_length
echo -ne \\x05\\x01\\x09\\x06\\xa1\\x01\\x05\\x07\\x19\\xe0\\x29\\xe7\\x15\\x00\\x25\\x01\\x75\\x01\\x95\\x08\\x81\\x02\\x95\\x01\\x75\\x08\\x81\\x03\\x95\\x05\\x75\\x01\\x05\\x08\\x19\\x01\\x29\\x05\\x91\\x02\\x95\\x01\\x75\\x03\\x91\\x03\\x95\\x06\\x75\\x08\\x15\\x00\\x25\\x65\\x05\\x07\\x19\\x00\\x29\\x65\\x81\\x00\\xc0 > functions/hid.usb0/report_desc

# Mouse
mkdir -p functions/hid.usb1
echo 2 > functions/hid.usb1/protocol
echo 1 > functions/hid.usb1/subclass
echo 4 > functions/hid.usb1/report_length
echo -ne \\x05\\x01\\x09\\x02\\xa1\\x01\\x09\\x01\\xa1\\x00\\x05\\x09\\x19\\x01\\x29\\x03\\x15\\x00\\x25\\x01\\x95\\x03\\x75\\x01\\x81\\x02\\x95\\x01\\x75\\x05\\x81\\x03\\x05\\x01\\x09\\x30\\x09\\x31\\x09\\x38\\x15\\x81\\x25\\x7f\\x75\\x08\\x95\\x03\\x81\\x06\\xc0\\xc0 > functions/hid.usb1/report_desc

mkdir -p configs/c.1/strings/0x409
echo "Config 1: ECM network" > configs/c.1/strings/0x409/configuration
echo 250 > configs/c.1/MaxPower

ln -s functions/hid.usb0 configs/c.1/
ln -s functions/hid.usb1 configs/c.1/

ls /sys/class/udc > UDC
EOF
chmod +x $GADGET_SCRIPT

# 4. Deploy Code
echo "Deploying code to $APP_DIR..."
mkdir -p $APP_DIR
cp -r . $APP_DIR
chown -R $USER:$USER $APP_DIR

# 5. Install Python Deps in Venv
echo "Installing Python environment..."
su - $USER -c "python3 -m venv $APP_DIR/venv"
su - $USER -c "$APP_DIR/venv/bin/pip install -r $APP_DIR/rng_operator/requirements.txt"

# 6. Systemd Service (USB Gadget)
echo "Creating systemd service for USB Gadget..."
cat << EOF > /etc/systemd/system/rongle-usb.service
[Unit]
Description=Rongle USB Gadget Config
After=network.target

[Service]
Type=oneshot
ExecStart=$GADGET_SCRIPT
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

# 7. Systemd Service (Operator)
echo "Creating systemd service for Operator..."
cat << EOF > /etc/systemd/system/rongle-operator.service
[Unit]
Description=Rongle Agentic Operator
After=rongle-usb.service network.target

[Service]
User=$USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/python -m rng_operator.main
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1
# Add GEMINI_API_KEY here or in an env file if needed

[Install]
WantedBy=multi-user.target
EOF

# 8. Enable Services
echo "Enabling services..."
systemctl daemon-reload
systemctl enable rongle-usb.service
systemctl enable rongle-operator.service

echo "✅ Deployment Complete!"
echo "Reboot the Pi to activate USB Gadget mode."
echo "Config file at: $APP_DIR/rng_operator/config/settings.json"
