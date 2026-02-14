# Codebase Summary

This document serves as a high-level map of the Rongle repository structure.

## Root Directories

*   `rng_operator/`: **The Backend.** The Python daemon that runs on the hardware device.
*   `frontend/`: **The Frontend.** The React/Vite PWA that controls the agent.
*   `portal/`: **The Cloud.** FastAPI backend for user management (optional).
*   `docs/`: **The Library.** Documentation for users, agents, and developers.
*   `scripts/`: **The Toolbox.** Helper scripts for building, testing, and deployment.
*   `android/`: **The Shell.** Native Android wrapper (Capacitor) for the frontend.

## Key Files

### `rng_operator/`
*   `main.py`: The entry point. Manages the "Look-Plan-Act" loop.
*   `config/settings.py`: Configuration loader (JSON/Env).
*   `hygienic_actuator/`: Hardware control (HID, GPIO).
    *   `ducky_parser.py`: Translates text commands to USB reports.
    *   `hid_gadget.py`: Writes to `/dev/hidg*`.
*   `visual_cortex/`: Computer Vision.
    *   `vlm_reasoner.py`: Interface to Gemini/SmolVLM.
    *   `servoing.py`: Closed-loop mouse control logic.
*   `policy_engine/guardian.py`: Safety firewall for commands.
*   `utils/keyboard_listener.py`: Handles stdin hotkeys (Dev Mode).

### `frontend/`
*   `src/App.tsx`: Main UI component.
*   `src/services/gemini.ts`: Client-side logic for "Direct Mode" VLM queries.
*   `src/components/HardwareStatus.tsx`: Telemetry dashboard.

### `docs/`
*   `ONBOARDING.md`: **Start Here.** Quick start guide.
*   `AGENTS.md`: Guide for AI contributors.
*   `SYSTEM_STATUS.md`: Current health and feature matrix.
*   `TESTING_PLAN_PIXEL.md`: Guide for Pixel 10 + PC setup.

### `scripts/`
*   `rongle`: Unified CLI tool (`./scripts/rongle`).
*   `setup_pixel_test.py`: Interactive wizard for new users.
*   `certify_hardware.py`: Validator for deployment targets.
