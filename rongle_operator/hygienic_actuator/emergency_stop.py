"""
EmergencyStop — GPIO-based hardware kill switch.

When the physical safety button is released (normally-closed), all HID
output is immediately halted and devices are sent release reports.

Works on Raspberry Pi GPIO via ``gpiod`` (libgpiod) for modern kernel
compatibility.  Falls back to a software-only mode on non-Pi hardware.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

logger = logging.getLogger(__name__)


class EmergencyStop:
    """
    Monitors a GPIO pin connected to a physical dead-man switch.

    The switch is wired as normally-closed (NC):
      - Button HELD   → GPIO reads LOW  → system ACTIVE
      - Button RELEASED → GPIO reads HIGH → EMERGENCY STOP

    Parameters
    ----------
    gpio_chip : str
        gpiod chip device (default ``/dev/gpiochip0``).
    gpio_line : int
        GPIO line number for the safety button (default 17 = physical pin 11).
    on_stop : callable
        Callback invoked when emergency stop triggers.
    poll_interval_s : float
        How frequently to poll the GPIO state.
    software_only : bool
        If True, skip GPIO and rely only on ``trigger()`` calls.
    """

    def __init__(
        self,
        gpio_chip: str = "/dev/gpiochip0",
        gpio_line: int = 17,
        on_stop: Callable[[], None] | None = None,
        poll_interval_s: float = 0.01,
        software_only: bool = False,
    ) -> None:
        self.gpio_chip = gpio_chip
        self.gpio_line = gpio_line
        self.poll_interval_s = poll_interval_s
        self.software_only = software_only
        self._on_stop = on_stop
        self._stopped = threading.Event()
        self._thread: threading.Thread | None = None
        self._gpiod_line = None

    @property
    def is_stopped(self) -> bool:
        return self._stopped.is_set()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self) -> None:
        """Begin monitoring the dead-man switch in a background thread."""
        if self.software_only:
            logger.info("EmergencyStop running in software-only mode")
            return

        try:
            import gpiod  # type: ignore[import-untyped]

            chip = gpiod.Chip(self.gpio_chip)
            self._gpiod_line = chip.get_line(self.gpio_line)
            self._gpiod_line.request(
                consumer="emergency_stop",
                type=gpiod.LINE_REQ_DIR_IN,
                flags=gpiod.LINE_REQ_FLAG_BIAS_PULL_UP,
            )
            logger.info(
                "EmergencyStop monitoring GPIO %s line %d",
                self.gpio_chip, self.gpio_line,
            )
        except (ImportError, OSError) as exc:
            logger.warning("GPIO unavailable (%s), falling back to software-only", exc)
            self.software_only = True
            return

        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Shut down the monitoring thread."""
        self._stopped.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self._gpiod_line is not None:
            self._gpiod_line.release()

    def trigger(self) -> None:
        """Manually trigger emergency stop (software kill switch)."""
        if not self._stopped.is_set():
            logger.critical("EMERGENCY STOP triggered")
            self._stopped.set()
            if self._on_stop:
                self._on_stop()

    def reset(self) -> None:
        """Re-arm the system after an emergency stop (requires human action)."""
        logger.info("Emergency stop RESET — system re-armed")
        self._stopped.clear()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _poll_loop(self) -> None:
        """Poll GPIO at fixed interval; trigger stop when button released."""
        while not self._stopped.is_set():
            try:
                value = self._gpiod_line.get_value()
                # NC switch: HIGH = button released = STOP
                if value == 1:
                    self.trigger()
                    return
            except OSError as exc:
                logger.error("GPIO read error: %s", exc)
                self.trigger()
                return
            time.sleep(self.poll_interval_s)
