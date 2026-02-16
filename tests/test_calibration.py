
import asyncio
import numpy as np
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from rongle_operator.calibration import HomographyCalibrator, CalibrationResult
from rongle_operator.visual_cortex.frame_grabber import CapturedFrame
from rongle_operator.visual_cortex.reflex_tracker import CursorDetection

@pytest.mark.asyncio
async def test_calibration_sequence():
    # Mocks
    hid = MagicMock()
    # Async mocks for HID writes (simulating sleeps)
    hid._write_mouse = MagicMock()

    grabber = AsyncMock()
    # Mock wait_for_frame to return frames with specific cursor positions
    # Sequence:
    # 1. Blind moves (4 corners)
    # 2. Sensitivity check (2 moves)

    # We need to simulate the cursor position changing based on blind moves.
    # Let's just return a sequence of detections.

    # Frame 1: After move to TL -> cursor at (100, 100)
    # Frame 2: After move to TR -> cursor at (1800, 100)
    # Frame 3: After move to BR -> cursor at (1800, 1000)
    # Frame 4: After move to BL -> cursor at (100, 1000)
    # Frame 5: Start sensitivity check (at BL) -> (100, 1000)
    # Frame 6: After move X (+200) -> (300, 1000)
    # Frame 7: After move Y (+200) -> (300, 1200)

    frames = []
    positions = [
        (100, 100),   # TL
        (1800, 100),  # TR
        (1800, 1000), # BR
        (100, 1000),  # BL
        (100, 1000),  # Start sens
        (300, 1000),  # Mid sens X
        (300, 1200),  # End sens Y
    ]

    for i, (x, y) in enumerate(positions):
        frame = MagicMock(spec=CapturedFrame)
        frame.image = np.zeros((1080, 1920, 3), dtype=np.uint8)
        frames.append(frame)

    grabber.wait_for_frame.side_effect = frames

    tracker = MagicMock()
    # tracker.detect(frame) -> Detection(x, y)
    # Since we mocked frames, we can just return Detections based on call count or frame identity?
    # Simpler: side_effect on tracker.detect

    detections = [CursorDetection(x=x, y=y, confidence=1.0, method="test") for x, y in positions]
    tracker.detect.side_effect = detections

    calibrator = HomographyCalibrator()

    # Run calibration
    result = await calibrator.calibrate(hid, grabber, tracker)

    assert isinstance(result, CalibrationResult)
    assert result.homography is not None
    assert result.homography.shape == (3, 3)

    # Check sensitivity
    # dx_cam = 300 - 100 = 200.
    # Map to screen?
    # TL=(100,100) -> (0,0), TR=(1800,100) -> (1,0). Width=1700.
    # So 200 cam pixels is approx 200/1700 = 0.117 screen width.
    # Move was 200 HID units.
    # Sensitivity = 200 / 0.117 = 1700.
    # Let's verify it's close.
    assert 1600 < result.sensitivity_x < 1800

    # Check map_camera_to_screen
    # (100, 100) should act as (0, 0)
    sx, sy = calibrator.map_camera_to_screen(100, 100)
    assert abs(sx - 0.0) < 0.01
    assert abs(sy - 0.0) < 0.01

    # (1800, 1000) should be (1, 1)
    sx, sy = calibrator.map_camera_to_screen(1800, 1000)
    assert abs(sx - 1.0) < 0.01
    assert abs(sy - 1.0) < 0.01
