import time
import numpy as np
from .base import VideoSource, HIDActuator, Frame

class DesktopVideoSource(VideoSource):
    def __init__(self, width=1920, height=1080):
        self.width = width
        self.height = height

    def open(self):
        try:
            import mss
            self.sct = mss.mss()
        except ImportError:
            print("Warning: mss not installed, simulation will use noise")
            self.sct = None

    def grab(self) -> Frame:
        if self.sct:
            img = np.array(self.sct.grab(self.sct.monitors[1]))
            # Convert BGRA to BGR
            img = img[:, :, :3]
            return Frame(img, time.time(), img.shape[1], img.shape[0])
        else:
            return Frame(np.random.randint(0, 255, (self.height, self.width, 3), dtype=np.uint8), time.time(), self.width, self.height)

    def close(self): pass

class DesktopHIDActuator(HIDActuator):
    def open(self):
        try:
            import pyautogui
            self.pg = pyautogui
            self.pg.FAILSAFE = False
        except ImportError:
            print("Warning: pyautogui not installed, HID simulation will log only")
            self.pg = None

    def send_key(self, scancode: int, modifier: int = 0):
        # Simplification: mapping scancodes back to keys would be complex
        # In desktop mode, we might just want to use higher-level API or a mapping
        print(f"[SIM] Send Key: scancode={scancode}, mod={modifier}")
        if self.pg:
            # Placeholder for scancode to key name mapping
            pass

    def send_mouse_move(self, dx: int, dy: int):
        if self.pg:
            self.pg.moveRel(dx, dy)
        else:
            print(f"[SIM] Mouse Move: {dx}, {dy}")

    def send_mouse_click(self, button: int = 1):
        if self.pg:
            btn = 'left' if button == 1 else 'right'
            self.pg.click(button=btn)
        else:
            print(f"[SIM] Mouse Click: button={button}")

    def release_all(self): pass
    def close(self): pass
