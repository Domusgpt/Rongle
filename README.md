# Rongle — The Hardware-Isolated Agentic Operator

[![Status](https://img.shields.io/badge/Status-Alpha-yellow)]()
[![Python](https://img.shields.io/badge/Python-3.12-blue)]()
[![React](https://img.shields.io/badge/React-19-cyan)]()

**Rongle** is an autonomous AI agent that controls computers physically. It sees the screen via HDMI capture and types on the keyboard via USB emulation. Because it runs on separate hardware (e.g., a Raspberry Pi), it is undetectable by software anti-cheat/anti-bot systems and immune to malware on the target machine.

## 📚 Documentation Suite

We maintain professional-grade documentation for both human developers and AI agents.

*   **[System Status](docs/SYSTEM_STATUS.md):** Current health, feature maturity, and known issues.
*   **[Architecture](docs/ARCHITECTURE.md):** High-level design, security model (Air-gap, Policy Engine), and data flow.
*   **[Agent Guide](docs/AGENTS.md):**  **Start here if you are an AI.** Codebase topology, coding standards, and directives.
*   **[API Reference](docs/API_REFERENCE.md):** Detailed class/method documentation for Backend and Frontend.
*   **[Development Plan](DEVELOPMENT_PLAN.md):** Roadmap for "The Ultimate Product" (Android, CNNs, Dynamic Scripting).

---

## 🚀 Quick Start

### Hardware Requirements
*   **Compute:** Raspberry Pi Zero 2 W (or 4/5), or an Android Device (with root/custom kernel for HID).
*   **Vision:** HDMI-to-CSI bridge (TC358743) or IP Webcam app.
*   **Input:** USB OTG cable.

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/Domusgpt/Rongle.git
    cd Rongle
    ```

2.  **Install Backend Dependencies:**
    ```bash
    pip install -r rng_operator/requirements.txt
    ```

3.  **Run the Operator:**
    ```bash
    # Interactive mode (prompts for goal)
    sudo python -m rng_operator.main

    # Dry-run (safe for dev machines without hardware gadgets)
    python -m rng_operator.main --dry-run --software-estop
    ```

4.  **Run the Frontend:**
    ```bash
    npm install
    npm run dev
    ```

## 🧠 Key Features

*   **Generative Ducky Script:** The agent writes its own automation scripts on the fly based on what it sees.
*   **Visual Servoing:** Closed-loop mouse control ensures clicks land exactly where intended, correcting for resolution mismatches.
*   **Safety First:** A rigorous `PolicyGuardian` blocks dangerous commands (`rm -rf`) and enforces "Safe Zones" on the screen.
*   **Android Integration:** Use your phone as the "Eye" (Camera) and "Hand" (USB Gadget).

## 🤝 Contributing

See [Review Snapshot](docs/REVIEW_SNAPSHOT.md) for recent architectural decisions. We welcome PRs!

---

*Built with ❤️ for the Air-Gapped Future.*
