# Product Roadmap

## Q1 2025: Foundation & Alpha (Current)
*   [x] **Hardware Isolation:** Operator runs on separate device (Pi/Android).
*   [x] **Vision:** V4L2 and Network Stream support.
*   [x] **Reasoning:** Gemini 3.0 Pro integration ("Generative Ducky Script").
*   [x] **Action:** Humanized HID injection via USB Gadget.
*   [x] **Safety:** Policy Guardian with blocked regions and regex filters.
*   [x] **Dev Experience:** Unified CLI, Docker support, and Dev Mode.

## Q2 2025: The "Tactile" Update (Beta)
*   [ ] **Visual Servoing:** Closed-loop mouse control (Move -> Look -> Correct) to handle resolution mismatches perfectly. (Partially implemented)
*   [ ] **OCR Integration:** Local text extraction (Tesseract/PaddleOCR) to reduce VLM token costs/latency.
*   [ ] **Android Native App:** Full React Native / Capacitor shell for the frontend, removing the need for a PC browser.
*   [ ] **Semantic Safety:** Local VLM (SmolVLM) checking command *intent* ("Is this command malicious?"), not just regex.

## Q3 2025: Enterprise Scale (v1.0)
*   [ ] **Fleet Management:** Portal dashboard to manage 100+ operators.
*   [ ] **Role-Based Access Control (RBAC):** Granular permissions for human supervisors.
*   [ ] **Audit Replay:** Visual playback of audit logs ("Black Box Recorder").
*   [ ] **Custom Training:** UI for fine-tuning the local CNN on proprietary applications.

## Future Horizons
*   **Voice Control:** "Hey Rongle, fix the printer driver."
*   **Multi-Agent Swarms:** Coordinated attacks/repairs on multiple machines.
*   **Hardware Certification Program:** Partner with hardware vendors for "Rongle Ready" devices.
