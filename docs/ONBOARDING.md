# Welcome to Rongle! 🦆

Rongle is an advanced **Hardware-Isolated Agentic Operator**. That sounds fancy, but it just means:
> **An AI that sees your screen and types on your keyboard, running on a separate device to stay undetectable and safe.**

This guide will get you from "Zero" to "Agent Controlling PC" in about 5 minutes.

---

## 🚦 Quick Start: Choose Your Path

### Path A: I just want to run the agent.
You have a PC and an Android phone (Pixel 10 recommended). You want to see the AI control your mouse.

1.  **Install Prerequisites:**
    *   [Python 3.12](https://www.python.org/downloads/)
    *   [Node.js 20+](https://nodejs.org/)
    *   [IP Webcam](https://play.google.com/store/apps/details?id=com.pas.webcam) (Android App)

2.  **Run the Wizard:**
    ```bash
    python3 scripts/setup_pixel_test.py
    ```
    *Follow the prompts. This script installs everything and launches the backend.*

3.  **Watch it Go:**
    *   Open the link shown in the terminal on your phone.
    *   Point your phone at your screen.
    *   The agent is now "Thinking" (in dry-run mode).

---

### Path B: I am a Developer.
You want to modify the code, fix bugs, or add features.

1.  **Clone & Install:**
    ```bash
    git clone https://github.com/Domusgpt/Rongle.git
    cd Rongle
    pip install -r rng_operator/requirements.txt
    npm install
    ```

2.  **Use the CLI Tool:**
    We have a unified CLI helper `scripts/rongle`.
    ```bash
    ./scripts/rongle start   # Spin up the full stack (Docker)
    ./scripts/rongle dev     # Run in Dev Mode (Unsafe/No Policy)
    ./scripts/rongle test    # Run all unit tests
    ./scripts/rongle verify  # Check your environment
    ```

3.  **Where is the code?**
    *   `rng_operator/`: The Python Brain. Start at `main.py`.
    *   `frontend/`: The React UI. Start at `src/App.tsx`.
    *   `docs/`: The Library. Read [ARCHITECTURE.md](ARCHITECTURE.md) first.

---

### Path C: I am an AI Agent.
You are an LLM instantiating into this codebase.

1.  **Read This First:** [docs/AGENTS.md](AGENTS.md).
2.  **Understand the Loop:** `rng_operator/main.py` -> `agent_loop`.
3.  **Respect the Safety:** Never bypass `PolicyGuardian`.

---

## 📚 Documentation Index

| Doc | Description |
| :--- | :--- |
| **[SYSTEM_STATUS.md](SYSTEM_STATUS.md)** | What works, what's broken, what's next. |
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | System diagrams and security model. |
| **[API_REFERENCE.md](API_REFERENCE.md)** | Class and method signatures. |
| **[TESTING_PLAN_PIXEL.md](TESTING_PLAN_PIXEL.md)** | Detailed guide for the Pixel/PC setup. |
| **[TIMELINE.md](TIMELINE.md)** | Phased testing schedule. |
| **[android/SETUP_GUIDE.md](android/SETUP_GUIDE.md)** | Android-specific configuration. |

---

## 🛠 Troubleshooting

**"The wizard failed to install dependencies."**
*   Ensure you have Python 3.12 and Node.js v20+.
*   Try running `pip install -r rng_operator/requirements.txt` manually.

**"The camera feed is black."**
*   Check that IP Webcam is running on the phone.
*   Ensure both devices are on the *same Wi-Fi network*.
*   Disable PC firewall temporarily.

**"I want to run it on a Raspberry Pi."**
*   This is the intended production hardware!
*   Flash Raspberry Pi OS Lite.
*   Copy this repo over.
*   Run `sudo python -m rng_operator.main`. (Sudo needed for USB Gadget access).

---

*Happy Hacking!*
