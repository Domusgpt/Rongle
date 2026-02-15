<div align="center">
  <pre>
    ____   ___  _   _  ____ _     _____
   |  _ \ / _ \| \ | |/ ___| |   | ____|
   | |_) | | | |  \| | |  _| |   |  _|
   |  _ <| |_| | |\  | |_| | |___| |___
   |_| \_\\___/|_| \_|\____|_____|_____|
   HARDWARE-ISOLATED AGENTIC OPERATOR
  </pre>

  <h3>The Hands and Eyes of the Air-Gapped Intelligence</h3>

  [![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
  [![Status](https://img.shields.io/badge/Status-Golden%20Master-gold.svg)](SUMMARY.md)
  [![Docs](https://img.shields.io/badge/Docs-Complete-green.svg)](docs/INDEX.md)
  [![Build](https://img.shields.io/badge/Build-Passing-brightgreen.svg)](scripts/verify_build.sh)

  [Start Here](#quick-start) • [Architecture](#how-it-works) • [For Developers](#developer-nexus) • [For AI Agents](#ai-agent-protocol)
</div>

---

# Welcome to Rongle

Rongle gives AI models physical agency. It is a hardware/software stack that allows an AI to **see** a computer screen (via HDMI/Camera) and **control** it (via USB Keyboard/Mouse), completely air-gapped from the target machine. No software installation required on the target.

## 🚀 Quick Start

**1. Hardware Setup:**
   - Plug Rongle Device (Pi/Android) into Target PC USB port.
   - Point Camera at Target Screen.

**2. Launch Stack (Docker):**
   ```bash
   ./scripts/rongle start
   ```

**3. Verify Operation:**
   ```bash
   ./scripts/rongle verify
   ```

**4. Access Dashboard:**
   - Open `http://localhost:5173` to see what Rongle sees.

---

## 🗺️ Choose Your Path

### 👩‍💻 I am a User / Operator
*   **[System Status](docs/SYSTEM_STATUS.md)**: Check health of current build.
*   **[Hardware Certification](scripts/certify_hardware.py)**: Validate your device compatibility.
*   **[Operational Metrics](docs/OPERATIONAL_METRICS.md)**: Performance benchmarks and latency targets.

### 🛠️ I am a Developer
*   **[Architecture Overview](docs/ARCHITECTURE.md)**: High-level system design.
*   **[API Reference](docs/API_REFERENCE.md)**: Portal and Operator API docs.
*   **[Contributing Guide](CONTRIBUTING.md)**: Code standards and workflow.
*   **[Training Pipeline](docs/TRAINING.md)**: How to train the local vision models.
*   **[Evolutionary Sandbox](rongle_operator/sandbox/README.md)**: Test agent logic in a virtual environment.

### 🤖 I am an AI Agent
*   **[Operation Manual (AGENTS.md)](docs/AGENTS.md)**: **READ THIS FIRST**. Protocol for autonomous coding and operation.
*   **[Timeline & Roadmap](docs/TIMELINE.md)**: Project history and future milestones.
*   **[Improvement Proposals](docs/IMPROVEMENT_PROPOSALS.md)**: RFCs for system evolution.

---

## 🧠 How It Works

The core loop follows a **Perception-Action Cycle**:

1.  **LOOK**: Capture frame via Camera/HDMI (`FrameGrabber`).
2.  **DETECT**: Analyze frame using VLM (Gemini) or Local CNN (`FastDetector`).
3.  **PLAN**: Generate **Ducky Script** intent (`VLMReasoner`).
4.  **ACT**: Execute keystrokes/mouse via USB Gadget (`HygienicActuator`).
5.  **VERIFY**: Confirm action success via visual feedback (`ReflexTracker`).

> **Security Note**: All actions are validated by a **Policy Engine** (`PolicyGuardian`) before execution.

---

## 📂 Repository Structure

*   `rongle_operator/` - **The Brains**: Python daemon for hardware control and vision.
*   `portal/` - **The Gateway**: FastAPI backend for auth and fleet management.
*   `training/` - **The Gym**: Tools to train local vision models.
*   `terraform/` - **The Cloud**: AWS deployment configuration.
*   `scripts/` - **The Toolbelt**: CLI utilities for lifecycle management.
*   `docs/` - **The Knowledge Base**: Comprehensive documentation.

---

<div align="center">
  <sub>Built with ❤️ by the Rongle Team. Operating the Unoperatable.</sub>
</div>
