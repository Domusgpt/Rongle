"""
Calibration — Screen coordinate mapping and sensitivity estimation.

Implements robust 4-point calibration to compute a Homography matrix
that maps Camera coordinates (distorted, perspective) to Normalized Screen coordinates (0..1).
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

import cv2
import numpy as np

from .hygienic_actuator.ducky_parser import MouseReport
from .visual_cortex.reflex_tracker import ReflexTracker
from .visual_cortex.frame_grabber import FrameGrabber
from .hygienic_actuator.hid_gadget import HIDGadget

logger = logging.getLogger(__name__)


@dataclass
class CalibrationResult:
    homography: np.ndarray  # 3x3 matrix
    sensitivity_x: float    # HID units per normalized screen width
    sensitivity_y: float    # HID units per normalized screen height
    error_margin: float     # Estimated reprojection error


class HomographyCalibrator:
    """
    Manages the calibration process to map Camera -> Screen coordinates.
    """

    def __init__(self) -> None:
        self.homography: np.ndarray | None = None
        self.sensitivity_x: float = 1000.0  # Default guess
        self.sensitivity_y: float = 1000.0
        self.camera_width: int = 1920
        self.camera_height: int = 1080

    async def calibrate(
        self,
        hid: HIDGadget,
        grabber: FrameGrabber,
        tracker: ReflexTracker,
    ) -> CalibrationResult:
        """
        Run full calibration sequence:
        1. Locate 4 corners (TL, TR, BR, BL) via blind moves.
        2. Compute Homography.
        3. Measure sensitivity via small moves.
        """
        logger.info("Starting Homography Calibration...")

        # 1. Find Corners
        corners_cam = await self._find_corners(hid, grabber, tracker)
        if not corners_cam:
            raise RuntimeError("Failed to find screen corners")

        # 2. Compute Homography
        # Source: Camera coordinates
        src_pts = np.array(corners_cam, dtype=np.float32)

        # Destination: Normalized Screen coordinates (TL, TR, BR, BL)
        # (0,0), (1,0), (1,1), (0,1)
        dst_pts = np.array([
            [0, 0],
            [1, 0],
            [1, 1],
            [0, 1]
        ], dtype=np.float32)

        H, status = cv2.findHomography(src_pts, dst_pts)
        if H is None:
             raise RuntimeError("Homography computation failed")

        self.homography = H
        logger.info("Homography matrix computed:\n%s", H)

        # 3. Measure Sensitivity
        # Move to ~Center (0.5, 0.5) to avoid edges
        # We need to know where we are. We are currently at BL (from corner find).
        # Map BL_cam to Screen (should be 0,1).
        # Move to (0.5, 0.5) implies moving (+0.5, -0.5) in screen space.
        # Use default sensitivity for this move.

        logger.info("Moving to center for sensitivity check...")
        # Move roughly to center from Bottom-Left
        # Assuming 1920x1080 screen and standard mouse speed, 1000 units might be enough?
        # Safe bet: use the corners we just found to estimate pixel distance?
        # No, we want HID sensitivity.

        # Let's just move +2000, -2000 from BL and see where we end up.
        # This brings us inwards.

        await self._move_hid(hid, 100, -100) # Small move to unstuck from corner
        await asyncio.sleep(0.5)

        # Now do a measured move
        start_frame = await grabber.wait_for_frame()
        start_cursor = tracker.detect(start_frame.image)
        if not start_cursor:
             logger.warning("Cursor lost during sensitivity check")
             # Fallback to defaults
             return CalibrationResult(H, 1000.0, 1000.0, 0.0)

        # Move X
        move_x = 200
        await self._move_hid(hid, move_x, 0)
        await asyncio.sleep(0.5)

        mid_frame = await grabber.wait_for_frame()
        mid_cursor = tracker.detect(mid_frame.image)

        if mid_cursor:
            # Map both to screen space
            p1 = self.map_camera_to_screen(start_cursor.x, start_cursor.y)
            p2 = self.map_camera_to_screen(mid_cursor.x, mid_cursor.y)

            dx_screen = abs(p2[0] - p1[0])
            if dx_screen > 0.01:
                self.sensitivity_x = move_x / dx_screen
                logger.info("Measured Sensitivity X: %.2f (delta_scr=%.3f)", self.sensitivity_x, dx_screen)

        # Move Y
        move_y = 200
        await self._move_hid(hid, 0, move_y)
        await asyncio.sleep(0.5)

        end_frame = await grabber.wait_for_frame()
        end_cursor = tracker.detect(end_frame.image)

        if end_cursor and mid_cursor:
            p2 = self.map_camera_to_screen(mid_cursor.x, mid_cursor.y)
            p3 = self.map_camera_to_screen(end_cursor.x, end_cursor.y)

            dy_screen = abs(p3[1] - p2[1])
            if dy_screen > 0.01:
                self.sensitivity_y = move_y / dy_screen
                logger.info("Measured Sensitivity Y: %.2f (delta_scr=%.3f)", self.sensitivity_y, dy_screen)

        return CalibrationResult(H, self.sensitivity_x, self.sensitivity_y, 0.0)

    async def _find_corners(self, hid: HIDGadget, grabber: FrameGrabber, tracker: ReflexTracker) -> list[tuple[int, int]] | None:
        """Locate 4 corners by moving blindly into them."""
        # Order: TL, TR, BR, BL
        moves = [
            (-10000, -10000), # -> TL
            (20000, 0),       # -> TR
            (0, 20000),       # -> BR
            (-20000, 0),      # -> BL
        ]

        corners = []

        for dx, dy in moves:
            await self._move_hid(hid, dx, dy)
            await asyncio.sleep(0.5) # Wait for move to settle

            # Capture and detect
            # Retry a few times if cursor not found
            found = None
            for _ in range(3):
                frame = await grabber.wait_for_frame()
                found = tracker.detect(frame.image)
                if found:
                    break
                await asyncio.sleep(0.2)

            if found:
                corners.append((found.x, found.y))
                logger.info("Corner found at (%d, %d)", found.x, found.y)
            else:
                logger.error("Failed to find cursor at corner step (%d, %d)", dx, dy)
                return None

        return corners

    async def _move_hid(self, hid: HIDGadget, dx: int, dy: int) -> None:
        """Helper to move HID mouse properly (handling report limits)."""
        # HID report usually fits 127 or 32767 depending on descriptor.
        # Assuming standard 8-bit or 16-bit. HIDGadget sends what it gets.
        # But let's break it down to be safe/smooth.

        step = 100
        steps_x = int(dx / step)
        steps_y = int(dy / step)

        rem_x = dx % step
        rem_y = dy % step

        # We can send these in a loop, but don't blocking-sleep too much.
        # Ideally HIDGadget should be async or we run in executor.
        # For now, we do simple loop with small sleep.

        max_steps = max(abs(steps_x), abs(steps_y))

        for i in range(max_steps):
            sx = step if i < abs(steps_x) else 0
            sy = step if i < abs(steps_y) else 0

            if steps_x < 0: sx = -sx
            if steps_y < 0: sy = -sy

            report = MouseReport(buttons=0, dx=sx, dy=sy, wheel=0)
            hid._write_mouse(report.pack())
            await asyncio.sleep(0.005) # 5ms

        if rem_x or rem_y:
            report = MouseReport(buttons=0, dx=rem_x, dy=rem_y, wheel=0)
            hid._write_mouse(report.pack())

    def map_camera_to_screen(self, cx: int, cy: int) -> tuple[float, float]:
        """Map camera pixel coordinates to normalized screen coordinates (0..1)."""
        if self.homography is None:
            return (0.0, 0.0)

        # Perspective transform
        # point is [x, y, 1]
        pt = np.array([[[cx, cy]]], dtype=np.float32)
        dst = cv2.perspectiveTransform(pt, self.homography)
        return (float(dst[0][0][0]), float(dst[0][0][1]))

    def calculate_hid_delta(self, curr_cam: tuple[int, int], target_cam: tuple[int, int]) -> tuple[int, int]:
        """Calculate HID dx, dy needed to move from curr to target (in Camera space)."""
        p1 = self.map_camera_to_screen(*curr_cam)
        p2 = self.map_camera_to_screen(*target_cam)

        dx_scr = p2[0] - p1[0]
        dy_scr = p2[1] - p1[1]

        dx_hid = int(dx_scr * self.sensitivity_x)
        dy_hid = int(dy_scr * self.sensitivity_y)

        return dx_hid, dy_hid
