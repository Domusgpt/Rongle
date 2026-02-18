# Future Improvements and Recommended Fixes
**Date:** 2026-02-10
**Engineer:** Jules (AI Assistant)

## Recommended Technical Improvements

### 1. Vision Subsystem Decoupling
- **Hardware Abstraction:** The `FrameGrabber` currently depends directly on `cv2`. Moving this to a backend-agnostic interface (e.g., a `VideoSource` protocol) would allow for easier mocking in tests and support for non-OpenCV backends (like raw V4L2 or specialized hardware libraries).
- **Dependency Management:** The test suite currently fails to collect many tests if `cv2` or `numpy` are missing. These should be made optional imports with graceful skips in the test suite to allow core logic tests to run on lightweight CI environments.

### 2. DuckyScriptParser Enhancements
- **Stateful Parsing:** While many methods were made static, the parser itself still maintains cursor state (`_cursor_x`, `_cursor_y`). For truly stateless multi-threaded use, this state should be moved into a `ParsingContext` object passed to the parse methods.
- **Validation Layer:** Add a pre-parsing validation step that checks for common Ducky Script errors (e.g., invalid modifier names) before execution begins.

### 3. Audit System Robustness
- **Automatic Log Rotation:** Currently, the audit log grows indefinitely. Implementing a rotation strategy (e.g., new file every 10k entries) with hash-linkage across files would prevent performance degradation while maintaining security.
- **Asynchronous Logging:** Move `AuditLogger` writes to a background thread to prevent logging I/O from blocking the high-frequency actuation loop.

### 4. Policy Engine Granularity
- **Context-Aware Policies:** The `PolicyGuardian` is currently stateless. Enhancing it to track recent history (e.g., "don't allow 5 clicks in the same region within 1 second") would provide better protection against bot-like behavior or malicious scripts.
- **Dynamic Allowlist Updates:** Support for reloading `allowlist.json` without restarting the operator would improve operational flexibility.

### 5. Testing and CI
- **Hardware Emulation:** Develop a more robust "Virtual Pi" environment that mocks `/dev/hidgX` and the camera interface more accurately, allowing for E2E testing without physical hardware.
- **Integration Tests:** Add tests that specifically verify the integration between `VLMReasoner` and `HIDGadget` using mocked LLM responses.

---
*End of Recommendations*
