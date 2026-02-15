# Architecture

## System Overview

Rongle is structured as three independent layers that communicate over HTTP/WebSocket. Each layer can run on a different machine or all on one device.

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  ANDROID / BROWSER                    CLOUD / SERVER                │
│  ┌───────────────────┐               ┌───────────────────┐         │
│  │    FRONTEND        │    HTTPS      │     PORTAL         │         │
│  │    (React PWA)     │◄────────────►│    (FastAPI)        │         │
│  │                    │    WS         │                    │         │
│  │  ┌──────────────┐ │               │  ┌──────────────┐ │         │
│  │  │ CNN Engine    │ │               │  │ LLM Service  │ │         │
│  │  │ (TF.js/WebGL)│ │               │  │ (Gemini API) │ │         │
│  │  └──────────────┘ │               │  └──────────────┘ │         │
│  │  ┌──────────────┐ │               │  ┌──────────────┐ │         │
│  │  │ HID Bridge   │ │               │  │ Auth + Billing│ │         │
│  │  │ (Web Serial) │ │               │  └──────────────┘ │         │
│  │  └──────┬───────┘ │               │  ┌──────────────┐ │         │
│  └─────────┼─────────┘               │  │ Audit Verify │ │         │
│            │ USB                      │  └──────────────┘ │         │
│            ▼                          └───────────────────┘         │
│  ┌─────────────────────┐                                            │
│  │   TARGET COMPUTER    │   PI HARDWARE (OPTIONAL)                  │
│  │   (receives HID)     │   ┌───────────────────┐                  │
│  └─────────────────────┘   │    OPERATOR         │                  │
│                             │    (Python daemon)  │                  │
│                             │  ┌───────────────┐ │                  │
│                             │  │ HID Gadget    │─┼──► USB /dev/hidg│
│                             │  │ Frame Grabber │─┼──► HDMI capture │
│                             │  │ Policy Engine │ │                  │
│                             │  │ Audit Logger  │ │                  │
│                             │  └───────────────┘ │                  │
│                             └───────────────────┘                  │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### Android Mode (MVP)

```
Phone Camera ──► LiveView ──► CNN (local, ~20ms) ──► Detections
                     │                                    │
                     └──► VLM Query (Gemini, ~2s) ◄──────┘ (CNN results enrich prompt)
                                    │
                                    ▼
                            Ducky Script ──► Policy Check ──► HID Bridge
                                                                  │
                                                    ┌─────────────┘
                                                    ▼
                                    CH9329 USB Dongle ──► Target PC
```

### Pi Mode (Production)

```
HDMI Capture ──► Frame Grabber ──► VLM Reasoner ──► Ducky Script
                       │                                   │
                       └──► Reflex Tracker                 ▼
                            (cursor position)       Policy Guardian
                                                          │
                                                          ▼
                                                    HID Gadget
                                                    /dev/hidg0 (kbd)
                                                    /dev/hidg1 (mouse)
                                                          │
                                                          ▼
                                                    Target Computer
```

### Portal-Mediated Mode

```
Device ──► portal_client.vlm_query() ──► Portal /api/llm/query
                                              │
                                   ┌──────────┘
                                   ▼
                           Quota Check ──► Gemini API ──► Usage Record
                                                              │
                                                              ▼
                                                    Response + remaining_quota
```

## Agent State Machine

```
       ┌──────┐
       │ IDLE │
       └──┬───┘
          │ START (user enters goal)
          ▼
    ┌───────────┐
    │ PERCEIVING│◄────────────────────────────────┐
    └─────┬─────┘                                  │
          │ frame captured                         │
          ▼                                        │
    ┌───────────┐                                  │
    │ PLANNING  │                                  │
    └─────┬─────┘                                  │
          │ VLM returns target element             │
          ▼                                        │
    ┌───────────┐                                  │
    │  ACTING   │                                  │
    └─────┬─────┘                                  │
          │ HID commands executed                  │
          ▼                                        │
    ┌───────────┐       success / retry            │
    │ VERIFYING │──────────────────────────────────┘
    └─────┬─────┘
          │ goal complete / max retries / error
          ▼
    ┌───────────┐        ┌─────────┐
    │  STOPPED  │        │  ERROR  │
    └───────────┘        └─────────┘

    EMERGENCY_STOP → immediately to STOPPED from any state
```

## CNN Vision Pipeline

