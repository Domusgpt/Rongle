# Architecture & Design

## System Overview

Rongle operates on a **Three-Tier Architecture**, designed to balance local latency requirements with cloud-based reasoning capabilities.

```mermaid
graph TD
    subgraph "Edge Device (Operator)"
        A[Visual Cortex] -->|Frames| B[FastDetector (CNN)]
        C[Hygienic Actuator] -->|USB HID| D[Target Computer]
        E[Agent Server] -->|WebSockets| C
        E -->|State| A
    end

    subgraph "User Interface (Frontend)"
        F[React App] -->|WebRTC/MJPEG| A
        F -->|Commands| E
        F -->|Auth/Config| G[Portal API]
    end

    subgraph "Cloud / Local Server (Portal)"
        G[Portal API] -->|Auth| H[PostgreSQL]
        G -->|Reasoning| I[VLM Service]
        I -->|Plan| F
    end
```

## 1. The Operator (`rng_operator`)
*   **Responsibility:** "Hands and Eyes".
*   **Location:** Runs on the hardware device physically connected to the target.
*   **Key Components:**
    *   `FastDetector`: Uses lightweight ONNX models (MobileNetV3) to identify UI elements (buttons, inputs) in real-time (~30ms latency).
    *   `HygienicActuator`: Translates abstract commands into human-like HID reports (curved mouse paths, jittered typing).
    *   `PolicyEngine`: Enforces safety rules locally to prevent unauthorized actions even if the cloud is compromised.

## 2. The Frontend (`App.tsx`)
*   **Responsibility:** "Consciousness and Control".
*   **Location:** Runs on the user's mobile device or browser.
*   **Key Workflow:**
    1.  **Look:** Receives video feed from Operator.
    2.  **Think:** Sends frame to VLM (Gemini/GPT-4o) via Portal.
    3.  **Plan:** Receives natural language plan, converts to Ducky Script.
    4.  **Act:** Sends signed Ducky Script to Operator.

## 3. The Portal (`portal`)
*   **Responsibility:** "Management and Billing".
*   **Location:** Cloud (AWS/GCP) or On-Prem Server.
*   **Features:**
    *   **Fleet Management:** Track status of all deployed agents.
    *   **Subscription Enforcer:** Limits API usage based on tier (Free/Pro/Enterprise).
    *   **Audit Log:** Immutable record of all actions taken by agents.

## Data Flow: "The Loop"

1.  **Capture:** Operator captures `Frame N`.
2.  **Stream:** `Frame N` sent to Frontend via WebSocket/WebRTC.
3.  **Analysis:** Frontend sends `Frame N` + `Goal` ("Open Terminal") to Cloud VLM.
4.  **Reasoning:** Cloud VLM returns: `{"action": "CLICK", "coords": [100, 200]}`.
5.  **Translation:** Frontend generates Ducky Script: `MOUSE_MOVE 100, 200; MOUSE_CLICK LEFT`.
6.  **Transmission:** Script sent to Operator.
7.  **Validation:** Operator `PolicyEngine` checks script.
8.  **Execution:** Operator executes script on Target.
9.  **Verification:** Cycle repeats to verify outcome.
