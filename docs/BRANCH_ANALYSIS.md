# Branch Analysis and Integration Roadmap
**Date:** 2026-02-10

## Current Branch Landscape

### 1. `main`
- **Status:** Stable base.
- **Architecture:** Legacy (`rongle_operator/`, `components/` at root).

### 2. `claude/hardware-agentic-operator-8qMPS` (v2.0 Architecture)
- **Status:** Structural Refactor.
- **Key Changes:**
    - Renamed backend to `rng_operator/`.
    - Moved frontend to `src/`.
    - Cleaned up `embedded_agent/` legacy code.
    - Updated `docs/ARCHITECTURE.md`.

### 3. `feature/v2-async-webrtc-calibration` (RFC Features - Unified)
- **Status:** Ported and Unified.
- **Key Changes:**
    - Unified the structural changes from the `claude` branch with the feature logic from the local work.
    - **RFC-001 (Async Core):** Implemented async perception-action loop in `rng_operator/main.py`.
    - **RFC-003 (WebRTC):** Added `WebRTCReceiver`, `WebRTCServer`, and `WebRTCStreamer`.
    - **RFC-004 (Robust Calibration):** Ported `HomographyCalibrator` and integrated into the async loop.
    - **Stateless Parser:** Incorporated the refactored `DuckyScriptParser` with static methods.

### 4. `refactor-operator-add-frontend-tests-11752427816827345970`
- **Status:** UI/UX and Testing focus.
- **Contains:**
    - `docs/ROADMAP.md`, `docs/SYSTEM_STATUS.md`.
    - Enhanced `App.tsx` and components.
    - Vitest setup for frontend.
- **Merge Conflict Risk:** High (due to structural renaming in v2).

### 5. `review-and-testing-setup-406055881745593486`
- **Status:** Contextual docs.
- **Contains:** `docs/FLIPPER_ZERO_ANALYSIS.md`, Red Team docs.

## Integration Recommendation

1.  **Adopt the Unified Branch:** Use `feature/v2-async-webrtc-calibration` as the new development target. It has successfully reconciled the structural v2 changes with the core RFC features.
2.  **Selective Porting from UI Branch:** Manually port the `ROADMAP.md`, `SYSTEM_STATUS.md`, and any improved component logic from the `refactor-operator-add-frontend-tests` branch into the `src/` directory.
3.  **Standardize Dependencies:** Unify `rng_operator/requirements.txt` and `package.json` across all branches.
4.  **Consolidate Docs:** Centralize all new documentation into the `docs/` folder, ensuring no legacy references to `rongle_operator` remain.

## Risks
- **Dependency Hell:** Several branches add conflicting or overlapping requirements.
- **Hardware Drift:** Features implemented for specific hardware (e.g., Pi vs Android) need to be guarded by environment checks.
