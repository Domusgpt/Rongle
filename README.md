<div align="center">
<img width="1200" height="475" alt="Rongle Banner" src="https://github.com/user-attachments/assets/0aa67016-6eaf-458a-adb2-6e31a0763ed6" />

# Rongle: The Sentient KVM

**Visual Reasoning at the Edge. Hardware Execution on the Target.**

[![Build Status](https://img.shields.io/badge/build-passing-brightgreen)](https://github.com/Domusgpt/Rongle/actions)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Documentation](https://img.shields.io/badge/docs-2026_Standard-gold)](docs/)

</div>

Rongle is a hardware-isolated agentic operator. It uses a mobile device (or specialized hardware) to "look" at a screen and physically interact with a computer via USB HID, controlled by advanced VLM (Vision Language Model) reasoning.

## 📚 Documentation Suite

*   **[User Guide](docs/USER_GUIDE.md):** For end-users operating the mobile app.
*   **[Operator Manual](docs/OPERATOR_MANUAL.md):** For hardware hackers setting up the Pi/Jetson.
*   **[Architecture](docs/ARCHITECTURE.md):** Deep dive into the 3-tier design (Frontend/Operator/Portal).
*   **[API Reference](docs/api_reference.md):** WebSocket and REST API specifications.
*   **[System Manifest](docs/manifest.md):** Complete inventory of system components.
*   **[Monetization Strategy](docs/MONETIZATION_STRATEGY.md):** Business model and SaaS features.

## 🚀 Quick Start (Simulation Mode)

Want to try it without hardware?

1.  **Start the Backend (Simulated Operator):**
    ```bash
    # Terminal 1
    export AGENT_TOKEN=dev-token-123
    python3 rng_operator/main.py
    ```

2.  **Start the Frontend:**
    ```bash
    # Terminal 2
    npm install
    npm run dev
    ```

3.  **Connect:**
    *   Open `http://localhost:3000`
    *   Set Bridge URL to `ws://localhost:8000`
    *   Set Auth Token to `dev-token-123`
    *   Type a goal and hit START.

## 🧪 Testing

We adhere to a rigorous testing standard.

*   **Unit Tests:** `npm run test` (Frontend)
*   **Backend Tests:** `npm run test:backend` (Pytest)
*   **E2E Tests:** `npm run test:e2e` (Full stack integration)

## 🛡️ Security

Rongle is designed with **Safety First**.
*   **Hardware Gap:** The agent runs on separate hardware.
*   **Policy Engine:** All commands are filtered through a strict allowlist.
*   **Audit Trail:** Every action is cryptographically logged.

See [SECURITY.md](docs/SECURITY.md) for details.
