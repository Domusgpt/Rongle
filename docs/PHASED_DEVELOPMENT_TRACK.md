# Phased Development Track: The Autonomous Operator
**Date:** 2026-02-10

This document outlines the strategic roadmap for evolving Rongle from a unified prototype into a production-ready autonomous agent.

---

## Phase 1: "The Brain" (Vision & Intelligence Optimization)
**Focus:** Accuracy, Latency, and Local Inference.

### 1.1 CNN Fine-Tuning & Integration
- **Goal:** Move from "random weights" to a production-grade UI element detector.
- **Status:** **In-Progress.** Training harness has been ported to `rng_operator/training/`.
- **2026 Industry Standard Requirements:**
    - **Dataset:** 5,000+ high-resolution screenshots across Windows, Linux, macOS, and Android.
    - **Architecture:** Transition from SSDLite-MobileNetV3 to a modern lightweight backbone (e.g., FastViT or YOLOv11-nano).
    - **Augmentation:** Advanced simulation of HDMI artifacts (compression, chromatic aberration, scanlines).
    - **Quantization:** Mixed-precision training (FP16) and INT8 post-training quantization for edge TPU support.
- **Outcome:** Sub-20ms detection of UI elements with >95% mAP@0.5.

### 1.2 Local VLM Optimization (Quantization)
- **Goal:** Run `SmolVLM` at usable speeds (1-2s inference) on Pi Zero 2 W or Android.
- **Tasks:**
    - Apply 4-bit/8-bit quantization to the model weights.
    - Implement a model-switching logic in `VLMReasoner` based on hardware capability.
- **Outcome:** Privacy-preserving reasoning without cloud dependencies.

### 1.3 OCR Integration
- **Goal:** Extract text locally to enrich the agent's context and reduce token costs.
- **Tasks:**
    - Integrate Tesseract or PaddleOCR into the `VisualCortex`.
    - Map extracted text to bounding boxes for precise "click-on-text" actions.

---

## Phase 2: "The Body" (Reliability & Multi-Platform)
**Focus:** Decoupling, Portability, and Robustness.

### 2.1 Hardware Abstraction Layer (HAL)
- **Goal:** Decouple core logic from specific drivers (OpenCV, Linux Gadget).
- **Status:** **Phase A Complete.** Core interfaces and Pi/Desktop backends implemented in `rng_operator/hal/`.
- **Tasks:**
    - Refine abstract interfaces for `VideoSource` and `HIDActuator`.
    - Implement backends for:
        - **Android:** CameraX + CH9329 Serial.
        - **Legacy:** Maintenance of the original direct driver calls.

### 2.2 Advanced Visual Servoing
- **Goal:** Handle extreme angles and low-quality video feeds.
- **Tasks:**
    - Implement 4-point homography estimation for "perspective correction".
    - Add predictive filtering (Kalman Filter) to the cursor tracker to handle frame drops.

### 2.3 Android Native App
- **Goal:** Remove the dependency on a desktop browser.
- **Tasks:**
    - Bundle the frontend using Capacitor into a production APK.
    - Implement background services to keep the WebRTC stream alive while the phone is locked.

---

## Phase 3: "The Fortress" (Enterprise & Fleet Management)
**Focus:** Security, Supervision, and Scalability.

### 3.1 Portal Command & Control (C2)
- **Goal:** Manage multiple operators from a single dashboard.
- **Tasks:**
    - Complete the `portal/` billing and subscription logic.
    - Implement a "Fleet Dashboard" to view status/logs of 100+ devices.

### 3.2 Audit Replay & Human Supervision
- **Goal:** Visual verification of agent actions for compliance.
- **Tasks:**
    - Build a tool to "replay" the Merkle Chain logs alongside the captured screenshots.
    - Implement "Request Intervention" state where the agent pauses and asks a human for help when confidence is low.

### 3.3 Semantic Safety Engine
- **Goal:** Prevent high-level malicious intent, not just bad keywords.
- **Tasks:**
    - Use the local VLM to "Audit" the generated Ducky Script against a set of high-level safety rules before execution.

---

## Quick Wins (Next 1-2 Weeks)

1.  **Data Collection Sprint:** Build a small tool (or use the existing sandbox) to capture 500 screenshots of diverse UI states. This is the prerequisite for all Phase 1 work.
2.  **HAL Migration (HID):** Decouple the `hid_gadget.py` logic into a standard interface. This will immediately allow the agent to run in "Simulation Mode" on a developer's Mac/Windows laptop using `pyautogui`.
3.  **Frontend Polish:** Update the `ActionLog` to show the Visual Servoing "correction steps" to give users more confidence in the agent's mechanical precision.

## Recommended Next Step:
**Focus on Phase 1.1 (CNN Training).**
The unified architecture is ready, but the "reflexes" are currently simulated. Training the local CNN will provide the biggest performance and accuracy boost for the OODA loop.
