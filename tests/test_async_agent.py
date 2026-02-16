
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from rongle_operator.main import perception_task, actuation_task, AgentAction
from rongle_operator.session_manager import AgentSession

@pytest.mark.asyncio
async def test_perception_task_flow():
    queue = asyncio.Queue(maxsize=1)
    stop_event = asyncio.Event()

    # Mocks
    grabber = AsyncMock()
    grabber.wait_for_frame.return_value = MagicMock(image=MagicMock(), sha256="hash")

    tracker = MagicMock()
    tracker.detect.return_value = MagicMock(x=100, y=100)

    reasoner = AsyncMock()
    # Mock VLM result: Found a button
    element = MagicMock()
    element.label = "Button"
    element.center = (500, 500)
    element.confidence = 0.9
    # Add width/height for safety if accessed
    element.width = 100
    element.height = 50
    # Mock center property if it's a property on the mock?
    # No, we set it directly but element is a Mock object.
    # If reasonser returns a Mock, property access works if configured.
    # Let's mock the class or just use a SimpleNamespace or Mock with specs.

    reasoner.find_element.return_value = element

    detector = MagicMock()
    calibrator = MagicMock()
    calibrator.map_camera_to_screen.return_value = (0.5, 0.5)

    session_mgr = MagicMock()
    current_session = AgentSession("id", "goal", 0)
    audit = MagicMock()

    # Run task
    task = asyncio.create_task(perception_task(
        queue, grabber, tracker, reasoner, detector,
        calibrator, session_mgr, current_session, stop_event, audit, "goal"
    ))

    # Wait for queue to have item
    action = await asyncio.wait_for(queue.get(), timeout=2.0)

    assert action.kind == "CLICK"
    assert action.label == "Click 'Button'"
    assert action.target_norm == (0.5, 0.5)

    stop_event.set()
    await task

@pytest.mark.asyncio
async def test_actuation_task_flow():
    queue = asyncio.Queue(maxsize=1)
    stop_event = asyncio.Event()

    action = AgentAction("CLICK", "Test Click", (0.8, 0.8), (0.2, 0.2))
    await queue.put(action)

    # Mocks
    hid = MagicMock()
    # These are called via run_in_executor
    hid.send_mouse_path = MagicMock()
    hid.send_mouse_click = MagicMock()

    parser = MagicMock()
    parser.humanizer.bezier_path.return_value = [] # list of points

    calibrator = MagicMock()
    calibrator.sensitivity_x = 1000
    calibrator.sensitivity_y = 1000

    guardian = MagicMock()
    estop = MagicMock()
    estop.is_stopped = False

    audit = MagicMock()
    session_mgr = MagicMock()
    current_session = AgentSession("id", "goal", 0)

    task = asyncio.create_task(actuation_task(
        queue, hid, parser, calibrator, guardian,
        estop, audit, session_mgr, current_session, stop_event
    ))

    # Wait for queue to be empty (processed)
    # queue.join() blocks until task_done() is called for every item.
    await queue.join()

    # Verify HID calls
    # Since executor runs in thread, give it a tiny bit of time to complete the call
    await asyncio.sleep(0.1)

    assert hid.send_mouse_path.called
    assert hid.send_mouse_click.called

    # Check session update
    assert current_session.step_index == 1
    assert "Test Click" in current_session.context_history
    session_mgr.save_session.assert_called()

    stop_event.set()
    try:
        await asyncio.wait_for(task, timeout=1.0)
    except asyncio.TimeoutError:
        task.cancel()
