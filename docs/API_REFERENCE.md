# API Reference

## `rng_operator` (Python Backend)

### `HygienicActuator`
**Path:** `rng_operator/hygienic_actuator/hid_gadget.py`

Handles raw USB HID report injection.

*   `open() -> None`: Open device file descriptors (`/dev/hidg0`, `/dev/hidg1`).
*   `close() -> None`: Release resources.
*   `execute(command: ParsedCommand) -> None`: Execute a single Ducky Script command.
*   `release_all() -> None`: Send "key up" reports for all keys and mouse buttons.

### `FrameGrabber`
**Path:** `rng_operator/visual_cortex/frame_grabber.py`

Captures video frames from local or network sources.

*   `__init__(device: str | int, ...)`:
    *   `device`: `/dev/videoN` (V4L2) or `http://...` (Network/FFMPEG).
*   `grab() -> CapturedFrame`: Blocking capture of the latest frame.
    *   Returns `CapturedFrame(image: np.ndarray, timestamp: float, sequence: int, sha256: str)`.
*   `start_streaming() -> None`: Begin background capture thread.

### `VLMReasoner`
**Path:** `rng_operator/visual_cortex/vlm_reasoner.py`

High-level logic and planning engine.

*   `find_element(frame: np.ndarray, description: str) -> UIElement | None`:
    *   Identify a single UI element matching the description.
*   `plan_action(frame: np.ndarray, goal: str, history: list[str]) -> str`:
    *   **New in 0.3.0**: Generate a full Ducky Script plan to achieve the goal based on the visual state and action history.
    *   Returns raw Ducky Script string (e.g., `MOUSE_MOVE 100 200\nCLICK LEFT`).

### `AuditLogger`
**Path:** `rng_operator/immutable_ledger/audit_logger.py`

Tamper-evident logging.

*   `log(action: str, screenshot_hash: str, ...) -> AuditEntry`:
    *   Appends a new entry to the Merkle chain.
*   `verify_chain() -> bool`:
    *   Recomputes all hashes from Genesis to Head to ensure integrity. Raises `RuntimeError` if tampering is detected.

---

## `portal` (FastAPI)

### Authentication
*   `POST /auth/register`: Create a new user account.
*   `POST /auth/token`: Login (returns JWT `access_token`).

### Devices
*   `POST /devices/`: Register a new operator device.
*   `GET /devices/`: List user's devices.
*   `POST /devices/{id}/key`: Regenerate API key for a device.

### Telemetry
*   `WS /ws/telemetry/{device_id}`: WebSocket endpoint for real-time status updates from the operator.

---

## `frontend` (React)

### `AgentBridge`
**Path:** `services/bridge.ts`

Manages communication with the operator.

*   `connect(url: string, token: string) -> Promise<void>`: Establish WebSocket connection.
*   `sendCommand(script: string) -> void`: Send Ducky Script to be executed.
*   `disconnect() -> void`: Close connection.

### `gemini.ts`
**Path:** `services/gemini.ts`

Client-side vision logic.

*   `analyzeScreenFrame(base64Image: string, goal: string) -> Promise<VisionAnalysisResult>`:
    *   Sends frame to Gemini (Direct or Proxy) and parses the JSON response into a structured action plan.
