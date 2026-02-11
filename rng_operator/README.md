# Operator — Hardware-Isolated Agentic Operator

Python daemon that runs on a Raspberry Pi Zero 2 W (or any Linux host with USB OTG). Captures the target computer's screen via HDMI, uses AI to understand the UI, generates humanized mouse/keyboard input, and injects it through USB HID — all validated by a policy engine and recorded in a tamper-evident audit log.

## Module Map

```
operator/
├── main.py                       # Entrypoint: calibrate → agent loop
├── config/
│   ├── settings.py               # Settings dataclass with JSON persistence
│   └── allowlist.json            # Default policy file
├── hygienic_actuator/
│   ├── ducky_parser.py           # Ducky Script → HID report translation
│   ├── humanizer.py              # Bezier-curve mouse path generation
│   ├── hid_gadget.py             # /dev/hidgX USB OTG writer
│   └── emergency_stop.py         # GPIO kill switch
├── visual_cortex/
│   ├── frame_grabber.py          # V4L2 frame capture
│   ├── reflex_tracker.py         # Template/YOLO cursor detection
│   └── vlm_reasoner.py           # Gemini / local VLM interface
├── policy_engine/
│   └── guardian.py               # Allowlist enforcement + rate limiter
├── immutable_ledger/
│   └── audit_logger.py           # Merkle chain audit log
├── portal_client.py              # Async portal HTTP+WS client
└── requirements.txt
```

## Running

```bash
# Install dependencies
pip install -r operator/requirements.txt

# Run with a goal
GEMINI_API_KEY=<key> python -m operator.main --goal "Open Notepad"

# Interactive mode
python -m operator.main

# Development (no real HID output, no GPIO)
python -m operator.main --dry-run --software-estop
```

### CLI Arguments

| Flag | Description |
|------|-------------|
| `--goal TEXT` | Agent goal string. Prompts interactively if omitted. |
| `--config PATH` | Path to settings JSON (default: `operator/config/settings.json`) |
| `--dry-run` | Disable actual HID writes (log only) |
| `--software-estop` | Use software kill switch instead of GPIO |

## Module Reference

### `main.py`

Orchestrates the full lifecycle:

1. **`calibrate(grabber, tracker, hid, audit)`** — Self-calibration procedure. Injects a known cursor delta (50px, 50px), re-captures, verifies the cursor moved by the expected amount (±15px tolerance). Up to 5 attempts.

2. **`agent_loop(goal, ...)`** — Core perception-action loop:
   - LOOK: `grabber.grab()` → `CapturedFrame`
   - DETECT: `tracker.detect()` for cursor + `reasoner.find_element()` for UI target
   - ACT: `parser.parse()` → `guardian.check_command()` → `hid.execute()`
   - VERIFY: Re-capture, check cursor distance from target (<30px = pass)
   - Emergency stop checked every iteration

3. **`main()`** — Entrypoint. Parses args, initializes all modules, runs calibrate + agent loop, handles graceful shutdown via SIGINT/SIGTERM.

### `hygienic_actuator/ducky_parser.py`

**`DuckyScriptParser`** — Translates Ducky Script text into `ParsedCommand` objects.

```python
parser = DuckyScriptParser(screen_w=1920, screen_h=1080)
commands = parser.parse("GUI r\nDELAY 500\nSTRING notepad\nENTER")
```

**Supported commands:**
- `STRING <text>` / `STRINGLN <text>` — Type characters
- `DELAY <ms>` — Wait
- `MOUSE_MOVE <x> <y>` — Move cursor (absolute coords → Bezier path)
- `MOUSE_CLICK [LEFT|RIGHT|MIDDLE]` — Click
- `REPEAT <n>` — Repeat last command
- `REM <comment>` — Ignored
- Modifier combos: `CTRL ALT DELETE`, `GUI r`, `SHIFT TAB`, etc.

**HID Reports:**
- `KeyboardReport` — 8 bytes: `[modifier, reserved, key1..key6]`
- `MouseReport` — 4 bytes: `[buttons, dx, dy, wheel]` (signed 8-bit deltas)

**Scancode Coverage:** Full USB HID Usage Table §10 — lowercase letters, digits, punctuation, shifted characters (`!@#$%^&*()`), function keys (F1–F12), navigation keys, numlock, print screen, all modifier aliases.

### `hygienic_actuator/humanizer.py`

**`Humanizer`** — Generates human-like mouse trajectories.

```python
humanizer = Humanizer(jitter_sigma=1.5, overshoot_ratio=0.25)
path = humanizer.bezier_path(100, 200, 500, 400)
# Returns: [BezierPoint(dx=3, dy=2, dwell_ms=8), ...]
```

