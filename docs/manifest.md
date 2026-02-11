# Rongle System Manifest

## Version 1.0.0 (2026-Q1)

This manifest provides a comprehensive inventory of the Rongle ecosystem, detailing every file, service, and configuration artifact. It serves as the single source of truth for system auditing and integrity verification.

### 1. Directory Structure Overview

```
.
├── android/                  # Native Android Wrapper (Capacitor)
├── components/               # React UI Components
├── docs/                     # Documentation Suite
├── hooks/                    # Custom React Hooks
├── portal/                   # SaaS Backend (FastAPI)
├── rng_operator/             # Hardware Agent (Python)
├── scripts/                  # CI/CD and Utility Scripts
├── services/                 # Frontend Services
├── tests/                    # Integration Tests
└── training/                 # CNN Model Training Harness
```

### 2. Component Inventory

#### A. Frontend (React/Vite)
**Role:** The user interface for controlling the agent, viewing the video feed, and managing subscriptions.

| File/Path | Purpose | Technology |
|:--- |:--- |:--- |
| `App.tsx` | Main application entry point; handles routing between Direct/Portal modes. | React |
| `components/ActionLog.tsx` | Displays the scrolling log of agent actions and system events. | React, Lucide |
| `components/HardwareStatus.tsx` | Visualizes latency, FPS, and connection state. | React |
| `components/LiveView.tsx` | Renders the WebRTC/MJPEG stream and handles frame capture. | React, Canvas API |
| `hooks/useAgent.ts` | State machine logic for the agent (Perceive -> Plan -> Act). | TypeScript |
| `services/bridge.ts` | Abstraction layer for WebSocket communication. | TypeScript |
| `services/gemini.ts` | Client-side interface for Gemini 1.5 Flash (Direct Mode). | Google GenAI SDK |

#### B. Operator (Python Daemon)
**Role:** The "body" of the agent. Runs on the edge device (Pi/Jetson), controlling USB gadgets and capturing video.

| File/Path | Purpose | Criticality |
|:--- |:--- |:--- |
| `rng_operator/main.py` | Entry point. Initializes the AsyncIO event loop and WebSocket server. | **CRITICAL** |
| `rng_operator/hygienic_actuator/` | Human-like HID injection logic. | High |
| `rng_operator/visual_cortex/` | Vision pipeline (Frame grabber, CNN inference). | High |
| `rng_operator/policy_engine/` | Safety layer. Validates commands against allowlists. | **CRITICAL** |
| `rng_operator/config/allowlist.json` | JSON definition of allowed commands. | High |

#### C. Portal (FastAPI Backend)
**Role:** The "brain" of the SaaS operation. Handles user accounts, billing, and advanced VLM reasoning.

| File/Path | Purpose | Database |
|:--- |:--- |:--- |
| `portal/main.py` | FastAPI application factory. | - |
| `portal/routers/auth.py` | JWT authentication endpoints. | PostgreSQL |
| `portal/routers/devices.py` | Device registry and heartbeat management. | PostgreSQL |
| `portal/models.py` | SQLAlchemy ORM definitions (User, Device, Subscription). | - |

### 3. Service Dependencies

| Service | Version | Usage |
|:--- |:--- |:--- |
| **Redis** | 7.x | Rate limiting, Pub/Sub for device commands. |
| **PostgreSQL** | 16.x | Persistent storage for Portal data. |
| **Stripe** | API 2024-06 | Subscription billing and invoicing. |
| **Gemini** | 1.5 Flash | VLM for visual reasoning (Google Cloud). |

### 4. Configuration Manifest

| Environment Variable | Component | Description | Default |
|:--- |:--- |:--- |:--- |
| `VITE_PORTAL_URL` | Frontend | URL of the SaaS Portal. | `https://api.rongle.ai` |
| `AGENT_TOKEN` | Operator | Bearer token for local auth. | `change-me-in-prod` |
| `JWT_SECRET` | Portal | Secret key for signing tokens. | *Required* |
| `DATABASE_URL` | Portal | Postgres connection string. | `sqlite:///./portal.db` |
| `STRIPE_KEY` | Portal | Secret key for billing. | - |

### 5. Integrity Verification

To verify the integrity of your installation, run the provided checksum script:

```bash
# Verify Operator Files
sha256sum -c scripts/integrity/operator.sha256

# Verify Frontend Build
sha256sum -c scripts/integrity/frontend.sha256
```
