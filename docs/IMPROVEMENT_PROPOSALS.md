# Improvement Proposals (RFCs)

Based on the [Engineering Critique](ENGINEERING_CRITIQUE.md), the following proposals outline the path forward.

## RFC-001: Async Agent Core
**Problem:** Blocking VLM calls freeze the agent loop.
**Proposal:**
1.  Rewrite `main.py` using `asyncio`.
2.  Run perception (`FrameGrabber`) and reasoning (`VLMReasoner`) in separate tasks.
3.  Use a `Queue` for actions. The `Actuator` task consumes commands from the queue, allowing the `Planner` to think ahead.

## RFC-002: Session Persistence
**Problem:** If the python process crashes, the agent forgets its goal and history.
**Proposal:**
1.  Introduce a `SessionManager` (SQLite or JSON).
2.  Store `current_goal`, `action_history`, and `step_index`.
3.  On startup, check for an active session and resume.

## RFC-003: Native Android Eye
**Problem:** Dependency on 3rd-party IP Webcam app.
**Proposal:**
1.  Build a custom Android Camera service within the Capacitor App.
2.  Stream video via WebRTC (peer-to-peer) directly to the backend, reducing latency and removing the HTTP stream overhead.

## RFC-004: Robust Calibration
**Problem:** Simple 2-point calibration fails on complex displays.
**Proposal:**
1.  Implement "9-point Calibration" (corners + edges + center).
2.  Compute a Homography matrix (perspective transform) instead of simple X/Y scaling.
3.  This allows accurate clicking even if the camera is viewing the screen at an angle.

## RFC-005: Encrypted Audit Logs
**Problem:** Logs are plaintext.
**Proposal:**
1.  Generate a session keypair on startup (or burn a public key into the firmware).
2.  Encrypt each log entry payload with the public key (Hybrid encryption: AES for data, RSA for session key).
3.  Only the holder of the private key (the admin) can read the logs.