The browser-based CNN system runs a parallel "fast reflex" loop alongside the slower VLM reasoning:

```
Frame (base64) ────┬──────────────────────────────────┐
                   │                                   │
                   ▼                                   ▼
         ┌─────────────────┐                ┌──────────────────┐
         │  CNN Fast Path   │                │  VLM Slow Path    │
         │  (~20-30ms)      │                │  (~1500-3000ms)   │
         │                  │                │                   │
         │  ┌────────────┐ │                │  Gemini API call  │
         │  │ Preprocessor│ │                │  with SoM prompt  │
         │  │ 320×320 RGB │ │                └────────┬──────────┘
         │  └──────┬─────┘ │                          │
         │         │       │                          │
         │  ┌──────┴─────┐ │                          │
         │  │  Detector   │ │                          │
         │  │ MobileNet-  │ │                          │
         │  │ SSD (17 cls)│ │                          │
         │  └──────┬─────┘ │                          │
         │         │       │                          │
         │  ┌──────┴─────┐ │                          │
         │  │ Classifier  │ │                          │
         │  │ Screen type │ │                          │
         │  │ (11 classes)│ │                          │
         │  └──────┬─────┘ │                          │
         │         │       │                          │
         │  ┌──────┴─────┐ │                          │
         │  │Frame Differ │ │                          │
         │  │ SSIM + pHash│ │                          │
         │  └─────────────┘ │                          │
         └────────┬─────────┘                          │
                  │                                    │
                  ▼                                    ▼
         CNN Detections                        VLM Analysis
         (boxes, classes,                      (action plan,
          screen type,                          ducky script,
          change regions)                       coordinates)
                  │                                    │
                  └──────────────┬──────────────────────┘
                                 │
                                 ▼
                        Combined Result
                  (auto-annotations from CNN,
                   action plan from VLM)
```

### CNN Model Architectures

**RongleNet-Detect (UI Detection)**
```
Input: 320×320×3
  │
  ├─ Conv2D 3×3/2 → 32 filters (160×160)
  ├─ DepthwiseSeparable 3×3/1 → 64 (160×160)
  ├─ DepthwiseSeparable 3×3/2 → 128 (80×80)  ──► Feature Map A (3 anchors)
  ├─ DepthwiseSeparable 3×3/1 → 128 (80×80)
  ├─ DepthwiseSeparable 3×3/2 → 256 (40×40)  ──► Feature Map B (3 anchors)
  ├─ DepthwiseSeparable 3×3/1 → 256 (40×40)
  ├─ DepthwiseSeparable 3×3/2 → 512 (20×20)  ──► Feature Map C (3 anchors)
  ├─ DepthwiseSeparable 3×3/1 → 512 (20×20)
  └─ DepthwiseSeparable 3×3/2 → 1024 (10×10) ──► Feature Map D (3 anchors)

Each feature map → Conv2D 1×1 → anchors × (4 + num_classes + 1)
  4 = bbox offsets (cx, cy, w, h)
  17 = UI element classes
  1 = objectness score

Anchor boxes:
  80×80: 3 anchors → 19,200 boxes (small: icons, checkboxes)
  40×40: 3 anchors →  4,800 boxes (medium: buttons, inputs)
  20×20: 3 anchors →  1,200 boxes (large: dialogs, toolbars)
  10×10: 3 anchors →    300 boxes (very large: full panels)
  Total: 25,500 boxes → NMS → max 50 detections
```

**RongleNet-Classify (Screen Classification)**
```
Input: 224×224×3
  │
  ├─ Conv2D 3×3/2 → 32 (112×112)
  ├─ 4× DepthwiseSeparable blocks → 512 (7×7)
  ├─ GlobalAveragePooling2D → 512
  ├─ Dense → 128 (ReLU, Dropout 0.3)
  └─ Dense → 11 (Softmax)

Classes: desktop, browser, terminal, file_manager, settings,
         dialog, login, editor, spreadsheet, media, unknown
```

## Merkle Audit Chain

