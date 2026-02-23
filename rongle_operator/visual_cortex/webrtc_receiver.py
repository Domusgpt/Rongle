"""
WebRTC Receiver — Handles incoming WebRTC connections from the Android app (Native Eye).

Uses ``aiortc`` to accept an SDP Offer, create an RTCPeerConnection, and
consume the incoming video track. Frames are stored in a buffer for the FrameGrabber.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

import cv2
import numpy as np
from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaRelay

logger = logging.getLogger(__name__)

# Monkey-patch av logging to reduce noise
logging.getLogger("av").setLevel(logging.WARNING)


class WebRTCReceiver:
    """
    Manages WebRTC connections and stores the latest video frame.
    """

    def __init__(self) -> None:
        self._pcs: set[RTCPeerConnection] = set()
        self._latest_frame: Optional[np.ndarray] = None
        self._frame_timestamp: float = 0.0
        self._frame_sequence: int = 0
        self._frame_event = asyncio.Event()
        self._relay: Optional[MediaRelay] = None

    async def handle_offer(self, sdp: dict) -> dict:
        """
        Process an SDP offer from a client (Android app).
        sdp: {"sdp": "...", "type": "offer"}
        Returns the SDP answer: {"sdp": "...", "type": "answer"}
        """
        pc = RTCPeerConnection()
        self._pcs.add(pc)

        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            logger.info("Connection state is %s", pc.connectionState)
            if pc.connectionState == "failed":
                await pc.close()
                self._pcs.discard(pc)
            elif pc.connectionState == "closed":
                self._pcs.discard(pc)

        @pc.on("track")
        def on_track(track):
            logger.info("Track received: %s (kind=%s)", track.id, track.kind)
            if track.kind == "video":
                # Create a background task to consume frames from this track
                asyncio.create_task(self._consume_track(track))

        # Set Remote Description
        offer = RTCSessionDescription(sdp=sdp["sdp"], type=sdp["type"])
        await pc.setRemoteDescription(offer)

        # Create Answer
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        return {
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type
        }

    async def _consume_track(self, track: MediaStreamTrack):
        """Consume frames from a video track forever."""
        logger.info("Started consuming video track %s", track.id)
        try:
            while True:
                frame = await track.recv()

                # Convert av.VideoFrame to numpy array (BGR for OpenCV)
                # frame.to_ndarray(format="bgr24") returns (H, W, 3)
                img = frame.to_ndarray(format="bgr24")

                # Update receiver's latest frame
                self._update_frame(img)

        except Exception as e:
            # MediaStreamError or similar means track ended
            logger.warning("Track ended or error: %s", e)
        finally:
            logger.info("Stopped consuming video track %s", track.id)

    def _update_frame(self, frame: np.ndarray):
        """Update the latest frame and notify waiters."""
        self._latest_frame = frame
        self._frame_timestamp = time.time()
        self._frame_sequence += 1
        # Set event for anyone waiting (FrameGrabber)
        self._frame_event.set()

    def get_latest_frame(self) -> tuple[Optional[np.ndarray], float, int]:
        """Return the latest frame, timestamp, and sequence number."""
        return self._latest_frame, self._frame_timestamp, self._frame_sequence

    async def wait_for_frame(self) -> tuple[Optional[np.ndarray], float, int]:
        """Wait until a new frame arrives."""
        self._frame_event.clear()
        await self._frame_event.wait()
        return self.get_latest_frame()

    async def close(self):
        """Close all peer connections."""
        coros = [pc.close() for pc in self._pcs]
        await asyncio.gather(*coros)
        self._pcs.clear()
