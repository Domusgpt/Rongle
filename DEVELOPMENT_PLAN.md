# Development Plan: The Ultimate Product (Rongle)

Based on the architectural vision "The Digital Heist: Breaking the Air-Gap with Rongle", this document outlines the roadmap for the next phase of development. The goal is to evolve the current `rng_operator` into a fully autonomous, hardware-isolated agent capable of complex UI interactions.

## 1. Hardware Configurations

We will support two distinct hardware configurations as outlined in the vision:

### A. The Android "Quick Job" (MVP)
*   **Purpose:** Fast, low-cost testing and rapid deployment.
*   **Components:**
    *   **Compute:** Laptop or lightweight PC running `rng_operator`.
    *   **Vision:** Android Smartphone (via IP Webcam or USB Camera) acting as the "Eye".
    *   **Action:** Android Smartphone (via Web Serial / USB Gadget app) or a standard microcontroller (Arduino/Pico) acting as the HID proxy.
*   **Implementation Gaps:**
    *   `FrameGrabber` must support network streams (MJPEG/RTSP) from Android IP Webcam apps.
    *   Serial communication bridge for HID commands if not using direct Linux Gadget API.

### B. The Raspberry Pi "Professional Heist" (Production)
*   **Purpose:** Secure, stealthy, and robust operations.
*   **Components:**
    *   **Compute:** Raspberry Pi 4/5 (CM4/CM5).
    *   **Vision:** HDMI-to-CSI capture card (TC358743 or similar) for pixel-perfect, uncompressed video.
    *   **Action:** Linux USB Gadget API (`/dev/hidg0`, `/dev/hidg1`) for native keyboard/mouse emulation.
    *   **Safety:** Physical GPIO "Dead-Man Switch" (E-Stop).
*   **Status:** Core support exists (`hid_gadget.py`, `frame_grabber.py` for V4L2).

---

## 2. Core Module Enhancements

### A. The Fast Reflex CNN ("RongleOne-Detect")
*   **Goal:** Sub-50ms detection of clickable elements (buttons, inputs) to guide the mouse.
*   **Architecture:** MobileNet-SSD (Single Shot MultiBox Detector).
*   **Current Status:** `ReflexTracker` supports loading ONNX models but lacks a training harness.
*   **Action Items:**
    1.  Create `rng_operator/training/`: A directory for training scripts.
    2.  Implement a PyTorch/TensorFlow training loop to fine-tune MobileNet-SSD on UI datasets (e.g., Rico, or custom labeled screens).
    3.  Implement an export pipeline to convert trained weights to ONNX for fast inference in `ReflexTracker`.

### B. Dynamic Ducky Script ("The Infiltration")
*   **Goal:** Convert high-level user intent (e.g., "Open Gmail and compose") into low-level Ducky Script commands on the fly.
*   **Architecture:** VLM (Vision-Language Model) -> Planner -> Ducky Script.
*   **Current Status:** `VLMReasoner` can see; `DuckyScriptParser` can execute. The "Planner" bridge is missing.
*   **Action Items:**
    1.  Develop `AgentController` (the main loop) that queries `VLMReasoner` for the next step.
    2.  Implement a "Generative Ducky Script" module where the LLM outputs script blocks (e.g., `STRING "subject"`, `TAB`, `ENTER`) based on the visual state.
    3.  Integrate `Humanizer` to ensure generated mouse paths are natural (Bezier curves).

### C. The Visual Cortex (Set-of-Mark)
*   **Goal:** Precise referencing of UI elements for the VLM.
*   **Action Items:**
    1.  Implement "Set-of-Mark" (SoM) prompting in `VLMReasoner`:
        *   Overlay numeric tags on detected elements (from CNN or DOM tree if available).
        *   Pass the tagged image to the VLM so it can say "Click element #5" instead of "Click the blue button".

---

## 3. Security & Governance

### A. Immutable Merkle Audit Chain
*   **Goal:** Tamper-evident logging where every action is cryptographically linked to the previous one.
*   **Status:** `AuditLogger` is implemented with SHA-256 chaining (`previous_hash`).
*   **Action Items:**
    *   Verify integration: Ensure `AgentController` logs *every* step (Look, Detect, Act) to the `AuditLogger`.
    *   Add "Policy Verdict" logging to record *why* an action was allowed or blocked.

### B. The Policy Guardian
*   **Goal:** Hardware-enforced safety limits.
*   **Status:** `emergency_stop.py` exists.
*   **Action Items:**
    *   Implement `PolicyEngine` to block destructive keystrokes (e.g., `rm -rf`, `format`).
    *   Define "Safe Zones" for mouse clicks (e.g., prevent clicking outside a specific window).

---

## 4. Implementation Roadmap

### Phase 1: Vision Expansion
1.  **Android Camera Support:** Update `FrameGrabber` to handle `http://.../video` streams.
2.  **CNN Training Harness:** Create `rng_operator/training/` and add scripts for MobileNet-SSD training and ONNX export.

### Phase 2: Intelligence & Control
3.  **Agent Controller:** Implement the `Look -> Detect -> Plan -> Act -> Verify` loop in `main.py` or `agent.py`.
4.  **Generative Scripting:** Connect VLM outputs to `DuckyScriptParser`.

### Phase 3: Hardening
5.  **Policy Enforcement:** Integrate `PolicyEngine` into the `Act` phase.
6.  **Full System Test:** Validate the entire chain with the "Android Quick Job" rig.
