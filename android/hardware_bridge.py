"""
Android Hardware Bridge — Connects Rongle Operator to Android hardware.

This script acts as a specialized entrypoint when running on an Android device
(e.g., via Termux). It uses:
1. "IP Webcam" app for video input (http://localhost:8080/video).
2. Root access or ADB to inject touch/keyboard events (replacing /dev/hidg*).

Usage:
    python -m android.hardware_bridge --goal "Open Chrome"
"""

import argparse
import logging
import os
import sys
import subprocess
import time
from pathlib import Path

# Add repo root to path
sys.path.append(str(Path(__file__).parent.parent))

from rongle_operator.main import agent_loop, calibrate
from rongle_operator.config.settings import Settings
from rongle_operator.visual_cortex import FrameGrabber, ReflexTracker, VLMReasoner, FastDetector
from rongle_operator.hygienic_actuator import DuckyScriptParser, EmergencyStop, HIDGadget
from rongle_operator.policy_engine import PolicyGuardian
from rongle_operator.immutable_ledger import AuditLogger
from rongle_operator.session_manager import SessionManager
from rongle_operator.visual_cortex.vlm_reasoner import GeminiBackend

logger = logging.getLogger("android_bridge")

class AndroidHIDGadget(HIDGadget):
    """
    Simulates HID gadget by injecting events into Android input subsystem.
    Requires root (su) or ADB access.
    """
    def __init__(self, dry_run: bool = False):
        super().__init__(dry_run=dry_run)
        self.use_adb = False # Set True if not running as root in Termux

    def open(self):
        logger.info("AndroidHIDGadget ready (using shell input commands)")

    def close(self):
        pass

    def execute(self, cmd):
        """Translate parsed Ducky command to 'input' shell command."""
        if self.dry_run:
            logger.info(f"Android DRY-RUN: {cmd.kind} {cmd.raw_line}")
            return

        # Simple mapping for MVP
        if cmd.kind == "mouse_click":
            # We need absolute coordinates for 'input tap'.
            # The parser tracks _cursor_x/_cursor_y.
            # But the base HIDGadget doesn't store state.
            # We rely on the caller to handle servoing/movement.
            # This is tricky because standard HID is relative.
            # Android 'input tap' is absolute.
            # Strategy: We only support absolute moves via MOUSE_MOVE logic
            # or we assume the parser's state is accurate.
            pass
        elif cmd.kind == "string":
            text = cmd.string_chars.replace(' ', '%s') # input text handles spaces poorly sometimes
            self._run(f"input text '{text}'")
        elif cmd.kind == "keyboard":
            # Map keycodes to Android keyevents if needed
            pass

    def _write_mouse(self, report_bytes):
        # Override relative mouse moves.
        # Since we can't easily do relative moves with 'input',
        # we might need to change the Actuator architecture to support Absolute positioning interfaces.
        # For now, we log a warning.
        logger.warning("Relative mouse injection not fully supported on Android Bridge yet.")

    def _run(self, shell_cmd):
        try:
            subprocess.run(shell_cmd, shell=True, check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed: {shell_cmd} -> {e}")

def main():
    parser = argparse.ArgumentParser(description="Rongle Android Bridge")
    parser.add_argument("--goal", type=str, default="")
    parser.add_argument("--ip-webcam", type=str, default="http://127.0.0.1:8080/video")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    # 1. Setup Vision (IP Webcam)
    settings = Settings()
    settings.video_device = args.ip_webcam

    grabber = FrameGrabber(device=settings.video_device)

    # 2. Setup HID (Android Shell)
    hid = AndroidHIDGadget()

    # 3. Setup Standard Components
    tracker = ReflexTracker()
    detector = FastDetector()
    guardian = PolicyGuardian()
    audit = AuditLogger(log_path="./android_audit.jsonl")
    session_mgr = SessionManager(db_path="./android_session.db")
    estop = EmergencyStop(software_only=True) # No GPIO on phone

    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if not gemini_key:
        logger.error("GEMINI_API_KEY required")
        return

    reasoner = VLMReasoner(backend=GeminiBackend(api_key=gemini_key))

    # Humanizer/Parser
    from rongle_operator.hygienic_actuator import Humanizer
    humanizer = Humanizer()
    ducky_parser = DuckyScriptParser(screen_w=1920, screen_h=1080, humanizer=humanizer)

    try:
        grabber.open()
        hid.open()

        goal = args.goal or input("Goal: ")

        agent_loop(
            goal=goal,
            grabber=grabber,
            tracker=tracker,
            reasoner=reasoner,
            parser=ducky_parser,
            hid=hid,
            guardian=guardian,
            audit=audit,
            estop=estop,
            detector=detector,
            session_mgr=session_mgr
        )
    except KeyboardInterrupt:
        pass
    finally:
        grabber.close()
        hid.close()

if __name__ == "__main__":
    main()
