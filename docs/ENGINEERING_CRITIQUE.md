# Engineering Critique: "Brutally Honest" Review

**Date:** 2026-02-03
**Status:** Post-Merge Integration

## 1. Security Flaws

### A. Secret Handling
*   **Gemini API Key (Frontend):** Currently stored in `sessionStorage` in Direct Mode. While better than hardcoding, this is vulnerable to XSS. In a production context, this key should never leave the server.
*   **Agent Token (WebSocket):** The `AGENT_TOKEN` is passed in plain text over `ws://` (not `wss://`) in local deployments. On a shared LAN, this is trivial to sniff.
    *   **Recommendation:** Enforce `wss://` (TLS) even for local connections, perhaps via a self-signed cert generated on the operator device during setup.

### B. Policy Bypass
*   **Regex Weakness:** The `PolicyGuardian` uses simple regexes like `rm -rf`. A malicious actor could bypass this with `rm -r -f` or `rm --recursive --force`.
    *   **Recommendation:** Move to a parser-based validation (tokenize the command string) rather than regex.

## 2. Architectural Debt

### A. Redundant State Management
*   The `useAgent` hook and `App.tsx` share some overlapping responsibilities regarding hardware state.
*   The `AgentBridge` logic is slightly fragmented between `services/bridge.ts` and `services/hid-bridge.ts`. The merge of the two branches seems to have left two bridge concepts.

### B. "Happy Path" Dependency
*   The system assumes the network is stable. WebSocket reconnection logic is basic.
*   If the VLM returns malformed JSON (common with smaller models), the error handling falls back to a generic "WAIT" state without adequate user feedback on *why* it failed.

## 3. Scalability Concerns

### A. Python Async Event Loop
*   The `rng_operator` uses `asyncio`. If the CNN inference (running on CPU on a Pi) takes 200ms, it might block the event loop if not properly threaded/process-isolated. The current `asyncio.to_thread` usage helps, but CPU-bound tasks (vision) compete with IO-bound tasks (websocket).

### B. Database
*   The Portal uses SQLite by default. This will lock under concurrent write load (e.g., multiple agents reporting telemetry simultaneously).
    *   **Recommendation:** Enforce PostgreSQL for any "Pro" deployment.

## 4. Usability

### A. Configuration Friction
*   Setting up the `AGENT_TOKEN` requires editing a JSON file or env var on the Pi. There is no "pairing" flow (e.g., QR code scanning) which is standard for IoT devices in 2026.

---

# Action Plan

1.  **Refine Policy Engine:** Implement a tokenizer for shell commands.
2.  **Unify Bridges:** Merge `hid-bridge.ts` and `bridge.ts` into a single interface.
3.  **Secure Local Link:** Add TLS support to the Operator.
