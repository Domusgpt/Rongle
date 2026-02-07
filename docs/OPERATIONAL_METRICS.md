# Operational Metrics & KPIs

This document defines the Key Performance Indicators (KPIs) and operational metrics for monitoring the Rongle Agent fleet.

## 1. Reliability Metrics

| Metric | Definition | Target | Source |
|---|---|---|---|
| **Mission Success Rate** | % of sessions that reach a `GOAL_COMPLETE` state without error. | > 95% | `session_manager.db` / Audit Log |
| **Crash Rate** | Number of unhandled exceptions per 1,000 active minutes. | < 0.1 | Portal Logs (`ERROR` level) |
| **Recovery Time** | Time between a crash and successful session resumption. | < 5s | Portal Telemetry (Heartbeat gaps) |

## 2. Performance Metrics

| Metric | Definition | Target | Source |
|---|---|---|---|
| **VLM Latency** | Time from frame capture to receiving JSON response. | < 2s | `PortalClient` logs |
| **Reflex Latency** | Time for local CNN to detect UI elements (`FastDetector`). | < 50ms | `rongle_operator` logs |
| **Servoing Convergence** | Number of iterations required for mouse to settle on target. | < 3 | `servoing.py` logs |
| **Foveation Efficiency** | % of VLM queries using cropped vs. full frames. | > 80% | `main.py` telemetry |

## 3. Security Metrics

| Metric | Definition | Target | Source |
|---|---|---|---|
| **Policy Blocks** | Number of actions blocked by `PolicyGuardian` per session. | 0 (Ideal) | Audit Log (`BLOCKED`) |
| **Semantic Rejections** | Number of actions rejected by VLM Semantic Guard. | Low | Audit Log (`SEMANTIC_BLOCK`) |
| **Auth Failures** | Rate of 401/403 errors from devices. | 0 | Portal Access Logs |

## 4. Hardware Health

| Metric | Definition | Target | Source |
|---|---|---|---|
| **Frame Drop Rate** | % of frames dropped by `FrameGrabber`. | < 1% | `FrameGrabber` internal counters |
| **HID Write Errors** | Count of failed USB writes. | 0 | `HARDWARE_FAULT` logs |
| **Thermal Status** | CPU temperature of the Operator device (Pi). | < 70°C | System Telemetry |

## 5. Measurement Plan

### A. Local Measurement (Dev)
Developers can view real-time metrics in the `DeviceManager` "Telemetry" panel.
Run `scripts/analyze_logs.py` (to be implemented) on local `audit.jsonl` files.

### B. Fleet Measurement (Prod)
1.  **Ingestion:** `PortalClient` batches logs to Portal.
2.  **Storage:** Portal writes to PostgreSQL (metadata) and S3/Blob (screenshots).
3.  **Visualization:** Grafana dashboard connected to Portal DB.
