# Rongle Project Review & Summary

## What is Rongle?

**Rongle** is a hardware-isolated, "agentic" computer operator. It uses AI vision to "see" a computer screen and USB HID (Human Interface Device) injection to "physically" control the keyboard and mouse.

Its core value proposition is **operating any computer through an air gap**, meaning it requires **zero software installation, drivers, or network connectivity** on the target machine. To the target computer, Rongle appears indistinguishable from a standard USB keyboard and mouse being used by a human.

## How It Works

The system is composed of three main parts:
1.  **Operator (The "Hands")**: A Python daemon (`rongle_operator`) running on hardware (Raspberry Pi or Android) that manages the camera, runs the agent loop, and sends USB commands.
2.  **Frontend (The "Eyes" & Interface)**: A React-based PWA that provides the user interface, real-time video feed, and currently hosts the lighter-weight vision models (CNNs).
3.  **Portal (The "Brain" / Manager)**: A FastAPI backend for user authentication, device management, and proxying requests to powerful LLMs (like Gemini).

### The Agent Loop
The core operation follows a continuous cycle: **LOOK → DETECT → ACT → VERIFY**

1.  **LOOK**: The system captures a frame of the target screen via a camera (Android) or HDMI capture card (Pi).
2.  **DETECT**:
    *   **VLM Reasoner**: A Vision Language Model (e.g., Google Gemini, SmolVLM) analyzes the screen to understand context and decide the next step towards the user's goal.
    *   **CNN Vision (Local)**: A faster, local TensorFlow.js model attempts to detect specific UI elements (buttons, fields) to reduce latency.
3.  **ACT**:
    *   The intent is converted into **Ducky Script**.
    *   **Policy Engine**: A safety layer (`guardian.py`) checks the command against an allowlist, time windows, and blocked sequences. It can also perform a semantic safety check using a local VLM.
    *   **Hygienic Actuator**: Converts script to USB HID reports. It uses **Visual Servoing** to actively guide the mouse to the target using real-time feedback, ensuring accuracy even without knowledge of host mouse acceleration.
4.  **VERIFY**: The system captures a new frame to confirm the action succeeded (e.g., `ASSERT_VISIBLE` commands).

### Key Technologies
*   **Vision**: Google Gemini API, TensorFlow.js (MobileNet-SSD), OpenCV.
*   **Control**: Linux USB Gadget API (`/dev/hidg*`), Web Serial API.
*   **Security**: Merkle Chain Audit Logging (`SHA256(timestamp||action||screenshot||prev)`), Hardware Dead-man Switch (GPIO).
*   **Infrastructure**: PostgreSQL (persistence), Redis (rate limiting).

## Implemented Roadmap

The following strategic optimizations have been implemented to move Rongle from MVP to Enterprise Scale:

### 1. Architectural Evolution
*   **Renaming**: The backend package has been renamed to `rongle_operator` to avoid standard library conflicts.
*   **Persistence**: The Portal now supports PostgreSQL via `DATABASE_URL` and Redis-based rate limiting via `REDIS_URL`.

### 2. Security Hardening
*   **Advanced Policy**: The Policy Engine now supports `TimeWindowRule`, `SequenceRule`, and `semantic_safety_check` to prevent unauthorized or dangerous actions.
*   **Strict Audit**: The Audit Logger strictly adheres to the Merkle Hash Chain specification for tamper-evidence.
*   **Portal Proxy**: Direct API key access in the frontend is deprecated. All traffic is routed through the Portal for centralized authentication and billing.

### 3. Actuation Refinement
*   **Visual Servoing**: A closed-loop control system (`servoing.py`) now guides mouse clicks to their targets, correcting for drift or acceleration issues in real-time.
*   **Reactive Ducky Script**: Added `WAIT_FOR_IMAGE` and `ASSERT_VISIBLE` commands to enable robust, conditional automation scripts.

### 4. Vision & Training
*   **Data Collection**: A `training/data_collector.py` utility is available to harvest annotated frames for training local CNN models, reducing reliance on cloud VLMs.

### 5. Testing & Quality Assurance
*   **Frontend**: Integrated `vitest` and `@testing-library/react` for component and service testing.
*   **Backend**: Added `pytest` suite for the `rongle_operator` to verify actuator and parser logic.
*   **Integration**: The `android/hardware_bridge.py` serves as an integration test harness for non-Linux hardware.

### 6. Architectural Decisions (Addressing Review Feedback)
*   **Communication Bridge**: Previous reviews suggested a direct Frontend<->Backend bridge (Bluetooth/WS). We explicitly chose a **Portal-Mediated Architecture** (Frontend -> Portal -> Operator) to ensure:
    *   **Auditability**: No commands bypass the central audit log.
    *   **Security**: Devices do not expose open ports on local networks; they dial out to the Portal via secure WebSocket.
    *   **Scalability**: Allows fleet management without complex P2P mesh networking.

## What's Next? (Gap Analysis)

To fully mature the system, the following are needed:
1.  **CI/CD Pipeline**: GitHub Actions workflows to run the `npm test` and `pytest` suites on every commit.
2.  **End-to-End Tests**: A Playwright suite that simulates the entire loop—Frontend UI -> Portal -> Mock Operator -> Virtual Screen—to verify the full chain.
3.  **Model Training**: Actual execution of the `training/train.py` script on a GPU cluster to produce the `mobilenet_ssd.onnx` model required for true local Foveated Rendering.
