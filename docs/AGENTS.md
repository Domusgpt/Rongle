# AGENTS.md — Intelligence Operating Manual

**Role:** You are the AI Developer / Maintainer (e.g., Rongle, Agentic Ducky).
**Scope:** This repository (`rng_operator`, `portal`, `frontend`).

## 1. Codebase Topology

### 1.1 `rng_operator/` (The Brain)
*   **Purpose:** The hardware-isolated daemon running on the edge device (Pi Zero / Android).
*   **Key Modules:**
    *   `main.py`: The `Look -> Plan -> Act -> Verify` loop. **Do not modify the loop structure without updating the state machine diagram.**
    *   `hygienic_actuator/`: Only this module touches hardware (`/dev/hidg*`). **Strict validation required.**
    *   `visual_cortex/`: Vision pipeline. `FrameGrabber` handles V4L2/Network. `VLMReasoner` handles high-level logic.
    *   `policy_engine/`: **Security Critical.** All actions must pass `guardian.check_command()`.
    *   `immutable_ledger/`: Audit logs. **Append-only.**

### 1.2 `portal/` (The Cloud)
*   **Purpose:** SaaS backend for authentication, device management, and billing.
*   **Stack:** FastAPI, PostgreSQL (asyncpg), Redis (rate limiting).
*   **Key Files:** `portal/models.py` (SQLAlchemy), `portal/routers/` (API endpoints).

### 1.3 `frontend/` (The User)
*   **Purpose:** React PWA for control and configuration.
*   **Stack:** Vite, React 19, Tailwind CSS, Capacitor (Android wrapper).
*   **Key Files:** `src/App.tsx` (Main UI), `src/services/gemini.ts` (LLM Interface).

## 2. Core Directives

1.  **Safety First (Hardware):**
    *   **NEVER** bypass `PolicyGuardian`.
    *   **ALWAYS** wrap HID writes in try/except blocks to catch hardware faults.
    *   **MANDATORY** E-Stop check in every iteration of `agent_loop`.

2.  **Privacy First (Data):**
    *   If `require_privacy=True` is passed to `VLMReasoner`, **MUST** use local backend (e.g., SmolVLM).
    *   **NEVER** log raw screenshots to cloud storage unless explicitly configured by the user. Audit logs store local hashes only.

3.  **Code Style:**
    *   **Python:** Type hints are mandatory (`mypy` strict). Use `black` formatting.
    *   **TypeScript:** Strict mode enabled. Use functional components and hooks.

4.  **Testing Protocol:**
    *   **Backend:** `pytest tests/`. Mock hardware interactions (`/dev/hidg*`).
    *   **Frontend:** `npm run test` (`vitest`). Mock API calls (`@google/genai`).
    *   **E2E:** `npm run test:e2e` (requires running backend).

## 3. Common Tasks & Patterns

### Adding a New Command
1.  **Define:** Add the command logic to `DuckyScriptParser` (`rng_operator/hygienic_actuator/ducky_parser.py`).
2.  **Validate:** Add a rule to `PolicyGuardian` (`rng_operator/policy_engine/guardian.py`).
3.  **Execute:** Implement the HID report generation in `HIDGadget` (`rng_operator/hygienic_actuator/hid_gadget.py`).
4.  **Test:** Add a unit test case in `tests/test_ducky_parser.py`.

### Updating the Vision Model
1.  **Local:** Update `rng_operator/visual_cortex/vlm_reasoner.py` -> `LocalVLMBackend`.
2.  **Remote:** Update `GeminiBackend` model string (e.g., `gemini-2.0-flash`).
3.  **Frontend:** Update `services/gemini.ts` to match.

## 4. Troubleshooting

*   **"Device or resource busy"**: The HID gadget is locked. Check if another process is using `/dev/hidg0`. Run `lsof /dev/hidg0`.
*   **"Calibration Failed"**: The `ReflexTracker` cannot find the cursor.
    *   Check HDMI cable connection.
    *   Ensure the cursor is visible (not hidden by OS).
    *   Check `assets/cursors/` for matching templates.
*   **"Policy Blocked"**: The command triggered a safety rule. Check `rng_operator/config/allowlist.json`.
