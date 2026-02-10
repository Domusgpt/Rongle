# Example: Basic Terminal Automation

This example demonstrates how to open a terminal, navigate to a directory, and list files using Ducky Script.

## Script

```duckyscript
REM Open Spotlight (MacOS) or Start Menu (Windows/Linux)
GUI space
DELAY 500

REM Search for Terminal
STRING Terminal
DELAY 500
ENTER
DELAY 1000

REM Navigate to project directory
STRING cd ~/projects/rongle
ENTER
DELAY 200

REM List files with details
STRING ls -la
ENTER
```

## Logic Breakdown

1.  **GUI space**: Triggers the system launcher. This is cross-platform usually, but might need `GUI` (Windows Key) on Windows.
2.  **DELAY**: Crucial for allowing the UI animation to complete. Using `1000` (1 second) is safe for most systems.
3.  **STRING**: Types the characters.
4.  **ENTER**: Executes the command.

## Verification Strategy

To verify this script succeeded, the `VisualCortex` should look for:
1.  A window resembling a terminal (black background, monospaced text).
2.  The text `projects/rongle` in the prompt.
3.  A file listing output.

---

# Example: Browser Navigation

Opens a browser and goes to a specific URL.

```duckyscript
GUI r
DELAY 500
STRING https://www.google.com
ENTER
DELAY 2000
```

## Notes
- `GUI r` is Windows-specific (Run dialog).
- On macOS, replace with `GUI space` -> `Safari` -> `ENTER` -> `GUI l` (Open Location).
