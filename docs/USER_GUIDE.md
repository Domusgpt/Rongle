# User Guide: Rongle Mobile App

**Welcome to the Future of Remote Administration.**

Rongle turns your mobile device into a sentient KVM switch. This guide covers the usage of the mobile application.

## 1. Getting Started

### Installation
1.  Download the `.apk` from the [Releases Page](https://github.com/Domusgpt/Rongle/releases) or the Play Store.
2.  Install on your Android device.

### Connection Modes
*   **Direct Mode (Local):** Connects directly to a Rongle Operator on your WiFi. Fast, secure, no internet required.
*   **Portal Mode (Cloud):** Connects via the Rongle Cloud. Allows remote control from anywhere.

## 2. Interface Overview

### The HUD
*   **Live View:** The center screen shows what the agent sees.
*   **Status Bar:**
    *   `LATENCY`: Network delay (aim for <50ms).
    *   `CONF`: AI Confidence score.
    *   `FPS`: Capture rate.
*   **Goal Input:** Type your intent here (e.g., "Fix the wifi settings").

### Controls
*   **Play/Pause:** Toggles the AI agent loop.
*   **ESTOP (Emergency Stop):** Immediately halts all input. **Hard hardware cut.**
*   **Config (Gear Icon):**
    *   *Human-in-the-loop:* If enabled, the AI asks for permission before clicking.
    *   *Bridge URL:* Set the IP of your Operator (e.g., `ws://192.168.1.50:8000`).
    *   *Auth Token:* Your security key.

## 3. Workflow

1.  **Connect:** Ensure the "Wifi" icon is green.
2.  **Aim:** Point the camera at the screen (if using phone camera) or ensure HDMI capture is working.
3.  **Command:** Type a goal.
4.  **Supervise:** Watch the "Reasoning" box. It explains what the AI is thinking.
    *   *Example:* "I see a login prompt. I will type the username."
5.  **Intervene:** If the AI is wrong, hit Pause or ESTOP.

## 4. Troubleshooting

*   **"Bridge Disconnected":** Check your WiFi. Ensure the Operator device is powered on.
*   **Low Confidence:** Improve lighting on the monitor. Reduce glare.
*   **Lag:** Switch to 5GHz WiFi.
