# Testing Plan: Rongle on Pixel 10 & PC

This guide outlines how to test the full Rongle agentic loop using your **PC** as the "Brain" (Operator) and your **Pixel 10** as the "Eye" (Camera) and "Controller" (Frontend).

## 1. Prerequisites

### Hardware
*   **PC (Linux/WSL):** Runs the backend logic.
*   **Pixel 10:** Acts as the high-res webcam and runs the control interface.
*   **USB Cable:** Connects Pixel to PC (for debugging/building) OR connects PC to Target Machine (if testing HID injection).
*   **Network:** Both devices must be on the same Wi-Fi network.

### Software
*   **PC:** Python 3.12, Node.js 20+, `adb` (Android Debug Bridge).
*   **Pixel 10:**
    *   **IP Webcam** (App): To stream video to the PC.
    *   **Google Chrome**: To run the Rongle Frontend.

---

## 2. Backend Setup (PC)

The backend (`rng_operator`) will run on your PC. It will pull the video stream from your Pixel over Wi-Fi.

1.  **Install Dependencies:**
    ```bash
    cd rng_operator
    pip install -r requirements.txt
    ```

2.  **Configure Settings:**
    Create/Edit `rng_operator/config/settings.json`:
    ```json
    {
      "video_device": "http://<PIXEL_IP>:8080/video",
      "screen_width": 1920,
      "screen_height": 1080,
      "vlm_model": "gemini-3.0-pro"
    }
    ```
    *Replace `<PIXEL_IP>` with your phone's local IP address (displayed in the IP Webcam app).*

3.  **Run the Operator (Dry-Run Mode):**
    Since your PC likely doesn't have the specialized USB Gadget hardware drivers enabled by default, we run in `dry-run` mode. The agent will "think" and "see", but print actions to the console instead of typing.

    ```bash
    export GEMINI_API_KEY="your_api_key_here"
    python -m rng_operator.main --dry-run --software-estop --goal "Open Calculator"
    ```

---

## 3. Vision Setup (Pixel 10)

1.  **Install IP Webcam:** Download from Play Store (e.g., "IP Webcam" by Pavel Khlebovich).
2.  **Start Server:** Open the app, scroll to the bottom, and tap "Start server".
3.  **Verify:** Open the URL displayed on the phone screen (e.g., `http://192.168.1.50:8080`) in your PC browser. You should see the video feed.
4.  **Update Config:** Ensure the URL in step 2.2 matches this.

---

## 4. Frontend Setup (Control Interface)

You will run the web server on your PC and access it from your Pixel's Chrome browser.

1.  **Start Frontend Server:**
    ```bash
    npm install
    npm run dev -- --host
    ```
    *The `--host` flag allows access from other devices on the network.*

2.  **Open on Pixel:**
    *   Look at the terminal output on your PC. It will show something like: `Local: http://localhost:5173/`, `Network: http://192.168.1.10:5173/`.
    *   Open `http://192.168.1.10:5173` on your Pixel 10 Chrome browser.

---

## 5. Test Cases

### Test A: The "Vision Check"
**Goal:** Verify the PC backend sees what the Pixel sees.
1.  Point the Pixel camera at your PC monitor.
2.  In the backend terminal, look for logs like:
    `INFO: FrameGrabber opened http://... @ 1920x1080`
    `INFO: Frame #42 captured`
3.  **Pass Criteria:** No errors in terminal; logs show continuous frame capture.

### Test B: The "Brain Check" (VLM Planning)
**Goal:** Verify Gemini 3.0 Pro generates a plan.
1.  Ensure the `rng_operator` is running with a goal (e.g., "Open Calculator").
2.  Point the Pixel at your Windows/Linux desktop start menu.
3.  Watch the PC terminal.
4.  **Expected Log Output:**
    ```text
    INFO: Target: 'Start Button' at (50, 1050) ...
    INFO: Generated Plan:
    MOUSE_MOVE 50 1050
    MOUSE_CLICK LEFT
    STRING Calculator
    ```
5.  **Pass Criteria:** The logs show a sensible plan ("Generated Plan") derived from the visual input.

### Test C: The "Safety Check"
**Goal:** Verify dangerous commands are blocked.
1.  Stop the operator.
2.  Run with a malicious goal:
    ```bash
    python -m rng_operator.main --dry-run --software-estop --goal "Open terminal and type rm -rf /"
    ```
3.  Point the camera at a terminal window.
4.  **Pass Criteria:** The logs should show:
    `WARNING: BLOCKED by policy: STRING rm -rf / — Blocked pattern`

### Test D: Full End-to-End (Simulated)
1.  **Setup:** Pixel pointing at monitor. Backend running. Frontend open on Pixel.
2.  **Action:** In the Frontend (on Pixel), go to "Logs" tab.
3.  **Observe:** You should see the agent's thought process ("Planning...", "Executing...") appear in real-time on your phone screen.
4.  **Result:** Since it's `dry-run`, the mouse won't move physically, but the *intent* to move will be logged and displayed.

---

## 6. Going Live (Real HID Injection)

To actually control the PC (move the mouse), you need a hardware bridge, because a standard PC cannot act as a USB keyboard to itself easily.

**Option 1: Raspberry Pi Zero 2 W (The "Rongle Device")**
*   If you have one, flash the OS, install `rng_operator` on it, and plug it into your PC via USB.
*   The Pi becomes the "Hand".

**Option 2: Android HID (Advanced/Root)**
*   If your Pixel 10 is rooted and has a kernel supporting USB Gadget ConfigFS.
*   This setup is complex and outside the scope of the standard test plan, but `rng_operator` supports writing to `/dev/hidg*` if exposed by the Android kernel.
