"""
DuckyScriptParser — Translates Ducky Script commands into raw HID report bytes.

Supports standard Ducky Script v1 commands:
  STRING, DELAY, GUI/WINDOWS, ENTER, TAB, ESCAPE, arrow keys,
  modifier combos (CTRL, ALT, SHIFT), MOUSE_MOVE, MOUSE_CLICK, etc.

Mouse movements are delegated to the Humanizer for Bezier-curve interpolation.
"""

from __future__ import annotations

import re
import struct
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Iterator

from .humanizer import Humanizer, BezierPoint


# ---------------------------------------------------------------------------
# USB HID Keyboard Scan Codes (USB HID Usage Tables §10)
# ---------------------------------------------------------------------------
class Modifier(IntEnum):
    NONE = 0x00
    LEFT_CTRL = 0x01
    LEFT_SHIFT = 0x02
    LEFT_ALT = 0x04
    LEFT_GUI = 0x08
    RIGHT_CTRL = 0x10
    RIGHT_SHIFT = 0x20
    RIGHT_ALT = 0x40
    RIGHT_GUI = 0x80


# fmt: off
_SCANCODE_MAP: dict[str, int] = {
    "a": 0x04, "b": 0x05, "c": 0x06, "d": 0x07, "e": 0x08, "f": 0x09,
    "g": 0x0A, "h": 0x0B, "i": 0x0C, "j": 0x0D, "k": 0x0E, "l": 0x0F,
    "m": 0x10, "n": 0x11, "o": 0x12, "p": 0x13, "q": 0x14, "r": 0x15,
    "s": 0x16, "t": 0x17, "u": 0x18, "v": 0x19, "w": 0x1A, "x": 0x1B,
    "y": 0x1C, "z": 0x1D,
    "1": 0x1E, "2": 0x1F, "3": 0x20, "4": 0x21, "5": 0x22, "6": 0x23,
    "7": 0x24, "8": 0x25, "9": 0x26, "0": 0x27,
    "\n": 0x28, "\t": 0x2B, " ": 0x2C,
    "-": 0x2D, "=": 0x2E, "[": 0x2F, "]": 0x30, "\\": 0x31,
    ";": 0x33, "'": 0x34, "`": 0x35, ",": 0x36, ".": 0x37, "/": 0x38,
}

_SHIFTED_MAP: dict[str, tuple[int, int]] = {
    "!": (Modifier.LEFT_SHIFT, 0x1E), "@": (Modifier.LEFT_SHIFT, 0x1F),
    "#": (Modifier.LEFT_SHIFT, 0x20), "$": (Modifier.LEFT_SHIFT, 0x21),
    "%": (Modifier.LEFT_SHIFT, 0x22), "^": (Modifier.LEFT_SHIFT, 0x23),
    "&": (Modifier.LEFT_SHIFT, 0x24), "*": (Modifier.LEFT_SHIFT, 0x25),
    "(": (Modifier.LEFT_SHIFT, 0x26), ")": (Modifier.LEFT_SHIFT, 0x27),
    "_": (Modifier.LEFT_SHIFT, 0x2D), "+": (Modifier.LEFT_SHIFT, 0x2E),
    "{": (Modifier.LEFT_SHIFT, 0x2F), "}": (Modifier.LEFT_SHIFT, 0x30),
    "|": (Modifier.LEFT_SHIFT, 0x31), ":": (Modifier.LEFT_SHIFT, 0x33),
    '"': (Modifier.LEFT_SHIFT, 0x34), "~": (Modifier.LEFT_SHIFT, 0x35),
    "<": (Modifier.LEFT_SHIFT, 0x36), ">": (Modifier.LEFT_SHIFT, 0x37),
    "?": (Modifier.LEFT_SHIFT, 0x38),
}

_SPECIAL_KEYS: dict[str, int] = {
    "ENTER": 0x28, "RETURN": 0x28, "ESCAPE": 0x29, "ESC": 0x29,
    "BACKSPACE": 0x2A, "TAB": 0x2B, "SPACE": 0x2C, "CAPSLOCK": 0x39,
    "F1": 0x3A, "F2": 0x3B, "F3": 0x3C, "F4": 0x3D, "F5": 0x3E,
    "F6": 0x3F, "F7": 0x40, "F8": 0x41, "F9": 0x42, "F10": 0x43,
    "F11": 0x44, "F12": 0x45,
    "PRINTSCREEN": 0x46, "SCROLLLOCK": 0x47, "PAUSE": 0x48,
    "INSERT": 0x49, "HOME": 0x4A, "PAGEUP": 0x4B, "DELETE": 0x4C,
    "END": 0x4D, "PAGEDOWN": 0x4E,
    "RIGHT": 0x4F, "RIGHTARROW": 0x4F,
    "LEFT": 0x50, "LEFTARROW": 0x50,
    "DOWN": 0x51, "DOWNARROW": 0x51,
    "UP": 0x52, "UPARROW": 0x52,
    "NUMLOCK": 0x53, "APP": 0x65, "MENU": 0x65,
}

