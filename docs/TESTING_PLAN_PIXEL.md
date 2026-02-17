# Testing Plan: Rongle on Pixel 10 & PC

This guide outlines how to test the full Rongle agentic loop using your **PC** as the "Brain" (Operator) and your **Pixel 10** as the "Eye" (Camera) and "Controller" (Frontend).

## 1. Quick Start (Automated)

We provide a setup script that automates dependency installation, configuration generation, and process launching.

1.  **On Pixel 10:**
    *   Install "IP Webcam" app.
    *   Open app -> "Start server".
    *   Note the IP address (e.g., `192.168.1.50`).

2.  **On PC:**
    ```bash
    python3 scripts/setup_pixel_test.py
    ```
    *   Follow the prompts to enter the Phone IP and your Gemini API Key.
    *   The script will install dependencies and launch both the Backend (Operator) and Frontend.

3.  **Connect:**
    *   The script output will show a network URL (e.g., `http://192.168.1.10:5173`).
    *   Open this URL on your Pixel 10 Chrome browser.

---

## 2. Manual Setup (Reference)

If the automated script fails or you need manual control:

### Backend Setup (PC)
1.  **Install:** `pip install -r rng_operator/requirements.txt`
2.  **Config:** Edit `rng_operator/config/settings.json`:
    ```json
    {
      "video_device": "http://<PHONE_IP>:8080/video",
      "vlm_model": "gemini-3.0-pro"
    }
    ```
3.  **Run:** `python -m rng_operator.main --dry-run --software-estop`

### Frontend Setup (PC)
1.  **Install:** `npm install`
2.  **Run:** `npm run dev -- --host`

---

## 3. Test Cases

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
1.  Run with a malicious goal: `python -m rng_operator.main --dry-run --software-estop --goal "rm -rf /"`
2.  **Pass Criteria:** Logs show `WARNING: BLOCKED by policy: STRING rm -rf /`.

---

## 4. Safety Architecture

When running on your personal PC, safety is paramount.

1.  **Dry-Run Mode:** The `--dry-run` flag in the setup script disables all physical HID injection. The agent *cannot* type or click on your PC; it only logs what it *would* do.
2.  **Software E-Stop:** The `--software-estop` flag enables a "virtual" kill switch since your PC lacks the GPIO pins of a Raspberry Pi. Pressing `Ctrl+C` in the terminal immediately halts the agent loop.
3.  **Policy Guardian:** Even if HID injection were enabled, the regex allowlist prevents destructive commands like formatting drives.

## 5. Going Live (Real HID Injection)

To actually control the PC, you need a hardware bridge.
*   **Raspberry Pi Zero 2 W:** Connect via USB to PC. Run `rng_operator` on the Pi.
*   **Android Root:** Advanced users can use the Pixel 10 itself as the HID device if the kernel supports USB Gadget ConfigFS.
