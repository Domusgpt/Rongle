# AI Agent Operation Manual

This document provides instructions for AI agents (and humans) on how to operate, verify, and maintain the Rongle system.

## 1. System Topology

*   **Rongle Operator**: Python daemon running on the edge device (Pi/Android). Handles hardware I/O and local vision.
*   **Portal**: FastAPI backend. Handles auth, policy, and VLM proxying.
*   **Frontend**: React PWA. Provides the user interface and remote control.

## 2. Startup Sequence

### A. Portal (Control Plane)
```bash
# Must start first
export JWT_SECRET="dev_secret"
export GEMINI_API_KEY="your_key"
uvicorn portal.app:app --host 0.0.0.0 --port 8000
```

### B. Frontend (UI)
```bash
# Configure to talk to Portal
export VITE_PORTAL_URL="http://localhost:8000"
npm run dev
```

### C. Operator (Edge Device)
```bash
# Connects to Portal via WebSocket
export GEMINI_API_KEY="your_key" # Or rely on Portal Proxy
python -m rongle_operator.main --goal "Test Goal" --dry-run
```

## 3. Verification Protocols

### A. Build Verification
Run `scripts/verify_build.sh` to check compile integrity and test suites.

### B. Runtime Verification (Dry Run)
1.  Start Portal and Frontend.
2.  Run Operator with `--dry-run`.
3.  Observe "Telemetry" in Frontend Device Manager.
4.  Confirm `AGENT_START` and `HEARTBEAT` events appear.

### C. Hardware Verification
1.  Ensure `/dev/video0` exists (Camera).
2.  Ensure `/dev/hidg0` and `/dev/hidg1` exist (USB Gadgets).
3.  Run `check_environment()` via `main.py`.

## 4. Troubleshooting

| Symptom | Diagnosis | Fix |
|---|---|---|
| **Agent Crash on Boot** | Missing hardware paths. | Check `check_environment` logs. Use `--dry-run` to bypass. |
| **Auth Failure (401)** | Invalid/Expired Device Key. | Regenerate key in Portal UI and update `settings.json`. |
| **Mouse Drifting** | Servoing failed or calibration off. | Re-run calibration step. Check lighting conditions. |
| **Slow Response** | VLM Latency high. | Check `OPERATIONAL_METRICS.md` targets. Switch to faster model. |