**Algorithm:**
1. Compute two control points offset perpendicular to the straight-line path
2. Add Gaussian noise to control points (scale proportional to distance)
3. Evaluate cubic Bezier at `N` steps where `N = min(80, max(15, distance/8))`
4. Apply smoothstep easing: `t² × (3 - 2t)`
5. Add per-point Gaussian jitter (σ=1.5px)
6. Convert absolute positions to relative deltas, clamped to ±127

### `hygienic_actuator/hid_gadget.py`

**`HIDGadget`** — Writes USB HID reports to Linux USB OTG gadget device files.

```python
with HIDGadget(keyboard_dev="/dev/hidg0", mouse_dev="/dev/hidg1") as hid:
    hid.send_string("Hello")
    hid.send_mouse_path(bezier_points)
    hid.send_mouse_click(button=1)  # left click
    hid.release_all()
```

**Prerequisites:** Raspberry Pi with `dwc2` overlay and ConfigFS HID gadget configured.

### `hygienic_actuator/emergency_stop.py`

**`EmergencyStop`** — GPIO-based hardware kill switch.

```python
estop = EmergencyStop(gpio_line=17, on_stop=hid.release_all)
estop.start()        # Begin monitoring
estop.is_stopped     # Check state
estop.trigger()      # Software trigger
estop.reset()        # Resume after stop
estop.stop()         # Clean shutdown
```

**Hardware:** Normally-closed momentary switch between GPIO 17 and GND. Release = HIGH = STOP. 10ms polling interval in background thread.

### `visual_cortex/frame_grabber.py`

**`FrameGrabber`** — V4L2 capture via OpenCV.

```python
grabber = FrameGrabber(device="/dev/video0", width=1920, height=1080, fps=30)
grabber.open()
frame = grabber.grab()  # CapturedFrame(image, timestamp, sequence, sha256)
```

Also supports background streaming: `start_streaming()` → `get_latest()`.

### `visual_cortex/reflex_tracker.py`

**`ReflexTracker`** — Fast cursor detection.

```python
tracker = ReflexTracker(cursor_templates_dir="assets/cursors")
detection = tracker.detect(frame_image)
# CursorDetection(x=450, y=300, confidence=0.92, method="template")
```

Uses multi-scale template matching (0.5x–1.5x). Falls back to YOLO ONNX model if available. Synthesizes a default arrow cursor template if no templates directory exists.

### `visual_cortex/vlm_reasoner.py`

**`VLMReasoner`** — UI understanding via vision-language models.

```python
# Remote (Gemini)
backend = GeminiBackend(api_key="...", model="gemini-2.0-flash")
# Local (HuggingFace)
backend = LocalVLMBackend(model_id="HuggingFaceTB/SmolVLM-256M-Instruct")

reasoner = VLMReasoner(backend=backend)
element = reasoner.find_element(image, "Click the search button")
# UIElement(label="Search", x=450, y=120, width=100, height=35, confidence=0.85)
```

### `policy_engine/guardian.py`

**`PolicyGuardian`** — Command validation against configurable rules.

```python
guardian = PolicyGuardian(allowlist_path="operator/config/allowlist.json")
verdict = guardian.check_command("STRING rm -rf /", cursor_x=500, cursor_y=300)
# PolicyVerdict(allowed=False, reason="Blocked pattern: rm\\s+-rf", rule_name="blocked_keystroke")
```

**Checks performed:**
1. Rate limit (sliding window, 50 cmd/sec)
2. Blocked keystroke patterns (regex)
3. Blocked key combos
4. Mouse click region bounds
5. Mouse speed limit (5000 px/sec)

### `immutable_ledger/audit_logger.py`

**`AuditLogger`** — Tamper-evident Merkle chain.

```python
with AuditLogger("/mnt/secure/audit.jsonl") as audit:
    audit.log("STRING hello", screenshot_hash="abc...")
    audit.log("MOUSE_CLICK LEFT", policy_verdict="allowed")
    audit.verify_chain()  # True or raises RuntimeError
```

**Hash formula:** `SHA256(f"{timestamp:.6f}|{action}|{screenshot_hash}|{previous_hash}")`

Genesis hash: `"0" × 64`. Append-only JSONL with `fsync()`. Resumes from existing file on restart.

### `portal_client.py`

**`PortalClient`** — Async device-to-portal communication.

```python
client = PortalClient(base_url="https://portal.rongle.io", api_key="rng_...")
settings = await client.fetch_settings()
result = await client.vlm_query(prompt="Find search button", image_b64="...")
await client.sync_audit(entries=[...])
await client.heartbeat()
```

Also supports WebSocket telemetry: `connect_telemetry()` → `send_telemetry()` / `receive_command()`.