_MODIFIER_ALIASES: dict[str, int] = {
    "CTRL": Modifier.LEFT_CTRL, "CONTROL": Modifier.LEFT_CTRL,
    "SHIFT": Modifier.LEFT_SHIFT, "ALT": Modifier.LEFT_ALT,
    "GUI": Modifier.LEFT_GUI, "WINDOWS": Modifier.LEFT_GUI,
    "COMMAND": Modifier.LEFT_GUI, "META": Modifier.LEFT_GUI,
}
# fmt: on


# ---------------------------------------------------------------------------
# HID Report containers
# ---------------------------------------------------------------------------
@dataclass
class KeyboardReport:
    """8-byte USB HID keyboard report."""
    modifier: int = 0
    reserved: int = 0
    keys: list[int] = field(default_factory=lambda: [0, 0, 0, 0, 0, 0])

    def to_bytes(self) -> bytes:
        return struct.pack("BBBBBBBBf", self.modifier, self.reserved,
                           *self.keys[:6])[:8]

    def pack(self) -> bytes:
        """Pack into an 8-byte HID keyboard report."""
        return struct.pack(
            "BB6B",
            self.modifier & 0xFF,
            self.reserved,
            *(self.keys[:6] + [0] * (6 - len(self.keys)))
        )

    @staticmethod
    def release() -> bytes:
        """All-zeros release report."""
        return b"\x00" * 8


@dataclass
class MouseReport:
    """4-byte USB HID relative mouse report.

    Layout: [buttons, dx (int8), dy (int8), wheel (int8)]
    """
    buttons: int = 0
    dx: int = 0
    dy: int = 0
    wheel: int = 0

    def pack(self) -> bytes:
        return struct.pack("Bbbb", self.buttons, self.dx, self.dy, self.wheel)

    @staticmethod
    def release() -> bytes:
        return b"\x00\x00\x00\x00"


# ---------------------------------------------------------------------------
# Parsed command representation
# ---------------------------------------------------------------------------
@dataclass
class ParsedCommand:
    """Intermediate representation of a single Ducky Script line."""
    kind: str                       # "keyboard" | "mouse_move" | "mouse_click" | "delay" | "string"
    keyboard_report: KeyboardReport | None = None
    mouse_points: list[BezierPoint] | None = None
    mouse_button: int = 0           # 0=none, 1=left, 2=right, 4=middle
    delay_ms: int = 0
    string_chars: str = ""
    raw_line: str = ""              # original script line for audit


