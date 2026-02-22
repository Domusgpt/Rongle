# User Experience (UX) Guidelines

Rongle aims to be the gold standard for "Hardware-Isolated Agentic Operators". To achieve this, we adhere to strict UX principles that prioritize transparency, safety, and professional aesthetics.

## 1. The "Glass Box" Philosophy
The user must always know *what* the agent is doing and *why*.
*   **Transparent State:** The agent's current state (`LOOKING`, `PLANNING`, `ACTING`) must be visible at all times.
*   **Visible Reasoning:** The "Thought Bubble" (Action Log) should display the VLM's reasoning, not just the final command.
*   **Confidence Scores:** Show confidence percentages for vision detections. If confidence is low, highlight it in yellow/red.

## 2. Safety by Default
The system is powerful and dangerous. The UI must reflect this.
*   **Red E-Stop:** The Emergency Stop button must be the most prominent element on the screen. It should be "always on top".
*   **Safe Zones:** Visual overlays (red semi-transparent boxes) should clearly mark restricted areas on the Live View.
*   **Confirmation:** High-risk actions (e.g., "Format Drive") should trigger a "Human-in-the-loop" confirmation prompt if configured.

## 3. Visual Language
We use a "Cyber-Industrial" aesthetic: clean, dark mode, high contrast.
*   **Colors:**
    *   Background: Dark Slate (`#0f172a`)
    *   Accent: Terminal Green (`#22c55e`) for success/active.
    *   Warning: Amber (`#f59e0b`) for low confidence/retries.
    *   Danger: Red (`#ef4444`) for E-Stop and Blocked actions.
*   **Typography:** Monospace fonts for logs and code. Sans-serif for UI labels.

## 4. Feedback Loops
*   **Latency:** The "Live View" must show the latency (ping) to the backend.
*   **Toast Notifications:** Use transient toasts for non-critical updates ("Settings Saved", "Screenshot Captured").
*   **Audio Cues:** (Future) Subtle clicks for keystrokes, buzzer for errors.

## 5. Mobile First
The primary controller is a smartphone.
*   **Touch Targets:** Buttons must be at least 44x44px.
*   **Gestures:** Swipe to dismiss logs.
*   **Orientation:** The UI must adapt to Portrait (Logs + Controls) and Landscape (Full Screen Video).
