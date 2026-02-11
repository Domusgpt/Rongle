# Evolutionary Sandbox 🏝️

The **Ducky Sandbox** is a virtual environment designed to evolve the capabilities of the Rongle Agent without requiring physical hardware. It simulates a desktop operating system, allowing the agent to "practice" and learn new automation strategies.

## Components

### 1. DuckySandbox (`rongle_operator/sandbox/ducky_sandbox.py`)
A state-machine that represents a computer. It maintains:
*   **Cursor Position**: (x, y)
*   **Window State**: Which window is active/visible.
*   **UI Elements**: Clickable buttons, icons, fields.
*   **Keyboard Buffer**: What has been typed.

### 2. Agentic Translator (`rongle_operator/sandbox/translator.py`)
An AI-powered bridge that translates human intent into Ducky Script.
*   **Input**: "Open Chrome and search for Dogs"
*   **Process**: LLM analyzes sandbox state -> generates optimized script.
*   **Output**:
    ```ducky
    MOUSE_MOVE 80 80
    MOUSE_CLICK LEFT
    DELAY 500
    STRING Dogs
    ENTER
    ```

## Usage

### Running Tests
The sandbox is verified via integration tests:

```bash
python3 tests/test_ducky_evolution.py
```

### Extending the Sandbox
To add new "software" to the sandbox, edit `ducky_sandbox.py` and add `UIElement` definitions to `_setup_default_desktop()` and handle their interactions in `_trigger_element_action()`.

## Future Vision
We plan to use this sandbox for **Reinforcement Learning (RL)**:
1.  Agent is given a goal.
2.  Agent generates a script.
3.  Sandbox returns a reward based on state change.
4.  Agent optimizes its Ducky Script generation policy.

---
[Back to Documentation Index](../../docs/INDEX.md)
