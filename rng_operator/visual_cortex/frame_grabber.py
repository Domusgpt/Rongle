"""
FrameGrabber — Captures frames from the HDMI-to-CSI bridge at /dev/video0 OR WebRTC source.

Uses Video4Linux2 (v4l2) via OpenCV to read from the capture device.
Provides both single-shot capture and continuous streaming modes.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Optional

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
    Continuous frame capture from a V4L2 device or WebRTC receiver.

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
    receiver : WebRTCReceiver | None
        Optional WebRTC receiver source. If provided, 'device' is ignored.
    """

    def __init__(
        self,
        device: str | int = "/dev/video0",
        width: int = 1920,
        height: int = 1080,
        fps: int = 30,
        receiver: Any | None = None,
    ) -> None:
        self.device = device
        self.width = width
        self.height = height
        self.fps = fps
        self.receiver = receiver

        self._cap: cv2.VideoCapture | None = None
        self._lock = threading.Lock()
        self._latest_frame: CapturedFrame | None = None
        self._seq = 0
        self._running = False
        self._thread: threading.Thread | None = None

        # Async support
        self._loop: asyncio.AbstractEventLoop | None = None
        self._frame_event: asyncio.Event | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def open(self) -> None:
        """Open the capture device."""
        if self.receiver:
            logger.info("FrameGrabber using WebRTC receiver source")
            return

        # Check if device is a network URL (IP Webcam) or local device
        if isinstance(self.device, str) and (self.device.startswith("http") or self.device.startswith("rtsp")):
            logger.info("Opening network stream: %s", self.device)
            # FFMPEG backend is better for network streams
            self._cap = cv2.VideoCapture(self.device, cv2.CAP_FFMPEG)
        else:
            self._cap = cv2.VideoCapture(self.device, cv2.CAP_V4L2)

        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open video device: {self.device}")

        # Setting props might not work on streams, but we try
        try:
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self._cap.set(cv2.CAP_PROP_FPS, self.fps)
        except Exception:
            pass

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
        if self.receiver:
            # Sync grab from receiver (polling latest)
            img, ts, seq = self.receiver.get_latest_frame()
            if img is None:
                # If no frame yet, wait briefly? or raise?
                # For compatibility with polling loops, we might sleep and retry?
                # But grab() usually blocks.
                # Since receiver is async populated, we can't easily block here without loop.
                # Just raise or return None (but return type is CapturedFrame).
                # We'll rely on the caller handling exceptions or retrying.
                raise RuntimeError("No WebRTC frame available yet")

            # Use receiver's sequence or maintain our own? Receiver has one.
            # Hash
            frame_hash = hashlib.sha256(img.tobytes()).hexdigest()
            return CapturedFrame(image=img, timestamp=ts, sequence=seq, sha256=frame_hash)

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
    def start_streaming(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        """Start capturing frames in a background thread."""
        self._loop = loop

        if self.receiver:
            # No thread needed, receiver pushes frames via async mechanism.
            # But wait_for_frame needs to work.
            # Receiver has its own event.
            # We don't need to do anything here except maybe ensure receiver is ready.
            return

        if self._cap is None:
            self.open()

        if self._loop:
            self._frame_event = asyncio.Event()

        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def get_latest(self) -> CapturedFrame | None:
        """Return the most recently captured frame (thread-safe)."""
        if self.receiver:
             img, ts, seq = self.receiver.get_latest_frame()
             if img is None: return None
             frame_hash = hashlib.sha256(img.tobytes()).hexdigest()
             return CapturedFrame(image=img, timestamp=ts, sequence=seq, sha256=frame_hash)

        with self._lock:
            return self._latest_frame

    async def wait_for_frame(self) -> CapturedFrame:
        """Wait for the next frame asynchronously."""
        if self.receiver:
            # Delegate to receiver
            img, ts, seq = await self.receiver.wait_for_frame()
            if img is None:
                 raise RuntimeError("WebRTC frame waiter returned None")
            frame_hash = hashlib.sha256(img.tobytes()).hexdigest()
            return CapturedFrame(image=img, timestamp=ts, sequence=seq, sha256=frame_hash)

        if not self._frame_event:
            raise RuntimeError("Streaming not configured for asyncio (pass loop to start_streaming)")

        await self._frame_event.wait()
        self._frame_event.clear()

        frame = self.get_latest()
        if frame is None:
             raise RuntimeError("Event set but no frame available")
        return frame

    def _capture_loop(self) -> None:
        interval = 1.0 / self.fps
        while self._running:
            try:
                frame = self.grab()
                with self._lock:
                    self._latest_frame = frame

                if self._loop and self._frame_event:
                    self._loop.call_soon_threadsafe(self._frame_event.set)

            except RuntimeError as exc:
                logger.warning("Frame grab error: %s", exc)
            time.sleep(interval)
