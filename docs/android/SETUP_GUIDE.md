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

## 2. Frontend Options: Browser vs APK

You have two choices for running the Controller interface on your Pixel 10.

### Option A: Development Mode (Wi-Fi) - *Recommended for now*
This requires your PC to serve the frontend.
1.  **Run Frontend (PC):** `npm run dev -- --host`.
2.  **Browser (Pixel):** Open Chrome and go to `http://<PC_IP>:5173`.
3.  **Install PWA:** Tap "Add to Home Screen" for a fullscreen app-like experience.

### Option B: Standalone APK (Production) - *Convenient but requires building*
You can install a real Android App (.apk) so you don't need the PC server.
1.  **Build:** On your PC (requires Android Studio / Gradle), run:
    ```bash
    npm run android:apk
    ```
    *See [Building the APK](BUILDING_APK.md) for detailed instructions.*
2.  **Install:** Transfer the generated `.apk` to your phone and install it.
3.  **Config:** The app will need to know where the Backend (Operator) is running. Go to Settings in the app and set the **Portal URL** or **Agent Bridge URL**.

## 3. Advanced: Backend on Android (Termux)

*Experimental:* You can run the Python backend *directly* on the phone using Termux. This is difficult because `opencv` is hard to compile on mobile.

1.  **Install Termux:** From F-Droid.
2.  **Install Packages:**
    ```bash
    pkg install python cmake build-essential
    pkg install python-numpy # Pre-compiled numpy helps
    ```
    *Note: `pkg install opencv` usually does not exist. You often need to build it or use a specific repository.*

    **Workaround:** Use a headless "stub" visual cortex if you can't get OpenCV working, or rely on the PC for vision processing initially.

3.  **Clone Repo:**
    ```bash
    git clone https://github.com/Domusgpt/Rongle.git
    cd Rongle
    # Install deps (this may take a long time to compile on phone)
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
