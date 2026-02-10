"""
Keyboard Listener — Listens for hotkeys on stdin to toggle runtime flags.
"""

import sys
import termios
import tty
import select
import threading
import logging

logger = logging.getLogger(__name__)

class KeyMonitor:
    def __init__(self, callback, trigger_key='('):
        self.callback = callback
        self.trigger_key = trigger_key
        self.running = False
        self._thread = None

    def start(self):
        self.running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False

    def _monitor_loop(self):
        # Only works if we have a TTY
        if not sys.stdin.isatty():
            logger.info("Stdin is not a TTY — Keyboard Monitor disabled")
            return

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            while self.running:
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    ch = sys.stdin.read(1)
                    if ch == self.trigger_key:
                        self.callback()
        except Exception as e:
            logger.error(f"Keyboard monitor error: {e}")
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
