# Documentation Audit & Comparison

**Benchmark Targets:**
1.  **TinyPilot:** The gold standard for polished, consumer-friendly KVM documentation.
2.  **PiKVM:** The gold standard for technical, DIY hacker documentation.

## 1. TinyPilot Comparison

| Feature | TinyPilot | Rongle (Current) | Verdict |
| :--- | :--- | :--- | :--- |
| **Getting Started** | "Buy Kit -> Plug in -> Go". Very hardware focused. | "Run script -> Edit JSON". | **Weakness.** We lack a "Zero to Hero" guide for non-coders. |
| **Visuals** | High-quality GIFs of the UI. Photos of cables. | ASCII Art & Mermaid diagrams. | **Improvement:** Need screenshots of the Mobile App in action. |
| **Troubleshooting** | "What do the LEDs mean?" | Generic "Check logs". | **Improvement:** Specific failure modes (e.g., "Camera not found"). |

## 2. PiKVM Comparison

| Feature | PiKVM | Rongle (Current) | Verdict |
| :--- | :--- | :--- | :--- |
| **Hardware Compatibility** | Massive list (Pi 2/3/4/Zero, diverse HDMI chips). | "Raspberry Pi 4/5". | **Acceptable** for MVP, but need to validate Pi Zero 2 W (popular/cheap). |
| **API Reference** | Detailed HTTP/WebSocket specs. | OpenAPI spec + WebSocket JSON examples. | **Parity.** Our `api_reference.md` is strong. |
| **Advanced Features** | IPMI, ATX Control, Mass Storage. | Focus on AI/VLM. | **Differentiation.** We sell "Intelligence", they sell "Control". Highlight VLM features more. |

## 3. Honest Report Card

**Overall Grade: B+**

**Strengths:**
*   **Modernity:** Our architecture docs (Mermaid) are better than PiKVM's text walls.
*   **AI Focus:** We document the *reasoning* loop, which no competitor has.
*   **Manifest:** The `manifest.md` is a great audit tool for security-conscious users.

**Weaknesses:**
*   **Abstraction:** Too much focus on "Architecture" and not enough on "Physical Reality".
    *   *Missing:* "Buy this exact $15 HDMI dongle from Amazon."
    *   *Missing:* "Print this 3D case."
*   **Validation:** We claim "2026 standard", but 2026 standards imply interactive docs or AI assistants *in* the docs.

## 4. Immediate Action Items

1.  **Hardware BOM:** Create a `docs/HARDWARE_BOM.md` with links to specific tested capture cards.
2.  **Visuals:** Add screenshots to `USER_GUIDE.md`.
3.  **Flipper Zero Integration:** Add a section to `ARCHITECTURE.md` about the potential "Phone + Flipper" mode.
