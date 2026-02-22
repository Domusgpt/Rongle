import time
import numpy as np
import logging
from .base import VideoSource, HIDActuator, Frame

logger = logging.getLogger(__name__)

class DesktopVideoSource(VideoSource):
    def __init__(self, width=1920, height=1080):
        self.width = width
        self.height = height
        self.sct = None

    def open(self):
        try:
            import mss
            self.sct = mss.mss()
            logger.info("DesktopVideoSource: mss initialized")
        except ImportError:
            logger.warning("mss not installed, simulation will use noise")
            self.sct = None

    def grab(self) -> Frame:
        if self.sct:
            # Grab the primary monitor
            monitor = self.sct.monitors[1]
            sct_img = self.sct.grab(monitor)
            # Convert to numpy array and from BGRA to BGR
            img = np.array(sct_img)[:, :, :3]
            # Resize if needed to match requested resolution
            import cv2
            if img.shape[1] != self.width or img.shape[0] != self.height:
                img = cv2.resize(img, (self.width, self.height))
            return Frame(img, time.time(), self.width, self.height)
        else:
            # Fallback noise
            img = np.random.randint(0, 255, (self.height, self.width, 3), dtype=np.uint8)
            return Frame(img, time.time(), self.width, self.height)

    def close(self):
        if self.sct:
            self.sct.close()

class DesktopHIDActuator(HIDActuator):
    def __init__(self):
        self.pg = None

    def open(self):
        try:
            import pyautogui
            self.pg = pyautogui
            self.pg.FAILSAFE = False
            logger.info("DesktopHIDActuator: pyautogui initialized")
        except ImportError:
            logger.warning("pyautogui not installed, HID simulation will log only")
            self.pg = None

    def send_key(self, scancode: int, modifier: int = 0):
        # We don't have a direct scancode -> pyautogui mapping here easily
        # For simulation, we'll log the scancode
        logger.info(f"[SIM] Key Press: scancode={scancode}, mod={modifier}")
        if self.pg:
            # Special case for common keys if we want more realism
            if scancode == 0x28: # ENTER
                self.pg.press('enter')
            elif scancode == 0x29: # ESC
                self.pg.press('esc')
            elif scancode == 0x2B: # TAB
                self.pg.press('tab')

    def send_mouse_move(self, dx: int, dy: int):
        if self.pg:
            self.pg.moveRel(dx, dy, duration=0.1)
        else:
            logger.info(f"[SIM] Mouse Move: ({dx}, {dy})")

    def send_mouse_click(self, button: int = 1):
        if self.pg:
            btn = 'left' if button == 1 else 'right'
            self.pg.click(button=btn)
        else:
            logger.info(f"[SIM] Mouse Click: button={button}")

    def release_all(self):
        logger.info("[SIM] Release All Keys/Buttons")

    def close(self): pass
