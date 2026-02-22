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


from ..hal.base import VideoSource

class FrameGrabber:
    """
    Continuous frame capture from a VideoSource or WebRTC receiver.

    Parameters
    ----------
    video_source : VideoSource | None
        HAL video source.
    width : int
        Capture width in pixels.
    height : int
        Capture height in pixels.
    fps : int
        Desired capture frame rate.
    receiver : WebRTCReceiver | None
        Optional WebRTC receiver source. If provided, 'video_source' is ignored.
    """

    def __init__(
        self,
        video_source: VideoSource | None = None,
        width: int = 1920,
        height: int = 1080,
        fps: int = 30,
        receiver: Any | None = None,
    ) -> None:
        self.video_source = video_source
        self.width = width
        self.height = height
        self.fps = fps
        self.receiver = receiver

        self._cap: Any | None = None
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

        if self.video_source:
             self.video_source.open()
             logger.info("FrameGrabber using HAL video source")
             return

        raise RuntimeError("No video source or receiver provided")

    def close(self) -> None:
        """Release the capture device."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=3.0)
        if self.video_source:
            self.video_source.close()

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
            img, ts, seq = self.receiver.get_latest_frame()
            if img is None:
                raise RuntimeError("No WebRTC frame available yet")
            frame_hash = hashlib.sha256(img.tobytes()).hexdigest()
            return CapturedFrame(image=img, timestamp=ts, sequence=seq, sha256=frame_hash)

        if self.video_source is None:
            raise RuntimeError("FrameGrabber not opened (no video source)")

        frame = self.video_source.grab()
        self._seq += 1
        frame_hash = hashlib.sha256(frame.image.tobytes()).hexdigest()

        return CapturedFrame(
            image=frame.image,
            timestamp=frame.timestamp,
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
