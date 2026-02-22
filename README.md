# Rongle — The Hardware-Isolated Agentic Operator 🦆

[![Status](https://img.shields.io/badge/Status-Alpha-yellow)]()
[![License](https://img.shields.io/badge/License-MIT-green)]()
[![Python](https://img.shields.io/badge/Python-3.12-blue)]()
[![React](https://img.shields.io/badge/React-19-cyan)]()

**Rongle** is an autonomous AI agent designed to bridge the gap between high-level reasoning and physical hardware actuation. Unlike traditional automation, Rongle operates through a **Hardware Air-Gap**, seeing the screen via HDMI capture and interacting via standard USB keyboard/mouse emulation.

> "Undetectable. Immutable. Autonomous."

---

## 🏗️ Core Architecture

Rongle follows a robust, modular design consisting of three primary layers:

1.  **`rng_operator` (The Brain):** An asynchronous Python daemon running on a Raspberry Pi or specialized Android device. It handles the OODA loop: **Observe** (OpenCV/V4L2), **Orient** (CNN/Reflex), **Decide** (Gemini/SmolVLM), and **Act** (USB HID).
2.  **Rongle Frontend (The Dashboard):** A high-performance React PWA providing real-time telemetry, live vision streaming (WebRTC), and agent goal management.
3.  **Hygienic HAL (The Interface):** A Hardware Abstraction Layer that ensures the agent can run on diverse targets, from Raspberry Pi Zero 2 W to native Desktop Simulations.

---

## 🧠 Key Capabilities

*   **Generative Ducky Script:** The agent doesn't follow fixed scripts; it identifies UI elements and generates its own automation code on the fly.
*   **Closed-Loop Visual Servoing:** Precision mouse control that corrects for hand jitter and resolution mismatches in real-time.
*   **Merkle Audit Chain:** Every action is cryptographically hashed and linked, creating an immutable record of agent behavior.
*   **Policy Guardian:** A hardware-enforced safety engine that blocks destructive commands and protects sensitive screen regions.

---

## 🚀 Quick Start

### 1. Prerequisites
- **Hardware:** Raspberry Pi Zero 2 W OR a laptop with a USB-to-HDMI capture card.
- **Python:** 3.12+
- **Node.js:** 20+

### 2. Installation
```bash
# Clone the repo
git clone https://github.com/Domusgpt/Rongle.git
cd Rongle

# Install all dependencies (System, Python, Node)
./scripts/rongle setup
```

### 3. Launch the Operator
```bash
# Run in Dry-Run mode (Simulated screen and HID)
python -m rng_operator.main --dry-run --software-estop

# For real hardware
sudo python -m rng_operator.main
```

### 4. Open the Frontend
```bash
npm run dev
# Visit http://localhost:5173
```

---

## 📚 Documentation
Detailed documentation is available in the **[Documentation Hub](docs/INDEX.md)**.

- **[Architecture Deep Dive](docs/ARCHITECTURE.md)**
- **[Hardware Setup Guide](docs/android/SETUP_GUIDE.md)**
- **[Phased Development Track](docs/PHASED_DEVELOPMENT_TRACK.md)**

---

## 🤝 Contributing
We welcome contributions from humans and AI agents. Please see our **[Contributing Guidelines](CONTRIBUTING.md)** and our **[Security Policy](SECURITY.md)**.

---
*Built with ❤️ for the Air-Gapped Future.*
