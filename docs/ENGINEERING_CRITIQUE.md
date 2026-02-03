# Engineering Critique & Technical Debt Analysis

This document outlines critical engineering flaws, scalability bottlenecks, and technical debt identified within the Rongle codebase.

## 1. Reliability & Stability (Must Fix)

### Critical: Lack of Persistent Agent State
The `rongle_operator` runs a stateless loop (`agent_loop` in `main.py`). If the process crashes or is restarted (e.g., by a watchdog), the agent loses all context:
- It forgets the current `goal`.
- It forgets `previous_action`.
- It re-runs calibration unnecessarily.

**Recommendation:** Implement a `StateStore` (SQLite/JSON) that persists the current goal, step index, and context. On startup, check for an active session and resume.

### Critical: Fragile API Key Handling
While the frontend now proxies VLM calls, the `PortalClient` in `rongle_operator/portal_client.py` relies on a long-lived `api_key` passed in `__init__`. There is no logic to:
- Refresh tokens.
- Handle `401 Unauthorized` gracefully (e.g., re-authenticate).
- Rotate keys.

**Recommendation:** Implement a robust `AuthManager` class that handles token lifecycle, including refresh flows.

### Major: Unhandled Hardware Failures
The `FrameGrabber` raises `RuntimeError` on capture failure. In `main.py`, this is caught, but `HIDGadget` write failures are not consistently handled. If the USB cable is disconnected, the daemon may zombie or crash without alerting the portal.

**Recommendation:** Wrap hardware I/O in retry logic with exponential backoff and send a "Hardware Fault" telemetry event to the portal.

## 2. Scalability (Should Fix)

### Major: Database Concurrency
The Portal defaults to `sqlite+aiosqlite`. While async, SQLite has a single write lock. High-frequency telemetry from multiple devices will cause `database is locked` errors.

**Recommendation:**
1. Enforce `PostgreSQL` for production via strict env checks.
2. Implement connection pooling (SQLAlchemy `pool_size`).
3. Batch telemetry writes (e.g., buffer logs in Redis and bulk-insert to Postgres).

### Major: Synchronous Blocks in Async Code
Review `portal/app.py`. While mostly async, ensuring no blocking calls (like standard `open()` or synchronous `requests`) slip into the event loop is crucial.

**Recommendation:** Audit all I/O paths. Ensure `PortalClient` uses `aiofiles` for any local file operations (e.g., saving settings).

## 3. Maintainability (Improvement)

### Minor: Hardcoded Paths & Constants
- `/mnt/secure/audit.jsonl` is hardcoded in defaults.
- `/dev/video0` and `/dev/hidg*` are hardcoded.
- `assets/cursors` is expected but not checked for existence during build.

**Recommendation:**
- Move all paths to a validated `config.yaml` or `.env` loader.
- Use `pathlib` consistently.
- Add a `check_environment()` startup routine that verifies hardware paths exist before entering the main loop.

### Minor: Code Duplication
- `training/data_collector.py` re-implements capture logic similar to `operator/visual_cortex/frame_grabber.py`.
- `ducky_parser.py` exists in both backend and potentially logic in frontend (for validation).

**Recommendation:** Refactor shared logic into a `rongle_common` package or strictly import.

## 4. Security (Critical)

### Critical: Merkle Chain Storage
The audit log is stored at `/mnt/secure/audit.jsonl`. If this is just a folder on the root partition, "tamper-evidence" is weak because a root attacker can delete the file.

**Recommendation:**
- If possible, mount a separate, read-only-after-write partition.
- Or, strictly stream logs to the Portal immediately and treat the local copy as a temporary buffer.

### Major: No TLS Pinning
`PortalClient` connects to `https://portal.rongle.io` relying on the system CA. A compromised device could be Man-in-the-Middle'd.

**Recommendation:** Implement certificate pinning in `httpx` client.

## 5. Vision Architecture

### Major: Stubbed Detectors
`FastDetector` is currently a stub. The system claims "Foveated Rendering" but falls back to full-frame VLM immediately. This is misleading and inefficient.

**Recommendation:**
- Prioritize training a quantized MobileNet-SSD.
- Integrate `onnxruntime` to run the model.
