import asyncio
import os
import time
import logging
import sys
from unittest.mock import MagicMock, patch

# Add repo root to path
sys.path.append(os.getcwd())

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("e2e_emulation")

# Import core components
# Note: we import the class/function we want to test directly if possible,
# or we import the module if we need to mock things inside it.
from rongle_operator.main import agent_loop, AgentState, SessionManager
from rongle_operator.visual_cortex import VLMReasoner, FrameGrabber, ReflexTracker, FastDetector
from rongle_operator.hygienic_actuator import DuckyScriptParser, HIDGadget, EmergencyStop
from rongle_operator.policy_engine import PolicyGuardian
from rongle_operator.immutable_ledger import AuditLogger

# Mock HID gadget path
MOCK_HIDG0 = "/tmp/mock_hidg0"
MOCK_HIDG1 = "/tmp/mock_hidg1"

import numpy as np
import cv2

def create_mock_frame():
    # 640x480 black image with white button
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    # Draw a white button at (300, 200) size 100x50
    # Top-left: 300, 200. Bottom-right: 400, 250.
    cv2.rectangle(img, (300, 200), (400, 250), (255, 255, 255), -1)
    return img

class MockFrameGrabber(FrameGrabber):
    def __init__(self):
        self.sequence = 0

    def grab(self):
        self.sequence += 1
        img = create_mock_frame()
        # Return object with .image, .sha256, .sequence
        mock_frame = MagicMock()
        mock_frame.image = img
        mock_frame.sha256 = "mock_sha256"
        mock_frame.sequence = self.sequence
        return mock_frame

class MockVLMReasoner(VLMReasoner):
    def __init__(self):
        self.backend = MagicMock() # Mock backend for semantic checks

    def find_element(self, image, prompt):
        # We simulate finding the "Submit" button
        # In main.py, agent_loop calls find_element.
        # It returns an object with .label, .x, .y, .center, .confidence

        logger.info(f"MockVLM: Finding element for prompt '{prompt}'")

        mock_elem = MagicMock()
        mock_elem.label = "Submit Button"
        mock_elem.x = 300
        mock_elem.y = 200
        mock_elem.width = 100
        mock_elem.height = 50
        mock_elem.center = (350, 225)
        mock_elem.confidence = 0.95

        return mock_elem

def run_emulation():
    logger.info("Starting E2E Emulation Proof...")

    # 1. Setup Mock Hardware Files
    with open(MOCK_HIDG0, "wb") as f: pass
    with open(MOCK_HIDG1, "wb") as f: pass

    # 2. Instantiate Components with Mocks

    # Grabber
    grabber = MockFrameGrabber()

    # Tracker (Mocked to return None or specific pos)
    tracker = MagicMock(spec=ReflexTracker)
    tracker.detect.return_value = None # No cursor detected initially

    # Reasoner
    reasoner = MockVLMReasoner()

    # Parser
    humanizer = MagicMock()
    parser = DuckyScriptParser(screen_w=640, screen_h=480, humanizer=humanizer)

    # HID Gadget (Patched to write to file)
    with patch("builtins.open", create=True) as mock_open:
        # We need to distinguish between opening config files and HID gadgets.
        # This is tricky with builtins.open.
        # Better to just use the real file system for HID since we made tmp files.
        pass

    # Let's use the real HIDGadget but point it to tmp files
    # We need to mock os.path.exists to pass checks if needed, but our files exist.

    hid = HIDGadget(keyboard_dev=MOCK_HIDG1, mouse_dev=MOCK_HIDG0, dry_run=False)
    # We need to mock the _open_hid_interface method because `os.open` usually requires root for some flags if it's a char dev?
    # HIDGadget uses `open(path, "wb", buffering=0)`. This works for regular files too.

    # Guardian
    guardian = PolicyGuardian(allowlist_path="rongle_operator/config/allowlist.json")

    # Audit
    audit = MagicMock(spec=AuditLogger)

    # Estop
    estop = MagicMock(spec=EmergencyStop)
    estop.is_stopped = False

    # Detector (CNN)
    detector = MagicMock(spec=FastDetector)
    detector.detect.return_value = [] # Return empty to force VLM fallback

    # Session Manager
    session_mgr = MagicMock(spec=SessionManager)
    session_mgr.load_active_session.return_value = None # Start new session
    session_mgr.save_session = MagicMock()

    # 3. Patch Servoing to avoid complex logic/timeouts (optional, but let's try real servoing logic if possible)
    # Servoing requires `tracker.detect` to return cursor position.
    # If we want servoing to succeed, we need to mock tracker to show cursor moving towards target.
    # That's complex for a unit test. Let's mock `visual_servo_move` to return True immediately.

    with patch("rongle_operator.hygienic_actuator.servoing.visual_servo_move", return_value=True) as mock_servo:

        # 4. Run Agent Loop (1 Iteration)
        # We'll use max_iterations=1

        logger.info("Executing Agent Loop...")

        hid.open() # Open the mock files

        agent_loop(
            goal="Click the Submit button",
            grabber=grabber,
            tracker=tracker,
            reasoner=reasoner,
            parser=parser,
            hid=hid,
            guardian=guardian,
            audit=audit,
            estop=estop,
            detector=detector,
            session_mgr=session_mgr,
            max_iterations=1
        )

        hid.close()

    # 5. Verify Output
    logger.info("Verifying HID Output...")

    # Check if MOCK_HIDG0 (Mouse) has data
    with open(MOCK_HIDG0, "rb") as f:
        mouse_data = f.read()

    logger.info(f"Captured {len(mouse_data)} bytes of mouse data.")

    # Logic:
    # `visual_servo_move` was mocked to return True.
    # agent_loop then constructs: "MOUSE_CLICK LEFT".
    # `DuckyScriptParser` parses this into a `MouseReport` with buttons=1.
    # `HIDGadget` writes this report (4 bytes) + release report (4 bytes).
    # Total 8 bytes expected if only click.

    # BUT, did we move?
    # In agent_loop:
    # ducky_script = "MOUSE_CLICK LEFT" (since servo returned True)
    # So no explicit move command in Ducky Script. The move happened *inside* servoing.
    # Since we mocked servoing, no move data was written during servoing.
    # We only see the click.

    if len(mouse_data) >= 8:
        # Check for click report (byte 0 is buttons)
        # Report 1: [1, 0, 0, 0]
        # Report 2: [0, 0, 0, 0]

        click_report = mouse_data[0:4]
        release_report = mouse_data[4:8]

        if click_report[0] == 1 and release_report[0] == 0:
            logger.info("✅ SUCCESS: Agent generated LEFT CLICK event.")
            return True
        else:
            logger.error(f"FAIL: Data did not match click pattern. Got: {click_report.hex()} {release_report.hex()}")
            return False
    else:
        logger.error("FAIL: Insufficient data written.")
        return False

if __name__ == "__main__":
    try:
        success = run_emulation()
        if not success:
            exit(1)
    except Exception as e:
        logger.error(f"Emulation crashed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
