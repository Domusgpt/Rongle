<div align="center">

# Rongle

**Hardware-Isolated Agentic Operator**

AI vision + HID injection from Android, Raspberry Pi, or any browser.

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](#license)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61dafb.svg)](https://react.dev)
[![TensorFlow.js](https://img.shields.io/badge/TF.js-4.22-orange.svg)](https://js.tensorflow.org)

</div>

---

## What Is Rongle?

Rongle is an **agentic computer operator** that physically controls any computer through USB HID injection, guided by AI vision. It sees the screen, understands UI elements, generates keyboard/mouse input, and verifies results — all through a hardware-isolated air gap.

**Two form factors, one codebase:**

| | Android (MVP) | Raspberry Pi (Production) |
|---|---|---|
| **Vision** | Phone camera aimed at monitor | HDMI-to-CSI capture card |
| **HID Output** | CH9329 USB dongle via Web Serial | USB OTG (`/dev/hidg0`, `/dev/hidg1`) |
| **VLM** | Gemini API (direct or portal proxy) | Gemini API or local SmolVLM |
| **CNN** | TF.js in-browser (WebGL) | ONNX / OpenCV on-device |
| **Safety** | Software kill switch | GPIO hardware dead-man switch |

The Android path lets anyone test with a phone and a $5 USB dongle. The Pi path is for production deployments with HDMI capture and hardware safety interlocks.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         RONGLE SYSTEM                                │
│                                                                      │
│  ┌────────────────┐    ┌────────────────┐    ┌────────────────────┐  │
│  │   FRONTEND     │    │    PORTAL       │    │     OPERATOR       │  │
│  │   (React PWA)  │◄──►│   (FastAPI)     │◄──►│   (Python daemon)  │  │
│  │                │    │                 │    │                    │  │
│  │  • LiveView    │    │  • JWT Auth     │    │  • Frame Grabber   │  │
│  │  • CNN Engine  │    │  • Device Mgmt  │    │  • VLM Reasoner    │  │
│  │  • SoM Annot.  │    │  • LLM Proxy    │    │  • Ducky Parser    │  │
│  │  • HID Bridge  │    │  • Billing      │    │  • HID Gadget      │  │
│  │  • Auth Gate   │    │  • Audit Verify │    │  • Policy Engine   │  │
│  │                │    │  • WebSocket    │    │  • Audit Logger    │  │
│  └────────┬───────┘    └────────────────┘    │  • Emergency Stop  │  │
│           │                                   └─────────┬──────────┘  │
│           │  Web Serial / WebSocket / Clipboard          │ /dev/hidgX │
│           ▼                                              ▼            │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                     TARGET COMPUTER (HOST)                      │  │
│  │        Receives USB HID input — no drivers, no software         │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### Agent Loop (LOOK → DETECT → ACT → VERIFY)

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│   LOOK   │────►│  DETECT  │────►│   ACT    │────►│  VERIFY  │
│ capture  │     │ CNN+VLM  │     │ policy → │     │ confirm  │
│  frame   │     │ find UI  │     │ HID exec │     │  result  │
└──────────┘     └──────────┘     └──────────┘     └────┬─────┘
     ▲                                                   │
     └───────────────────────────────────────────────────┘
                    loop until goal achieved
```

1. **LOOK** — Capture frame (phone camera or HDMI)
2. **DETECT** — CNN identifies UI elements locally (~20ms), VLM reasons about next action (~2s)
3. **ACT** — Generate Ducky Script → policy gate → humanized HID injection
4. **VERIFY** — Re-capture frame, check cursor position and screen change

---

## Project Structure

```
Rongle/
├── rongle_operator/               # Python — Pi hardware daemon
│   ├── main.py                    # Orchestrator: calibrate + agent loop
│   ├── config/
│   │   ├── settings.py            # Dataclass configuration (JSON load/save)
│   │   └── allowlist.json         # Default policy (blocked patterns, regions)
│   ├── hygienic_actuator/
│   │   ├── ducky_parser.py        # Ducky Script → USB HID reports
│   │   ├── humanizer.py           # Bezier-curve mouse paths with jitter
│   │   ├── hid_gadget.py          # /dev/hidgX USB OTG writer
│   │   └── emergency_stop.py      # GPIO dead-man switch
│   ├── visual_cortex/
│   │   ├── frame_grabber.py       # V4L2 / OpenCV frame capture
│   │   ├── reflex_tracker.py      # Template + YOLO cursor tracking
│   │   └── vlm_reasoner.py        # Gemini + local HuggingFace VLM
│   ├── policy_engine/
│   │   └── guardian.py            # Allowlist + rate limit enforcement
│   ├── immutable_ledger/
│   │   └── audit_logger.py        # SHA-256 Merkle chain audit log
│   ├── portal_client.py           # Async HTTP+WS client for portal
│   └── requirements.txt
│
├── portal/                        # Python — FastAPI management API
│   ├── app.py                     # App factory, middleware, routers
│   ├── config.py                  # Environment-based settings
│   ├── database.py                # SQLAlchemy 2.0 async (SQLite/Postgres)
│   ├── models.py                  # User, Device, Subscription, Audit ORM
│   ├── schemas.py                 # Pydantic validation + tier definitions
│   ├── auth.py                    # JWT + bcrypt utilities
│   ├── dependencies.py            # Auth extraction (Bearer + API key)
│   ├── routers/
│   │   ├── auth.py                # POST /auth/{register,login,refresh}
│   │   ├── users.py               # GET/PATCH /users/me
│   │   ├── devices.py             # CRUD /devices/ + heartbeat
│   │   ├── policies.py            # GET/PUT/PATCH /devices/{id}/policy
│   │   ├── llm_proxy.py           # POST /llm/query (metered VLM proxy)
│   │   ├── subscriptions.py       # GET/PUT /subscription/ + usage
│   │   ├── audit.py               # GET /audit + verify + sync
│   │   └── ws.py                  # WS /ws/device/ + /ws/watch/
│   ├── services/
│   │   └── llm_service.py         # Gemini proxy + quota enforcement
│   ├── middleware/
│   │   └── security.py            # Rate limiting + request logging
│   └── requirements.txt
│
├── services/                      # TypeScript — Frontend services
│   ├── gemini.ts                  # Direct Gemini API (structured JSON)
│   ├── portal-api.ts              # Portal HTTP client (JWT auth)
│   ├── canvas-annotator.ts        # Set-of-Mark annotation engine
│   ├── hid-bridge.ts              # Multi-transport HID bridge
│   └── cnn/                       # Built-in CNN vision system
│       ├── types.ts               # Detection, Classification, FrameDiff
│       ├── engine.ts              # TF.js backend + IndexedDB cache
│       ├── architecture.ts        # MobileNet-SSD + classifier models
│       ├── preprocessor.ts        # Canvas → tensor conversion
│       ├── postprocessor.ts       # NMS, anchor decoding, softmax
│       ├── ui-detector.ts         # UI element detection pipeline
│       ├── screen-classifier.ts   # Screen type classification
│       ├── frame-differ.ts        # SSIM, perceptual hash, edge density
│       └── index.ts               # RongleCNN unified API
│
├── components/                    # React components
│   ├── LiveView.tsx               # Camera feed + analysis overlay
│   ├── CNNOverlay.tsx             # Real-time detection box rendering
│   ├── AnnotationCanvas.tsx       # Tap-to-mark annotation UI
│   ├── HardwareStatus.tsx         # Status grid (camera, HID, portal)
│   ├── ActionLog.tsx              # Terminal-style log viewer
│   ├── AuthGate.tsx               # Login / register flow
│   └── DeviceManager.tsx          # Device CRUD + subscription panel
│
├── App.tsx                        # Main app: state machine, agent loop
├── index.tsx                      # React root mount
├── types.ts                       # Shared TypeScript types
├── index.html                     # PWA shell + importmap + Tailwind
├── manifest.json                  # PWA manifest (installable on Android)
├── vite.config.ts                 # Vite build config
├── tsconfig.json                  # TypeScript compiler options
└── package.json                   # Node.js dependencies
```

---

## Quick Start

### Android (Browser — Fastest Path)

```bash
# 1. Clone and install
git clone https://github.com/Domusgpt/Rongle.git
cd Rongle
npm install

# 2. Set your Gemini API key
echo "GEMINI_API_KEY=your_key_here" > .env.local

# 3. Start dev server
npm run dev
# Opens at http://localhost:3000

# 4. Open on your Android phone (same network)
#    → Allow camera access
#    → Point camera at target monitor
#    → Enter a goal like "Open the terminal and type hello"
#    → Press START
```

**For HID output (optional):**
- Connect a CH9329 USB-to-UART dongle to the target computer
- Pair with phone via USB OTG cable
- Click "USB Serial" in the HID Connection bar
- The Web Serial API will prompt for the device

### Raspberry Pi (Hardware Operator)

```bash
# 1. Set up USB OTG gadget (Pi Zero 2 W)
sudo dtoverlay dwc2
# Configure ConfigFS HID gadget (keyboard + mouse)
# See docs/SETUP.md for detailed instructions

# 2. Install Python dependencies
pip install -r rongle_operator/requirements.txt

# 3. Connect HDMI capture card to target monitor

# 4. Run
export GEMINI_API_KEY=your_key_here
python -m rongle_operator.main --goal "Open Notepad and type Hello World"

# Or interactive mode:
python -m rongle_operator.main
```

### Portal (Management API)

```bash
# 1. Install dependencies
cd portal
pip install -r requirements.txt

# 2. Configure
export JWT_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")
export GEMINI_API_KEY=your_key_here

# 3. Run
uvicorn portal.app:app --host 0.0.0.0 --port 8000

# API docs at http://localhost:8000/docs
```

---

## Core Modules

### Hygienic Actuator

Translates high-level commands into physical USB HID input.

- **Ducky Script Parser** — Full USB HID Usage Table scancode map. Parses `STRING`, `STRINGLN`, `DELAY`, `MOUSE_MOVE`, `MOUSE_CLICK`, `REPEAT`, modifier combos (`CTRL ALT DELETE`, `GUI r`). Outputs 8-byte keyboard reports and 4-byte mouse reports.

- **Humanizer** — Cubic Bezier curves with two randomized control points offset perpendicular to the straight-line path. Gaussian jitter (σ=1.5px), smoothstep easing `t²(3-2t)`, adaptive step count `min(80, max(15, distance/8))`. Mouse deltas clamped to signed 8-bit (±127).

- **HID Gadget** — Writes directly to `/dev/hidg0` (keyboard) and `/dev/hidg1` (mouse) via `os.open(O_WRONLY)`. Supports dry-run mode for development. Auto-release on shutdown.

- **Emergency Stop** — GPIO pin 17 (configurable) via `gpiod`. Normally-closed dead-man switch: release button → GPIO HIGH → all HID output halts. 10ms polling thread. Software-only fallback for development.

### Visual Cortex

Captures and interprets the target computer's screen.

- **Frame Grabber** — V4L2 via OpenCV. Returns `CapturedFrame(image, timestamp, sequence, sha256)`. Single-shot or background streaming modes.

- **Reflex Tracker** — Multi-scale template matching (0.5x–1.5x) for cursor detection. YOLO ONNX fallback. Synthesizes default arrow cursor template when no assets available.

- **VLM Reasoner** — Dual backend: Gemini API (remote) or HuggingFace Transformers (local SmolVLM/PaliGemma). Returns `UIElement(label, x, y, width, height, confidence)`. Structured JSON response parsing.

### CNN Vision System (Browser)

Built-in TensorFlow.js CNN pipeline for fast local inference without API calls.

- **RongleNet-Detect** — MobileNet-SSD architecture with depthwise separable convolutions. 4 feature map scales (80×80, 40×40, 20×20, 10×10), 3 anchors per cell, 17 UI element classes. 25,500 anchor boxes → NMS → up to 50 detections. Target: <30ms on mobile WebGL.

- **RongleNet-Classify** — Lightweight MobileNet classifier. 11 screen type classes: desktop, browser, terminal, file_manager, settings, dialog, login, editor, spreadsheet, media, unknown.

- **Frame Differ** — No CNN required. Pure canvas-based SSIM (8×8 block windows), absolute pixel difference, connected-component region extraction, Sobel edge density, perceptual hashing (pHash) with Hamming distance. Works immediately without training.

### Policy Engine

Every command passes through the policy gate before execution.

- **Allowlist filtering** — Configurable regions (screen areas where clicks are allowed), regex pattern blocking (`rm -rf`, `curl.*|.*sh`, `dd if=`, `mkfs`, `chmod 777`, etc.), blocked key combos (`CTRL ALT DELETE`).

- **Rate limiting** — Sliding window: 50 commands/sec max, 5000 px/sec max mouse speed.

### Immutable Ledger

Tamper-evident audit trail using a Merkle hash chain.

```
hash_N = SHA256( timestamp || action || screenshot_hash || hash_{N-1} )
```

- Genesis hash: `"0" × 64`
- Append-only JSONL with `fsync()` after every write
- Full chain verification: replay from genesis, check every link
- Resume on restart by replaying existing entries

### Portal API

FastAPI management backend with subscription billing.

| Tier | Monthly Quota | Devices | Price |
|------|---------------|---------|-------|
| Free | 100 VLM calls | 1 | $0 |
| Starter | 2,000 | 3 | $19/mo |
| Pro | 20,000 | 10 | $79/mo |
| Enterprise | Unlimited | Unlimited | Custom |

**Key endpoints:**
- `POST /api/auth/register` — Create account + free subscription
- `POST /api/llm/query` — Metered VLM proxy (devices never hold API keys)
- `GET /api/devices/{id}/audit/verify` — Server-side Merkle chain verification
- `WS /ws/device/{id}` — Real-time telemetry streaming
- `WS /ws/watch/{id}` — Live device observation for users

### Set-of-Mark Annotations

The annotation engine composites numbered marks and bounding boxes onto camera frames before sending to VLM. This improves grounding accuracy by giving the VLM explicit visual anchors to reference.

```
[Original Frame] + [Marks/Boxes] → [Composite Image] + [Text Prompt Suffix]
                                                          ↓
                                    "Marked elements: [1] Search button at (450, 120),
                                     [2] Text input at (300, 200), ..."
```

12 high-contrast colors. Corner-accented bounding boxes. Zone overlays with dashed borders. Auto-annotation from VLM detection results.

---

## Configuration

### Operator Settings (`rongle_operator/config/settings.json`)

```json
{
  "screen_width": 1920,
  "screen_height": 1080,
  "video_device": "/dev/video0",
  "capture_fps": 30,
  "hid_keyboard_dev": "/dev/hidg0",
  "hid_mouse_dev": "/dev/hidg1",
  "humanizer_jitter_sigma": 1.5,
  "humanizer_overshoot": 0.25,
  "vlm_model": "gemini-2.0-flash",
  "local_vlm_model": "HuggingFaceTB/SmolVLM-256M-Instruct",
  "allowlist_path": "rongle_operator/config/allowlist.json",
  "audit_log_path": "/mnt/secure/audit.jsonl",
  "estop_gpio_line": 17,
  "max_iterations": 100,
  "confidence_threshold": 0.5
}
```

### Portal Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./rongle.db` | Database connection string |
| `JWT_SECRET` | (generated) | HMAC key for JWT tokens |
| `GEMINI_API_KEY` | (required) | Google Gemini API key |
| `RATE_LIMIT_PER_MINUTE` | `60` | Max requests per IP per minute |
| `CORS_ORIGINS` | `*` | Allowed CORS origins |
| `RONGLE_DEBUG` | `false` | Enable debug logging + SQL echo |

### Frontend Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | (required for direct mode) | Gemini API key |
| `VITE_PORTAL_URL` | `http://localhost:8000` | Portal API base URL |

---

## Security Model

### Hardware Isolation

The target computer sees **only a USB HID device** — no network, no drivers, no software installation. This is the same protocol used by a keyboard and mouse. The target cannot detect that it is being operated by AI.

### Policy Engine

Every keystroke and click is validated against a configurable allowlist before execution. Default policy blocks:
- Destructive commands (`rm -rf`, `mkfs`, `dd if=`, `chmod 777`)
- Remote code execution (`curl|sh`, `wget|sh`, `python -c`, `powershell -enc`)
- Dangerous key combos (`CTRL ALT DELETE`)
- Out-of-bounds mouse clicks
- Excessive command rates (>50/sec)

### Audit Trail

The Merkle hash chain makes the audit log tamper-evident. If any entry is modified, deleted, or reordered, all subsequent hashes break. The portal can independently verify the chain.

### Portal Security

- JWT access tokens (1hr) + refresh tokens (30 days)
- bcrypt password hashing with auto-deprecation
- Per-IP rate limiting (sliding window)
- Devices authenticate via API key (`rng_` prefix), never hold LLM API keys
- CORS configurable per-deployment

---

## Development

```bash
# Frontend dev server (hot reload)
npm run dev

# Portal dev server (auto-reload)
uvicorn portal.app:app --reload --host 0.0.0.0 --port 8000

# Operator dry-run (no actual HID output)
python -m rongle_operator.main --dry-run --software-estop

# Build frontend for production
npm run build
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, TypeScript, Tailwind CSS, Vite |
| CNN | TensorFlow.js 4.22 (WebGL backend) |
| Portal | FastAPI, SQLAlchemy 2.0, aiosqlite |
| Operator | Python 3.11+, OpenCV, gpiod |
| VLM | Google Gemini API, HuggingFace Transformers |
| HID | USB OTG ConfigFS, CH9329 UART, Web Serial API |
| Auth | JWT (python-jose), bcrypt (passlib) |
| Audit | SHA-256 Merkle chain, append-only JSONL |

---

## License

MIT — see [LICENSE](LICENSE) for details.
