# Android Setup Guide

This guide details how to configure your Android device (specifically the Pixel 10, though applicable to others) for use with Rongle.

## 1. Vision Setup (IP Webcam)

To use your phone as the "Eye", we use the **IP Webcam** app to stream video over Wi-Fi.

1.  **Download:** Install [IP Webcam](https://play.google.com/store/apps/details?id=com.pas.webcam) from the Google Play Store.
2.  **Configure:**
    *   *Video Preferences:* Set resolution to 1920x1080 (or 1280x720 for lower latency).
    *   *Local Broadcasting:* Ensure it's enabled.
    *   *Port:* Default is 8080.
3.  **Start:** Scroll to the bottom and tap "Start Server".
4.  **Connect:** Note the IP address (e.g., `http://192.168.1.50:8080`). Enter this into `scripts/setup_pixel_test.py` or `rng_operator/config/settings.json`.

## 2. Frontend Access (Chrome)

To use your phone as the "Controller" (Dashboard):

1.  **Run Frontend:** On your PC, run `npm run dev -- --host` (or via `scripts/rongle start`).
2.  **Browser:** Open Chrome on Android.
3.  **URL:** Navigate to `http://<PC_IP>:5173`.
4.  **Install PWA:** Tap the "Install App" prompt or "Add to Home Screen" to get a fullscreen experience.

## 3. Advanced: Backend on Android (Termux)

*Experimental:* You can run the Python backend *directly* on the phone using Termux, removing the need for a PC backend.

1.  **Install Termux:** From F-Droid (Play Store version is outdated).
2.  **Install Packages:**
    ```bash
    pkg install python opencv
    ```
3.  **Clone Repo:**
    ```bash
    git clone https://github.com/Domusgpt/Rongle.git
    cd Rongle
    pip install -r rng_operator/requirements.txt
    ```
4.  **Run:**
    ```bash
    python -m rng_operator.main --dry-run
    ```
    *Note: Hardware HID injection requires root permissions and kernel support.*

## 4. Troubleshooting

*   **Laggy Video:** Reduce resolution in IP Webcam to 720p or 480p.
*   **Connection Refused:** Ensure PC firewall allows inbound connections on ports 8000 (Portal) and 5173 (Frontend).
*   **"HTTPS Required":** Some browser features (like PWA installation) prefer HTTPS. You may need to set up a local proxy (e.g., `mkcert`) if testing heavily.
