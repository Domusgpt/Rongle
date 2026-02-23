from abc import ABC, abstractmethod
import numpy as np
from dataclasses import dataclass

@dataclass
class Frame:
    image: np.ndarray
    timestamp: float
    width: int
    height: int

class VideoSource(ABC):
    @abstractmethod
    def open(self): pass
    @abstractmethod
    def grab(self) -> Frame: pass
    @abstractmethod
    def close(self): pass

class HIDActuator(ABC):
    @abstractmethod
    def open(self): pass
    @abstractmethod
    def send_key(self, scancode: int, modifier: int = 0): pass
    @abstractmethod
    def send_mouse_move(self, dx: int, dy: int): pass
    @abstractmethod
    def send_mouse_click(self, button: int = 1): pass
    @abstractmethod
    def release_all(self): pass
    @abstractmethod
    def close(self): pass
