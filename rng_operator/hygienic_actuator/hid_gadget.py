"""
HIDGadget — Low-level interface to the Linux USB OTG Composite HID gadget.

Writes raw HID reports to /dev/hidgX device files to inject keyboard and
mouse events into the host machine.

On the Raspberry Pi Zero 2 W this requires:
  - ``dwc2`` overlay enabled in /boot/config.txt
  - ``libcomposite`` kernel module loaded
  - ConfigFS gadget configured (keyboard @ /dev/hidg0, mouse @ /dev/hidg1)
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from .ducky_parser import KeyboardReport, MouseReport, ParsedCommand
from .humanizer import BezierPoint

logger = logging.getLogger(__name__)


class HIDGadget:
    """
    Writes HID reports to the Linux USB gadget device files.

    Parameters
    ----------
    keyboard_dev : str
        Path to the HID keyboard device (default ``/dev/hidg0``).
    mouse_dev : str
        Path to the HID mouse device (default ``/dev/hidg1``).
    dry_run : bool
        If True, log reports without writing to device files. Useful for
        development on non-Pi hardware.
    """

    def __init__(
        self,
        keyboard_dev: str = "/dev/hidg0",
        mouse_dev: str = "/dev/hidg1",
        dry_run: bool = False,
    ) -> None:
        self.keyboard_dev = keyboard_dev
        self.mouse_dev = mouse_dev
        self.dry_run = dry_run
        self._kbd_fd: int | None = None
        self._mouse_fd: int | None = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------
    def open(self) -> None:
        """Open device file descriptors."""
        if self.dry_run:
            logger.info("HIDGadget running in dry-run mode")
            return
        self._kbd_fd = os.open(self.keyboard_dev, os.O_WRONLY)
        self._mouse_fd = os.open(self.mouse_dev, os.O_WRONLY)
        logger.info("Opened HID devices: kbd=%s mouse=%s", self.keyboard_dev, self.mouse_dev)

    def close(self) -> None:
        """Close device file descriptors."""
        for fd in (self._kbd_fd, self._mouse_fd):
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
        self._kbd_fd = None
        self._mouse_fd = None

    def __enter__(self) -> HIDGadget:
        self.open()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Low-level writers
    # ------------------------------------------------------------------
    def _write_kbd(self, data: bytes) -> None:
        if self.dry_run:
            logger.debug("KBD >> %s", data.hex())
            return
        if self._kbd_fd is not None:
            os.write(self._kbd_fd, data)

    def _write_mouse(self, data: bytes) -> None:
        if self.dry_run:
            logger.debug("MOUSE >> %s", data.hex())
            return
        if self._mouse_fd is not None:
            os.write(self._mouse_fd, data)

    # ------------------------------------------------------------------
    # High-level command execution
    # ------------------------------------------------------------------
    def execute(self, cmd: ParsedCommand) -> None:
        """Execute a single ParsedCommand by writing HID reports."""
        if cmd.kind == "keyboard":
            self.send_key(cmd.keyboard_report)
        elif cmd.kind == "string":
            self.send_string(cmd.string_chars)
        elif cmd.kind == "mouse_move":
            self.send_mouse_path(cmd.mouse_points or [])
        elif cmd.kind == "mouse_click":
            self.send_mouse_click(cmd.mouse_button)
        elif cmd.kind == "delay":
            time.sleep(cmd.delay_ms / 1000.0)

    def send_key(self, report: KeyboardReport | None) -> None:
        """Send a single keypress (press + release)."""
        if report is None:
            return
        self._write_kbd(report.pack())
        time.sleep(0.008)  # 8ms between press and release
        self._write_kbd(KeyboardReport.release())
        time.sleep(0.004)

    def send_string(self, text: str, inter_key_ms: int = 12) -> None:
        """Type a string character-by-character with inter-key delay."""
        from .ducky_parser import DuckyScriptParser
        # Use a temporary parser instance for char conversion
        parser = DuckyScriptParser.__new__(DuckyScriptParser)
        for ch in text:
            report = parser.char_to_report(ch)
            self.send_key(report)
            time.sleep(inter_key_ms / 1000.0)

    def send_mouse_path(self, points: list[BezierPoint]) -> None:
        """Send a sequence of relative mouse movement reports."""
        for pt in points:
            report = MouseReport(buttons=0, dx=pt.dx, dy=pt.dy, wheel=0)
            self._write_mouse(report.pack())
            time.sleep(pt.dwell_ms / 1000.0)

    def send_mouse_click(self, button: int = 1) -> None:
        """Click a mouse button (press + release)."""
        press = MouseReport(buttons=button, dx=0, dy=0, wheel=0)
        self._write_mouse(press.pack())
        time.sleep(0.05)
        self._write_mouse(MouseReport.release())
        time.sleep(0.02)

    def release_all(self) -> None:
        """Send release reports for both keyboard and mouse (safety)."""
        self._write_kbd(KeyboardReport.release())
        self._write_mouse(MouseReport.release())
