# Rongle Project Review & Summary

## What is Rongle?

**Rongle** is a hardware-isolated, "agentic" computer operator. It uses AI vision to "see" a computer screen and USB HID (Human Interface Device) injection to "physically" control the keyboard and mouse.

Its core value proposition is **operating any computer through an air gap**, meaning it requires **zero software installation, drivers, or network connectivity** on the target machine. To the target computer, Rongle appears indistinguishable from a standard USB keyboard and mouse being used by a human.

## How It Works

The system is composed of three main parts:
1.  **Operator (The "Hands")**: A Python daemon running on hardware (Raspberry Pi or Android) that manages the camera, runs the agent loop, and sends USB commands.
2.  **Frontend (The "Eyes" & Interface)**: A React-based PWA that provides the user interface, real-time video feed, and currently hosts the lighter-weight vision models (CNNs).
3.  **Portal (The "Brain" / Manager)**: A FastAPI backend for user authentication, device management, and proxying requests to powerful LLMs (like Gemini).

### The Agent Loop
The core operation follows a continuous cycle: **LOOK → DETECT → ACT → VERIFY**

1.  **LOOK**: The system captures a frame of the target screen via a camera (Android) or HDMI capture card (Pi).
2.  **DETECT**:
    *   **VLM Reasoner**: A Vision Language Model (e.g., Google Gemini, SmolVLM) analyzes the screen to understand context and decide the next step towards the user's goal.
    *   **CNN Vision (Local)**: A faster, local TensorFlow.js model attempts to detect specific UI elements (buttons, fields) to reduce latency (currently in early stages).
3.  **ACT**:
    *   The intent is converted into **Ducky Script** (e.g., `MOUSE_MOVE 500 500`, `STRING "Hello"`).
    *   **Policy Engine**: A safety layer checks the command against an "allowlist" to block dangerous actions (e.g., `rm -rf`).
    *   **Hygienic Actuator**: Converts script to USB HID reports, adding "humanizing" noise (jitter, curves) to mouse movements to evade bot detection.
4.  **VERIFY**: The system captures a new frame to confirm the action succeeded (e.g., did the menu open?).

### Key Technologies
*   **Vision**: Google Gemini API, TensorFlow.js (MobileNet-SSD), OpenCV.
*   **Control**: Linux USB Gadget API (`/dev/hidg*`), Web Serial API.
*   **Security**: Merkle Chain Audit Logging, Hardware Dead-man Switch (GPIO).

## Continued Development Roadmap

To move Rongle from its current "MVP" state to a production-ready system, development would likely focus on:

### 1. Vision System Maturity
*   **Train Local CNNs**: The current code notes that local CNN models utilize "random weights". A significant effort is needed to collect UI datasets and train the MobileNet-SSD models so the agent can detect buttons/inputs locally and instantly, reducing reliance on slower/expensive cloud VLMs.
*   **VLM Optimization**: Implementing "Set-of-Mark" prompting more robustly to improve the accuracy of the VLM's spatial understanding (grounding).

### 2. Robustness & Calibration
*   **Auto-Calibration**: The "Self-Calibration" routine (detecting cursor position) needs to be rock-solid across various screen resolutions and aspect ratios.
*   **Error Recovery**: The agent needs better strategies for when it gets "lost" or when an action fails (e.g., clicking a button that didn't respond).

### 3. Hardware & Safety
*   **Production Hardware**: Finalizing the Raspberry Pi "HAT" or custom PCB design for the hardware operator, ensuring the HDMI capture and USB injection are stable.
*   **Enhanced Safety**: Expanding the Policy Engine to support more complex, context-aware rules (e.g., "allow clicking 'Delete' only if inside the 'Trash' folder").

### 4. Fleet Management (Portal)
*   Building out the **Portal** to manage multiple agents simultaneously, view centralized audit logs, and push policy updates to fleets of devices.
