import cv2
import time
import os
import struct
from .base import VideoSource, HIDActuator, Frame
import numpy as np

class PiVideoSource(VideoSource):
    def __init__(self, device="/dev/video0", width=1920, height=1080):
        self.device = device
        self.width = width
        self.height = height
        self.cap = None

    def open(self):
        self.cap = cv2.VideoCapture(self.device, cv2.CAP_V4L2)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        if not self.cap.isOpened():
            raise RuntimeError(f"Could not open {self.device}")

    def grab(self) -> Frame:
        ret, image = self.cap.read()
        if not ret:
            raise RuntimeError("Frame capture failed")
        return Frame(image, time.time(), self.width, self.height)

    def close(self):
        if self.cap:
            self.cap.release()

class PiHIDActuator(HIDActuator):
    def __init__(self, kbd_dev="/dev/hidg0", mouse_dev="/dev/hidg1"):
        self.kbd_dev = kbd_dev
        self.mouse_dev = mouse_dev
        self.kbd_fd = None
        self.mouse_fd = None

    def open(self):
        self.kbd_fd = os.open(self.kbd_dev, os.O_WRONLY)
        self.mouse_fd = os.open(self.mouse_dev, os.O_WRONLY)

    def send_key(self, scancode: int, modifier: int = 0):
        report = struct.pack("BB6B", modifier, 0, scancode, 0, 0, 0, 0, 0)
        os.write(self.kbd_fd, report)
        time.sleep(0.01)
        os.write(self.kbd_fd, b"\x00"*8)

    def send_mouse_move(self, dx: int, dy: int):
        report = struct.pack("Bbbb", 0, dx, dy, 0)
        os.write(self.mouse_fd, report)

    def send_mouse_click(self, button: int = 1):
        press = struct.pack("Bbbb", button, 0, 0, 0)
        release = struct.pack("Bbbb", 0, 0, 0, 0)
        os.write(self.mouse_fd, press)
        time.sleep(0.05)
        os.write(self.mouse_fd, release)

    def release_all(self):
        os.write(self.kbd_fd, b"\x00"*8)
        os.write(self.mouse_fd, b"\x00"*4)

    def close(self):
        if self.kbd_fd: os.close(self.kbd_fd)
        if self.mouse_fd: os.close(self.mouse_fd)
