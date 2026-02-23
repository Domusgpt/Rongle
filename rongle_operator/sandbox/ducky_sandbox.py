"""
DuckySandbox: A Virtual Computer Environment for Agentic Ducky Script Testing.

This module simulates a computer desktop environment (Cursor, Windows, UI Elements)
and accepts raw HID reports or high-level Ducky Script commands to update its state.
It allows for rapid prototyping and evolution of agentic scripts without physical hardware.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import logging
import time

logger = logging.getLogger("ducky_sandbox")

@dataclass
class UIElement:
    id: str
    label: str
    x: int
    y: int
    width: int
    height: int
    visible: bool = True
    active: bool = False

    @property
    def center(self):
        return (self.x + self.width // 2, self.y + self.height // 2)

    def contains(self, x: int, y: int) -> bool:
        return self.x <= x <= self.x + self.width and self.y <= y <= self.y + self.height

@dataclass
class SandboxState:
    cursor_x: int = 0
    cursor_y: int = 0
    screen_width: int = 1920
    screen_height: int = 1080
    active_window: str = "Desktop"
    elements: List[UIElement] = field(default_factory=list)
    clipboard: str = ""
    typed_buffer: str = ""
    last_event: str = ""

class DuckySandbox:
    def __init__(self, width=1920, height=1080):
        self.state = SandboxState(screen_width=width, screen_height=height)
        self._setup_default_desktop()

    def _setup_default_desktop(self):
        """Initialize with some dummy elements."""
        self.state.elements = [
            UIElement("btn_start", "Start Menu", 0, 1040, 50, 40),
            UIElement("icon_browser", "Chrome", 50, 50, 60, 60),
            UIElement("icon_terminal", "Terminal", 50, 150, 60, 60),
            UIElement("window_browser", "Google Chrome", 200, 100, 800, 600, visible=False),
            UIElement("input_search", "Search Bar", 300, 200, 400, 30, visible=False)
        ]

    def render(self) -> str:
        """Return a text representation of the current state."""
        output = [
            f"--- Virtual Desktop ({self.state.screen_width}x{self.state.screen_height}) ---",
            f"Active Window: {self.state.active_window}",
            f"Cursor: ({self.state.cursor_x}, {self.state.cursor_y})",
            f"Clipboard: '{self.state.clipboard}'",
            f"Typed Buffer: '{self.state.typed_buffer}'",
            "Visible Elements:"
        ]
        for el in self.state.elements:
            if el.visible:
                status = " [HOVER]" if el.contains(self.state.cursor_x, self.state.cursor_y) else ""
                output.append(f"  - {el.label} at ({el.x},{el.y}) {el.width}x{el.height}{status}")
        return "\n".join(output)

    def receive_hid_mouse(self, dx: int, dy: int, buttons: int):
        """Simulate mouse movement and clicks."""
        self.state.cursor_x = max(0, min(self.state.screen_width, self.state.cursor_x + dx))
        self.state.cursor_y = max(0, min(self.state.screen_height, self.state.cursor_y + dy))

        if buttons & 1: # Left Click
            self._handle_click()

    def receive_hid_keyboard(self, key_code: int, modifiers: int):
        """Simulate keystrokes (simplified)."""
        # Mapping HID usage IDs to characters is complex, simplified here
        # This is where a real HID parser/mapper would go.
        # For simulation, we accept ASCII/String input directly usually.
        pass

    def execute_ducky_command(self, line: str):
        """Execute a high-level Ducky Script command directly."""
        parts = line.strip().split()
        if not parts: return

        cmd = parts[0].upper()

        if cmd == "MOUSE_MOVE":
            # Absolute move
            try:
                x, y = int(parts[1]), int(parts[2])
                self.state.cursor_x = x
                self.state.cursor_y = y
                self.state.last_event = f"Moved to ({x}, {y})"
            except ValueError: pass

        elif cmd == "MOUSE_CLICK":
            self._handle_click()
            self.state.last_event = "Clicked Left"

        elif cmd == "STRING":
            text = " ".join(parts[1:])
            self.state.typed_buffer += text
            self.state.last_event = f"Typed: '{text}'"
            # Update Active Element if Input
            self._handle_typing(text)

        elif cmd == "ENTER":
            self.state.typed_buffer += "\n"
            self._handle_enter()

        elif cmd == "DELAY":
            # Simulation doesn't need real sleep usually, but we can log it
            pass

    def _handle_click(self):
        clicked_element = None
        for el in self.state.elements:
            if el.visible and el.contains(self.state.cursor_x, self.state.cursor_y):
                clicked_element = el
                break

        if clicked_element:
            logger.info(f"Clicked on {clicked_element.label}")
            self._trigger_element_action(clicked_element)
        else:
            logger.info("Clicked on background")

    def _trigger_element_action(self, element: UIElement):
        """Logic for sandbox interactivity."""
        if element.id == "icon_browser":
            self.state.active_window = "Google Chrome"
            # Show browser window elements
            for el in self.state.elements:
                if el.id in ["window_browser", "input_search"]:
                    el.visible = True

        elif element.id == "icon_terminal":
            self.state.active_window = "Terminal"

        elif element.id == "input_search":
            element.active = True # Focus

    def _handle_typing(self, text: str):
        # Find focused element
        for el in self.state.elements:
            if el.active:
                # In a real sim, we'd update the element's text property
                pass

    def _handle_enter(self):
        # If searching in browser
        if self.state.active_window == "Google Chrome":
             # Simulate page load
             logger.info("Browser navigating...")
