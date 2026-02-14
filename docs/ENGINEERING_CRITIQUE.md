# Engineering Critique & Technical Debt Assessment

**Date:** February 2025
**Reviewer:** Jules (AI Agent)

This document provides a critical analysis of the current Rongle codebase (`rng_operator`, `portal`, `frontend`). It highlights areas of concern, technical debt, and potential failure points.

## 1. Architectural Debt

### 1.1 The "God Loop" in `main.py`
*   **Issue:** The `agent_loop` function in `rng_operator/main.py` is becoming a monolith. It handles VLM perception, path planning, safety checks, HID execution, and audit logging all in one procedural block.
*   **Risk:** High coupling makes it difficult to unit test specific behaviors (e.g., testing "planning" without mocking "execution").
*   **Severity:** **High**

### 1.2 Frontend-Backend Coupling via IP Webcam
*   **Issue:** The system relies heavily on "IP Webcam" (an external Android app) for vision. This introduces latency (HTTP MJPEG stream) and a dependency on a 3rd-party app that might be killed by the OS.
*   **Risk:** Production unreliability. If the Wi-Fi glitches, the "Eye" goes blind, but the "Hand" might still be moving.
*   **Severity:** **Medium** (Acceptable for Alpha, fatal for Production).

### 1.3 Hardcoded Calibration
*   **Issue:** The `calibrate` function assumes a linear, unrotated relationship between mouse deltas and screen pixels.
*   **Risk:** Fails on curved monitors, rotated screens, or systems with mouse acceleration enabled.
*   **Severity:** **Medium**

## 2. Security Risks

### 2.1 Dev Mode "Konami Code"
*   **Issue:** While cool, enabling a "God Mode" override via `stdin` input ("Konami Code") is a security backdoor if the terminal is accessible via SSH or exposed logs.
*   **Risk:** An attacker with shell access can bypass the Policy Guardian.
*   **Severity:** **High** (in deployed environments).

### 2.2 Unencrypted Local Logs
*   **Issue:** Audit logs are stored in plain JSONL at `/mnt/secure/audit.jsonl`.
*   **Risk:** If the physical device is stolen, the logs (containing potentially sensitive screen hashes and actions) are readable.
*   **Severity:** **Medium**

## 3. Performance Bottlenecks

### 3.1 Synchronous VLM Calls
*   **Issue:** `VLMReasoner` makes blocking HTTP calls to Gemini. The entire agent loop freezes while waiting for the API.
*   **Impact:** Cycle time is ~1-2 seconds. Smooth visual servoing requires <100ms.
*   **Severity:** **High**

### 3.2 MJPEG Decoding
*   **Issue:** `FrameGrabber` with `cv2.VideoCapture` on HTTP streams can block indefinitely if the network stalls.
*   **Impact:** Agent hangs.
*   **Severity:** **Medium**

## 4. Code Hygiene

### 4.1 Type Safety
*   **Issue:** Python code is mostly typed, but some areas (especially `kwargs` in VLM backends) are loose.
*   **Risk:** Runtime type errors.

### 4.2 Test Coverage Gaps
*   **Issue:** `rng_operator/visual_cortex` has minimal unit tests because mocking OpenCV/V4L2 is difficult.
*   **Risk:** Regressions in vision logic are hard to catch without physical hardware.
