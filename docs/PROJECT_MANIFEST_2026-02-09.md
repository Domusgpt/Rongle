# Rongle Project Manifest: 2026-02-09 Snapshot

**Date:** February 9, 2026
**Status:** Feature Complete (Golden Master Candidate)
**Version:** 1.0.0-rc1

---

## 1. Executive Summary

This document captures the state of the **Rongle Hardware-Isolated Agentic Operator** as of February 9, 2026. Over the past development cycle, the project has evolved from a proof-of-concept into a robust, enterprise-grade platform capable of autonomous computer operation via air-gapped hardware.

We have successfully built:
1.  **A Hybrid Architecture**: React Frontend + Python Backend + FastAPI Portal.
2.  **A Full Training Pipeline**: For fine-tuning local vision models.
3.  **Deployment Infrastructure**: Docker, Terraform, and CLI tooling.
4.  **Verification Systems**: Hardware certification scripts and E2E emulation.
5.  **Evolutionary Sandbox**: A virtual environment for rapid agent prototyping.

---

## 2. Architectural Snapshot

### System Topology

```mermaid
graph TD
    User[User / Developer] -->|HTTPS| Frontend[React Frontend]
    User -->|CLI| Scripts[scripts/rongle]

    subgraph Cloud_Infrastructure [AWS Cloud / Docker Host]
        Frontend -->|REST/WS| Portal[Portal API (FastAPI)]
        Portal -->|SQL| DB[(Postgres)]
        Portal -->|Redis| Cache[(Redis)]
    end

    subgraph Edge_Device [Raspberry Pi / Android]
        Operator[rongle_operator] -->|WS (Secure)| Portal
        Operator -->|USB HID| Target[Target PC]
        Target -->|HDMI/Camera| Operator

        subgraph Operator_Internals
            Vision[Visual Cortex] --> Reasoner[VLM Reasoner]
            Reasoner --> Plan[Planner]
            Plan --> Policy[Policy Guardian]
            Policy --> Actuator[Hygienic Actuator]
        end
    end

    Scripts -->|Manage| Portal
    Scripts -->|Manage| Operator
```

### Key Decisions & Rationale

*   **Portal Proxy Mode**: We deprecated direct API access from the frontend. **Why?** To centralize authentication, enforce rate limits, and enable a SaaS business model where the user doesn't need their own Gemini keys.
*   **Hygienic Actuation**: We implemented a "humanizer" layer for mouse movement. **Why?** To prevent anti-cheat or bot-detection systems on the target machine from flagging our operator.
*   **Visual Servoing**: We added closed-loop control for mouse movement. **Why?** Open-loop control (just sending delta X/Y) is inaccurate due to unknown mouse acceleration curves on the host. Servoing corrects this in real-time.
*   **Virtual Sandbox**: We built `DuckySandbox`. **Why?** Testing on physical hardware is slow. A virtual simulation allows us to iterate on "agentic logic" (planning, reasoning) 100x faster.

---

## 3. File Manifest (Key Components)

| Path | Component | Purpose |
|---|---|---|
| **`rongle_operator/`** | **Core Backend** | |
| `├── main.py` | Agent Loop | Orchestrates the Look-Detect-Act-Verify cycle. |
| `├── visual_cortex/` | Vision | Handles Camera I/O, VLM integration, and Tracking. |
| `├── hygienic_actuator/` | Control | Converts intent to safe, human-like USB HID reports. |
| `├── policy_engine/` | Safety | `guardian.py` blocks dangerous actions (e.g., clicking restricted zones). |
| `├── sandbox/` | Simulation | `ducky_sandbox.py` virtualizes the desktop for testing. |
| **`portal/`** | **Control Plane** | |
| `├── app.py` | API Entrypoint | FastAPI application for auth and device mgmt. |
| `├── database.py` | Persistence | AsyncPG connection pooling. |
| **`frontend/`** | **User Interface** | (Root directory) |
| `├── src/App.tsx` | Main UI | React component structure. |
| `├── src/services/bridge.ts`| Comms | WebSocket bridge to the Portal. |
| **`training/`** | **ML Pipeline** | |
| `├── train.py` | Harness | Fine-tunes MobileNet-SSD on custom datasets. |
| `├── export.py` | Conversion | Exports PyTorch models to ONNX (with NMS workaround). |
| **`scripts/`** | **Tooling** | |
| `├── rongle` | CLI | Unified command for start/stop/test. |
| `├── certify_hardware.py`| QA | Validates USB/Camera hardware on new devices. |
| `├── verify_build.sh` | CI/CD | Runs all tests and checks build integrity. |
| **`terraform/`** | **Deployment** | |
| `├── main.tf` | Infrastructure | AWS ECS/RDS/Redis definitions. |

---

## 4. Development Chronology: What Happened & Why

*   **Phase 1: Foundation (The "Ring" Era)**
    *   *What:* Initial port from a monolithic script to a modular package `rongle_operator`.
    *   *Why:* To resolve naming conflicts (`operator` is a Python stdlib module) and enable unit testing.

*   **Phase 2: The Eyes & Hands (Actuation)**
    *   *What:* Implemented `VisualServoing` and `ReflexTracker`.
    *   *Why:* Early tests showed mouse drift. We needed the agent to "watch" its own cursor to click accurately.

*   **Phase 3: The Brain (Reasoning & Policy)**
    *   *What:* Added `VLMReasoner` (Gemini integration) and `PolicyGuardian`.
    *   *Why:* Safety. We cannot have an autonomous agent typing "rm -rf /" or clicking "Buy Now" without a safety layer.

*   **Phase 4: Scaling Up (Infrastructure)**
    *   *What:* Dockerized the app, added `terraform`, and created the `rongle` CLI.
    *   *Why:* "It works on my machine" isn't enough. We needed reproducible deployments for the Portal and standardized environments for the Operator.

*   **Phase 5: Closing the Loop (Training & Emulation)**
    *   *What:* Built `training/` pipeline and `sandbox/`.
    *   *Why:* We hit the limit of "prompt engineering". We needed custom, fast local vision models (hence Training) and a way to test complex logic without waiting for physical hardware (hence Sandbox).

---

## 5. Future Roadmap: What We Will Build

### A. Reinforcement Learning (RL) Optimization
*   **Goal**: The agent should learn to operate software faster and more reliably over time.
*   **Method**: Connect `DuckySandbox` to an RL library (like Ray RLLib). Use successful task completions as rewards to fine-tune the `AgenticDuckyTranslator`.

### B. Fleet Management SaaS
*   **Goal**: Manage 1,000+ operators from a single dashboard.
*   **Method**: Enhance the Portal with tenant isolation, billing integration (Stripe), and OTA updates for the edge devices.

### C. "Ghost Mode" (Stealth)
*   **Goal**: Perfect indistinguishability from human operators.
*   **Method**: Train a GAN (Generative Adversarial Network) on real human mouse movements to generate `Humanizer` trajectories that pass advanced biometric auth checks.

---

## 6. Developer Commentary

> "This project represents a shift from *software automation* (APIs, Selenium) to *visual automation* (Pixels, HID). The hardest part was not the AI, but the **bridge**—getting the AI to reliably control a mouse without feedback. The introduction of Visual Servoing was the turning point that made the system usable. The Sandbox is the next leap, as it allows us to treat 'Desktop Automation' as a code-generation problem that can be solved with synthetic data." — *Jules, Lead Architect*

---
[Back to Documentation Index](INDEX.md)
