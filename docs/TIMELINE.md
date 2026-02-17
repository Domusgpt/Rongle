# Testing Timeline: Rongle with Android (Pixel 10)

This document outlines a recommended schedule for validating the Rongle system using your Pixel 10. The goal is to move from safe simulation to full autonomous control in structured phases.

## 📅 Phase 1: Setup & Connection (Day 0 - Today)

**Goal:** Establish communication between the Brain (PC) and the Eye (Pixel 10).

*   [ ] **Install Software:**
    *   PC: Python 3.12, Node.js 20+.
    *   Pixel 10: "IP Webcam" app (Play Store), Google Chrome.
*   [ ] **Network Check:**
    *   Connect both devices to the same Wi-Fi.
    *   Ping Pixel IP from PC.
*   [ ] **Launch System:**
    *   Run `python3 scripts/setup_pixel_test.py`.
    *   Verify you can see the Frontend on your Pixel's Chrome browser.
    *   Verify the backend logs show "Frame captured" from the IP Webcam stream.

**Success Criteria:** You can see the video feed on your PC monitor (mirrored from phone) and the logs are active.

---

## 📅 Phase 2: Vision & Planning (Day 1-2)

**Goal:** Verify the AI can "see" and "think" correctly without risking hardware damage.

*   [ ] **Dry-Run Mode:** Ensure `--dry-run` is enabled (default in setup script).
*   [ ] **The "Start Menu" Test:**
    *   Point Pixel at your PC monitor (Windows Start button or Linux Dock).
    *   Set Goal: "Click the Start button".
    *   Watch Logs: Check if `VLMReasoner` identifies the button correctly and generates `MOUSE_MOVE` coordinates.
*   [ ] **The "Typing" Test:**
    *   Open Notepad/Text Editor on PC.
    *   Set Goal: "Type Hello World".
    *   Watch Logs: Verify `STRING Hello World` command is generated.

**Success Criteria:** The generated plans in the logs match your expectations. The red bounding box (if overlay enabled) aligns with the real-world object.

---

## 📅 Phase 3: Hardware Integration (Day 3-4)

**Goal:** Close the loop with physical action.

*   [ ] **Hardware Bridge:**
    *   *Option A (Recommended):* Connect Raspberry Pi Zero 2 W to PC via USB. Run `rng_operator` on Pi.
    *   *Option B (Advanced):* Root Pixel 10 and enable USB Gadget kernel modules (requires custom kernel knowledge).
*   [ ] **Calibration:**
    *   Run the agent. It will attempt "Self-Calibration" by moving the mouse.
    *   Verify the mouse cursor actually moves on your screen.
*   [ ] **Servo Tuning:**
    *   If the mouse overshoots/undershoots, adjust `scale_x` / `scale_y` or `gain` in `rng_operator/visual_cortex/servoing.py`.

**Success Criteria:** The agent can consistently move the mouse to a target within 10px accuracy.

---

## 📅 Phase 4: Field Testing (Day 5+)

**Goal:** Autonomous execution of complex tasks.

*   [ ] **Task 1:** "Open Browser and navigate to google.com".
*   [ ] **Task 2:** "Open Calculator, calculate 5 * 5".
*   [ ] **Safety Drill:**
    *   While agent is moving, trigger the E-Stop (Ctrl+C on PC or GPIO button on Pi).
    *   Verify immediate halt.

**Success Criteria:** Reliable execution of multi-step tasks with < 10% failure rate.
