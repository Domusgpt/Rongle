import asyncio
import numpy as np
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from rongle_operator.visual_cortex.webrtc_receiver import WebRTCReceiver
from rongle_operator.visual_cortex.frame_grabber import FrameGrabber, CapturedFrame

# Mocking external libs
# Since aiortc might not be installed in CI or local unless we run pip install
# But I added them to requirements.
# However, for unit tests, mocking is better.

@pytest.mark.asyncio
@patch("rongle_operator.visual_cortex.webrtc_receiver.RTCPeerConnection")
@patch("rongle_operator.visual_cortex.webrtc_receiver.RTCSessionDescription")
async def test_webrtc_receiver_offer_handling(MockSDP, MockPC):
    receiver = WebRTCReceiver()

    # Mock PC instance
    pc = MockPC.return_value
    pc.createAnswer = AsyncMock()
    pc.setLocalDescription = AsyncMock()
    pc.setRemoteDescription = AsyncMock()
    pc.localDescription = MagicMock()
    pc.localDescription.sdp = "answer_sdp"
    pc.localDescription.type = "answer"

    # Mock createAnswer result (it returns RTCSessionDescription)
    answer_desc = MagicMock()
    pc.createAnswer.return_value = answer_desc

    offer = {"sdp": "offer_sdp", "type": "offer"}
    answer = await receiver.handle_offer(offer)

    assert answer["sdp"] == "answer_sdp"
    assert answer["type"] == "answer"

    pc.setRemoteDescription.assert_called_once()
    pc.createAnswer.assert_called_once()
    pc.setLocalDescription.assert_called_with(answer_desc)

@pytest.mark.asyncio
async def test_webrtc_receiver_frame_consumption():
    receiver = WebRTCReceiver()

    # Mock track
    track = AsyncMock()
    track.kind = "video"
    track.id = "video-track"

    # Mock frame from av
    frame = MagicMock()
    # to_ndarray returns numpy array
    frame.to_ndarray.return_value = np.zeros((100, 100, 3), dtype=np.uint8)

    # track.recv needs to return frame once, then raise Exception to stop loop
    # But wait, _consume_track loops forever until exception.
    # We can mock recv to raise asyncio.CancelledError to stop cleanly or just Exception.

    # To test that it updates frame:
    # We can run the task, wait a bit, then cancel it?
    # Or just have it run one iteration.

    # Let's use side_effect to return frame then raise StopIteration (which breaks loop in some contexts but here we catch Exception)
    track.recv.side_effect = [frame, RuntimeError("Stop")]

    # We need to await _consume_track
    # It catches Exception and logs it, then finishes.
    await receiver._consume_track(track)

    img, ts, seq = receiver.get_latest_frame()
    assert img is not None
    assert img.shape == (100, 100, 3)
    assert seq == 1

@pytest.mark.asyncio
async def test_frame_grabber_webrtc_integration():
    # Mock receiver
    receiver = MagicMock() # Not AsyncMock because wait_for_frame returns a tuple, not a coroutine mock by default unless configured

    # wait_for_frame is async
    receiver.wait_for_frame = AsyncMock()

    frame_img = np.zeros((1080, 1920, 3), dtype=np.uint8)
    # Return (img, ts, seq)
    receiver.wait_for_frame.return_value = (frame_img, 12345.0, 1)

    # get_latest_frame is sync
    receiver.get_latest_frame.return_value = (frame_img, 12345.0, 1)

    grabber = FrameGrabber(receiver=receiver)

    # Test grab (sync)
    captured = grabber.grab()
    assert isinstance(captured, CapturedFrame)
    assert captured.sequence == 1
    assert captured.timestamp == 12345.0

    # Test wait_for_frame (async)
    captured_async = await grabber.wait_for_frame()
    assert isinstance(captured_async, CapturedFrame)
    assert captured_async.sequence == 1

    receiver.wait_for_frame.assert_called()