```
Entry 0 (Genesis)          Entry 1                    Entry 2
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│ prev: "000...000" │      │ prev: hash_0      │      │ prev: hash_1      │
│ ts:   1706000000  │      │ ts:   1706000001  │      │ ts:   1706000002  │
│ action: "START"   │      │ action: "CLICK"   │      │ action: "STRING"  │
│ ss_hash: "abc..." │      │ ss_hash: "def..." │      │ ss_hash: "ghi..." │
│ hash_0 = SHA256(  │─────►│ hash_1 = SHA256(  │─────►│ hash_2 = SHA256(  │
│   ts|action|      │      │   ts|action|      │      │   ts|action|      │
│   ss_hash|prev)   │      │   ss_hash|prev)   │      │   ss_hash|prev)   │
└──────────────────┘      └──────────────────┘      └──────────────────┘

Verification: replay from genesis, recompute each hash, compare.
If any entry is modified, all subsequent hashes break.
```

## Set-of-Mark (SoM) Annotation Pipeline

```
┌──────────────┐    ┌──────────────────┐    ┌──────────────────────┐
│ Raw Camera    │    │  Annotation       │    │  Composite Image     │
│ Frame         │───►│  Engine           │───►│  (JPEG base64)       │
│ (base64 JPEG) │    │  • marks (circles)│    │  + Prompt Suffix:    │
└──────────────┘    │  • boxes (rects)  │    │  "[1] Button (50,30)"│
                    │  • zones (areas)  │    │  "[2] Input (100,80)"│
                    │  • labels (text)  │    └──────────┬───────────┘
                    └──────────────────┘               │
                                                        ▼
                                                    VLM receives
                                                    annotated image
                                                    + text anchors
```

## Portal Authentication Flow

```
Client                              Portal
  │                                    │
  │  POST /auth/register               │
  │  {email, password}                 │
  │───────────────────────────────────►│
  │                                    │ Create User + free Subscription
  │  {access_token, refresh_token}     │
  │◄───────────────────────────────────│
  │                                    │
  │  GET /devices/ (Bearer token)      │
  │───────────────────────────────────►│
  │                                    │ Validate JWT, return devices
  │  [{id, name, api_key, ...}]        │
  │◄───────────────────────────────────│
  │                                    │
  │  ... token expires (60 min) ...    │
  │                                    │
  │  POST /auth/refresh                │
  │  {refresh_token}                   │
  │───────────────────────────────────►│
  │                                    │ Issue new token pair
  │  {access_token, refresh_token}     │
  │◄───────────────────────────────────│
```

## HID Transport Layer

### Pi Mode: USB OTG ConfigFS

```
Operator Python Process
  │
  ├── os.open("/dev/hidg0", O_WRONLY)  ──► 8-byte keyboard reports
  └── os.open("/dev/hidg1", O_WRONLY)  ──► 4-byte mouse reports
                                              │
                                         USB OTG
                                              │
                                         Target PC
                                         (sees USB keyboard + mouse)
```

### Android Mode: CH9329 via Web Serial

```
Browser (Web Serial API)
  │
  ├── navigator.serial.requestPort()
  ├── port.open({ baudRate: 9600 })
  └── writer.write(ch9329_packet)
         │
         │  CH9329 Serial Protocol:
         │  [0x57, 0xAB, addr, cmd, len, ...data, checksum]
         │  cmd=0x02: keyboard report
         │  cmd=0x05: mouse report
         │
    USB-to-UART dongle (CH9329)
         │
    Target PC USB port
    (sees USB keyboard + mouse)
```

### Fallback: WebSocket Bridge

```
Browser ──► WebSocket ──► localhost companion app ──► USB HID
```

### Fallback: Clipboard

```
Browser ──► navigator.clipboard.writeText() ──► user pastes manually
```

## Technology Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Frontend framework | React 19 + Vite | Mature ecosystem, fast HMR, CDN-loadable via importmaps |
| CSS | Tailwind CDN | Zero build config, rapid prototyping |
| VLM | Gemini API | Best cost/quality for vision tasks, structured JSON output |
| Local VLM | SmolVLM-256M | Small enough for Pi Zero 2 W (512MB RAM) |
| CNN framework | TensorFlow.js | Browser-native, WebGL acceleration, model persistence |
| Backend | FastAPI + SQLAlchemy async | Fast, typed, auto-docs, async-first |
| Database | SQLite (MVP) → Postgres | Zero-config dev, production-swap via URL |
| Auth | JWT + bcrypt | Stateless, standard, well-supported |
| Audit | Merkle hash chain | Tamper-evident without blockchain overhead |
| HID protocol | USB HID over OTG / CH9329 | Universal compatibility, no target drivers needed |
| Serial protocol | Web Serial API | Browser-native, no native app required |

---
[Back to Documentation Index](INDEX.md)