# ---------------------------------------------------------------------------
# DuckyScriptParser
# ---------------------------------------------------------------------------
class DuckyScriptParser:
    """
    Translates Ducky Script text into a sequence of ``ParsedCommand`` objects.

    Mouse movements are converted to humanized Bezier-curve waypoints via the
    ``Humanizer`` so that the cursor path mimics human hand jitter.

    Usage::

        parser = DuckyScriptParser(screen_w=1920, screen_h=1080)
        for cmd in parser.parse(script_text):
            ...  # feed to HIDGadget
    """

    # Regex for MOUSE_MOVE x y
    _RE_MOUSE_MOVE = re.compile(r"^MOUSE_MOVE\s+(-?\d+)\s+(-?\d+)$", re.IGNORECASE)
    _RE_MOUSE_CLICK = re.compile(r"^MOUSE_CLICK\s*(LEFT|RIGHT|MIDDLE)?$", re.IGNORECASE)
    _RE_DELAY = re.compile(r"^DELAY\s+(\d+)$", re.IGNORECASE)
    _RE_STRING = re.compile(r"^STRING\s(.+)$", re.IGNORECASE)
    _RE_STRINGLN = re.compile(r"^STRINGLN\s(.+)$", re.IGNORECASE)
    _RE_REPEAT = re.compile(r"^REPEAT\s+(\d+)$", re.IGNORECASE)
    _RE_REM = re.compile(r"^REM\s", re.IGNORECASE)

    def __init__(
        self,
        screen_w: int = 1920,
        screen_h: int = 1080,
        humanizer: Humanizer | None = None,
        default_inter_key_ms: int = 12,
    ) -> None:
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.humanizer = humanizer or Humanizer()
        self.default_inter_key_ms = default_inter_key_ms

        # Current absolute cursor position (for relative delta computation)
        self._cursor_x: float = screen_w / 2
        self._cursor_y: float = screen_h / 2

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def parse(self, script: str) -> list[ParsedCommand]:
        """Parse a full Ducky Script and return ordered commands."""
        commands: list[ParsedCommand] = []
        lines = script.strip().splitlines()

        for line in lines:
            line = line.strip()
            if not line or self._RE_REM.match(line):
                continue

            # REPEAT — duplicate last command N times
            m = self._RE_REPEAT.match(line)
            if m and commands:
                count = int(m.group(1))
                last = commands[-1]
                for _ in range(count):
                    commands.append(last)
                continue

            cmd = self._parse_line(line)
            if cmd is not None:
                commands.append(cmd)

        return commands

    def parse_iter(self, script: str) -> Iterator[ParsedCommand]:
        """Lazily yield commands (useful for streaming execution)."""
        yield from self.parse(script)

    # ------------------------------------------------------------------
    # Character-level helpers
    # ------------------------------------------------------------------
    def char_to_report(self, ch: str) -> KeyboardReport:
        """Convert a single character to a KeyboardReport."""
        if ch in _SHIFTED_MAP:
            mod, code = _SHIFTED_MAP[ch]
            return KeyboardReport(modifier=mod, keys=[code])

        lower = ch.lower()
        code = _SCANCODE_MAP.get(lower, 0)
        mod = Modifier.LEFT_SHIFT if ch.isupper() and ch.isalpha() else Modifier.NONE
        return KeyboardReport(modifier=mod, keys=[code])

    def string_to_reports(self, text: str) -> list[KeyboardReport]:
        """Convert a string into a sequence of keyboard reports."""
        return [self.char_to_report(ch) for ch in text]

    # ------------------------------------------------------------------
    # Internal line parser
    # ------------------------------------------------------------------
    def _parse_line(self, line: str) -> ParsedCommand | None:
        # DELAY
        m = self._RE_DELAY.match(line)
        if m:
            return ParsedCommand(kind="delay", delay_ms=int(m.group(1)), raw_line=line)

        # STRING
        m = self._RE_STRING.match(line)
        if m:
            return ParsedCommand(kind="string", string_chars=m.group(1), raw_line=line)

        # STRINGLN (STRING + ENTER)
        m = self._RE_STRINGLN.match(line)
        if m:
            return ParsedCommand(
                kind="string", string_chars=m.group(1) + "\n", raw_line=line
            )

        # MOUSE_MOVE x y — absolute target coordinates
        m = self._RE_MOUSE_MOVE.match(line)
        if m:
            target_x = int(m.group(1))
            target_y = int(m.group(2))
            points = self.humanizer.bezier_path(
                self._cursor_x, self._cursor_y,
                float(target_x), float(target_y),
            )
            self._cursor_x = float(target_x)
            self._cursor_y = float(target_y)
            return ParsedCommand(kind="mouse_move", mouse_points=points, raw_line=line)

        # MOUSE_CLICK
        m = self._RE_MOUSE_CLICK.match(line)
        if m:
            btn_name = (m.group(1) or "LEFT").upper()
            btn_code = {"LEFT": 1, "RIGHT": 2, "MIDDLE": 4}.get(btn_name, 1)
            return ParsedCommand(kind="mouse_click", mouse_button=btn_code, raw_line=line)

        # Modifier combos: CTRL ALT DELETE, GUI r, etc.
        return self._parse_combo(line)

    def _parse_combo(self, line: str) -> ParsedCommand | None:
        """Parse modifier+key combos like ``CTRL ALT DELETE`` or ``GUI r``."""
        tokens = line.split()
        modifier = Modifier.NONE
        keycode = 0

        for token in tokens:
            upper = token.upper()
            if upper in _MODIFIER_ALIASES:
                modifier |= _MODIFIER_ALIASES[upper]
            elif upper in _SPECIAL_KEYS:
                keycode = _SPECIAL_KEYS[upper]
            elif len(token) == 1:
                lower = token.lower()
                keycode = _SCANCODE_MAP.get(lower, 0)
                if token.isupper() and token.isalpha():
                    modifier |= Modifier.LEFT_SHIFT
            else:
                # Unknown token — skip gracefully
                continue

        if keycode == 0 and modifier == Modifier.NONE:
            return None

        report = KeyboardReport(modifier=modifier, keys=[keycode])
        return ParsedCommand(kind="keyboard", keyboard_report=report, raw_line=line)
