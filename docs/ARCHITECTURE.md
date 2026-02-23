# System Architecture

## Overview

Rongle is a **Hardware-Isolated Agentic Operator**. It is designed to control a computer system (the "Target") without installing any software on it. Instead, it acts as a physical user: looking at the screen (HDMI capture) and typing on the keyboard (USB HID injection).

```mermaid
graph TD
    User[User / Operator] -->|Goal: "Open Gmail"| Frontend(Frontend PWA)

    subgraph "Air-Gapped Domain (The Rongle Device)"
        Frontend -->|WebSocket| Operator(rng_operator Daemon)

        Operator -->|Capture| VisualCortex(Visual Cortex)
        Operator -->|Plan| VLM(VLM Reasoner)
        Operator -->|Validate| Guardian(Policy Guardian)
        Operator -->|Log| Ledger(Audit Logger)
        Operator -->|Inject| HID(Hygienic Actuator)
    end

    VisualCortex <-->|HDMI/IP Cam| Target(Target Machine)
    HID -->|USB| Target
```

## Security Model

### 1. The Hardware Air-Gap
The core philosophy is strict isolation. The Target machine treats Rongle as a generic monitor and a standard USB keyboard. It has no knowledge of the AI agent. This prevents malware propagation from the Target to the Agent, and ensures the Agent works on any OS (Windows, Linux, macOS, BIOS).

### 2. The Policy Guardian
Before any keystroke or mouse click is sent to the USB port, it must pass through the `PolicyGuardian`.
*   **Allowlist:** Only approved commands (or regex patterns) are allowed.
*   **Rate Limiting:** Prevents "fuzzing" attacks or rapid-fire inputs.
*   **Blocked Regions:** Prevents clicking on dangerous UI elements (e.g., "Format Drive" buttons), defined by coordinates.

### 3. Immutable Audit Log
Every action is recorded in a Merkle Hash Chain (`AuditLogger`).
*   Entry $H_n = SHA256(Timestamp + Action + H_{n-1})$
*   This ensures that logs cannot be tampered with or deleted without breaking the cryptographic chain.

## Data Flow

### The "OODA Loop" (Observe, Orient, Decide, Act)

1.  **Observe (Look):** `FrameGrabber` captures a raw frame from `/dev/video0` or network stream.
2.  **Orient (Detect):** `ReflexTracker` locates the mouse cursor. `VLMReasoner` (Gemini/Local) analyzes the UI elements.
3.  **Decide (Plan):** The VLM generates a sequence of Ducky Script commands to achieve the user's goal.
4.  **Act (Execute):**
    *   `DuckyScriptParser` converts text to HID reports.
    *   `PolicyGuardian` approves/denies the batch.
    *   `HIDGadget` writes reports to `/dev/hidg*`.
    *   `Humanizer` adds Bezier curve jitter to mouse movements to mimic human behavior (evading bot detection).

## Component Stack

| Component | Technology | Purpose |
| :--- | :--- | :--- |
| **Operator** | Python 3.12 | Core daemon, hardware I/O, state machine. |
| **Vision** | OpenCV, PyTorch, ONNX | Frame capture, object detection, VLM interfacing. |
| **Frontend** | React, Vite, Capacitor | User interface, configuration, live stream view. |
| **Portal** | FastAPI, PostgreSQL | Optional cloud control plane for fleet management. |
| **Hardware** | Raspberry Pi Zero 2 W | Reference platform (supports USB OTG + CSI/HDMI). |
