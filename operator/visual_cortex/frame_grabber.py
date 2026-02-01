"""
FrameGrabber — Captures frames from the HDMI-to-CSI bridge at /dev/video0.

Uses Video4Linux2 (v4l2) via OpenCV to read from the capture device.
Provides both single-shot capture and continuous streaming modes.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class CapturedFrame:
    """A single captured frame with metadata."""
    image: np.ndarray           # BGR image (H, W, 3)
    timestamp: float            # time.time() of capture
    sequence: int               # monotonic frame counter
    sha256: str                 # hex digest of raw frame bytes

    @property
    def height(self) -> int:
        return self.image.shape[0]

    @property
    def width(self) -> int:
        return self.image.shape[1]

    def to_jpeg(self, quality: int = 85) -> bytes:
        """Encode frame as JPEG bytes."""
        ok, buf = cv2.imencode(".jpg", self.image, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if not ok:
            raise RuntimeError("JPEG encoding failed")
        return buf.tobytes()

    def to_gray(self) -> np.ndarray:
        """Return grayscale version of the frame."""
        return cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY)


class FrameGrabber:
    """
    Continuous frame capture from a V4L2 device.

    Parameters
    ----------
    device : str | int
        V4L2 device path (e.g., ``/dev/video0``) or index.
    width : int
        Capture width in pixels.
    height : int
        Capture height in pixels.
    fps : int
        Desired capture frame rate.
    """

    def __init__(
        self,
        device: str | int = "/dev/video0",
        width: int = 1920,
        height: int = 1080,
        fps: int = 30,
    ) -> None:
        self.device = device
        self.width = width
        self.height = height
        self.fps = fps

        self._cap: cv2.VideoCapture | None = None
        self._lock = threading.Lock()
        self._latest_frame: CapturedFrame | None = None
        self._seq = 0
        self._running = False
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def open(self) -> None:
        """Open the capture device."""
        self._cap = cv2.VideoCapture(self.device, cv2.CAP_V4L2)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open video device: {self.device}")

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._cap.set(cv2.CAP_PROP_FPS, self.fps)

        actual_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        logger.info(
            "FrameGrabber opened %s @ %dx%d",
            self.device, actual_w, actual_h,
        )

    def close(self) -> None:
        """Release the capture device."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=3.0)
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def __enter__(self) -> FrameGrabber:
        self.open()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Single-shot capture
    # ------------------------------------------------------------------
    def grab(self) -> CapturedFrame:
        """Capture and return a single frame (blocking)."""
        if self._cap is None or not self._cap.isOpened():
            raise RuntimeError("FrameGrabber not opened")

        ret, frame = self._cap.read()
        if not ret or frame is None:
            raise RuntimeError("Frame capture failed — check HDMI signal")

        self._seq += 1
        ts = time.time()
        frame_hash = hashlib.sha256(frame.tobytes()).hexdigest()

        return CapturedFrame(
            image=frame,
            timestamp=ts,
            sequence=self._seq,
            sha256=frame_hash,
        )

    # ------------------------------------------------------------------
    # Continuous capture (background thread)
    # ------------------------------------------------------------------
    def start_streaming(self) -> None:
        """Start capturing frames in a background thread."""
        if self._cap is None:
            self.open()
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def get_latest(self) -> CapturedFrame | None:
        """Return the most recently captured frame (thread-safe)."""
        with self._lock:
            return self._latest_frame

    def _capture_loop(self) -> None:
        interval = 1.0 / self.fps
        while self._running:
            try:
                frame = self.grab()
                with self._lock:
                    self._latest_frame = frame
            except RuntimeError as exc:
                logger.warning("Frame grab error: %s", exc)
            time.sleep(interval)
