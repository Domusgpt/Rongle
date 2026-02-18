#!/usr/bin/env python3
"""
Hardware-Isolated Agentic Operator — Async Core (RFC-001)

Implements the async perception-action loop with robust calibration (RFC-004)
and session persistence (RFC-002).
Also supports WebRTC streaming input (RFC-003).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from .config.settings import Settings
from .hygienic_actuator import DuckyScriptParser, EmergencyStop, HIDGadget, Humanizer
from .hal.base import VideoSource, HIDActuator
from .hal.pi_hal import PiVideoSource, PiHIDActuator
from .hal.desktop_hal import DesktopVideoSource, DesktopHIDActuator
from .immutable_ledger import AuditLogger
from .policy_engine import PolicyGuardian, PolicyVerdict
from .visual_cortex import FrameGrabber, ReflexTracker, VLMReasoner, FastDetector
from .visual_cortex.vlm_reasoner import GeminiBackend, LocalVLMBackend
from .session_manager import SessionManager, AgentSession
from .calibration import HomographyCalibrator, CalibrationResult

# RFC-003 WebRTC
try:
    from .visual_cortex.webrtc_receiver import WebRTCReceiver
    from .webrtc_server import WebRTCServer
    HAS_WEBRTC = True
except ImportError:
    HAS_WEBRTC = False

logger = logging.getLogger("rng_operator")


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------
@dataclass
class AgentAction:
    """Represents a planned action to be executed."""
    kind: str  # "CLICK", "TYPE", "WAIT", "DONE"
    label: str  # Description for logs
    target_norm: tuple[float, float] | None = None  # (x, y) 0..1
    current_norm: tuple[float, float] | None = None  # (x, y) 0..1 (detected cursor pos)
    text: str | None = None  # For TYPE actions


class AgentState:
    IDLE = "IDLE"
    CALIBRATING = "CALIBRATING"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


# ---------------------------------------------------------------------------
# Async Tasks
# ---------------------------------------------------------------------------
async def perception_task(
    queue: asyncio.Queue[AgentAction],
    grabber: FrameGrabber,
    tracker: ReflexTracker,
    reasoner: VLMReasoner,
    detector: FastDetector,
    calibrator: HomographyCalibrator,
    session_mgr: SessionManager,
    current_session: AgentSession,
    stop_event: asyncio.Event,
    audit: AuditLogger,
    goal: str,
) -> None:
    """
    Continually perceives the environment and plans actions.
    """
    logger.info("Perception task started.")
    last_action_desc = ""

    while not stop_event.is_set():
        try:
            # 1. Wait for next frame (Async)
            # This works for both V4L2 and WebRTC sources
            frame = await grabber.wait_for_frame()

            # 2. Detect Cursor
            cursor = tracker.detect(frame.image)
            cursor_norm = (0.5, 0.5) # Default center if not found
            if cursor:
                cursor_norm = calibrator.map_camera_to_screen(cursor.x, cursor.y)

            # 3. Reason / Plan
            # Check if queue is full (backpressure)
            if queue.full():
                await asyncio.sleep(0.1)
                continue

            prompt = goal
            if current_session.context_history:
                last_action_desc = current_session.context_history[-1]
                prompt = f"{goal} (previous action: {last_action_desc})"

            # VLM Query (Async)
            element = await reasoner.find_element(frame.image, prompt)

            action = None
            if element:
                logger.info("Perception: Found target '%s' at (%d, %d)", element.label, element.x, element.y)

                # Map target to normalized screen coords
                target_center_x, target_center_y = element.center
                target_norm = calibrator.map_camera_to_screen(target_center_x, target_center_y)

                # Create Action
                action = AgentAction(
                    kind="CLICK",
                    label=f"Click '{element.label}'",
                    target_norm=target_norm,
                    current_norm=cursor_norm
                )
            else:
                logger.info("Perception: No element found. Goal might be complete.")
                await asyncio.sleep(1.0)
                continue

            # 4. Push to Queue
            await queue.put(action)
            audit.log("PLAN", action_detail=action.label, screenshot_hash=frame.sha256)

            # Wait a bit to avoid rapid-fire (simple rate limiting)
            await asyncio.sleep(0.5)

        except Exception as e:
            logger.error("Perception error: %s", e)
            await asyncio.sleep(1.0)

    logger.info("Perception task stopped.")


async def actuation_task(
    queue: asyncio.Queue[AgentAction],
    hid: HIDGadget,
    parser: DuckyScriptParser,
    calibrator: HomographyCalibrator,
    tracker: ReflexTracker,
    grabber: FrameGrabber,
    servo: VisualServo,
    guardian: PolicyGuardian,
    estop: EmergencyStop,
    audit: AuditLogger,
    session_mgr: SessionManager,
    current_session: AgentSession,
    stop_event: asyncio.Event,
) -> None:
    """
    Consumes actions from the queue and executes them on hardware.
    """
    logger.info("Actuation task started.")

    while not stop_event.is_set():
        try:
            # Get action (with timeout to check stop_event)
            try:
                action = await asyncio.wait_for(queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            if estop.is_stopped:
                logger.critical("E-STOP Active. Dropping action.")
                queue.task_done()
                continue

            logger.info("Actuation: Executing %s", action.label)

            # Execute Action
            if action.kind == "CLICK" and action.target_norm and action.current_norm:
                sx = calibrator.sensitivity_x
                sy = calibrator.sensitivity_y

                start_hid_x = action.current_norm[0] * sx
                start_hid_y = action.current_norm[1] * sy

                end_hid_x = action.target_norm[0] * sx
                end_hid_y = action.target_norm[1] * sy

                # 1. Open-loop Move (Bezier Path)
                points = parser.humanizer.bezier_path(start_hid_x, start_hid_y, end_hid_x, end_hid_y)
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, hid.send_mouse_path, points)

                # 2. Closed-loop Correction (Visual Servoing)
                servo_steps = 0
                max_servo_steps = 3
                while servo_steps < max_servo_steps:
                    s_frame = await grabber.wait_for_frame()
                    s_det = tracker.detect(s_frame.image)
                    if not s_det:
                        break

                    # Map target_norm to current image pixels
                    tx_img = action.target_norm[0] * s_frame.width
                    ty_img = action.target_norm[1] * s_frame.height

                    dx, dy = servo.compute_correction(s_det.x, s_det.y, int(tx_img), int(ty_img))
                    if dx == 0 and dy == 0:
                        break

                    from .hygienic_actuator.ducky_parser import MouseReport
                    report = MouseReport(buttons=0, dx=dx, dy=dy, wheel=0)
                    await loop.run_in_executor(None, hid._write_mouse, report.pack())
                    await asyncio.sleep(0.1)
                    servo_steps += 1

                # 3. Click
                await loop.run_in_executor(None, hid.send_mouse_click, 1) # Left click

                audit.log("EXECUTE", action_detail=f"Moved and Clicked: {action.label} (servo_steps={servo_steps})")

            elif action.kind == "TYPE" and action.text:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, hid.send_string, action.text)
                audit.log("EXECUTE", action_detail=f"Typed: {action.text}")

            # Update Session (Persistence)
            current_session.step_index += 1
            current_session.context_history.append(action.label)
            # Trim history
            if len(current_session.context_history) > 10:
                current_session.context_history.pop(0)
            session_mgr.save_session(current_session)

            queue.task_done()

            # Brief pause to let UI settle
            await asyncio.sleep(0.2)

        except Exception as e:
            logger.error("Actuation error: %s", e)
            queue.task_done() # Mark done even on error

    logger.info("Actuation task stopped.")


# ---------------------------------------------------------------------------
# Setup & Main
# ---------------------------------------------------------------------------
def check_environment(settings: Settings, dry_run: bool, use_webrtc: bool) -> None:
    """Pre-flight check for hardware availability."""
    if dry_run:
        logger.info("Dry-run mode: skipping hardware checks.")
        return

    required = [
        ("Keyboard Gadget", settings.hid_keyboard_dev),
        ("Mouse Gadget", settings.hid_mouse_dev),
    ]

    # Only check video device if NOT using WebRTC
    if not use_webrtc:
        required.append(("Video Device", settings.video_device))

    missing = []
    for name, path in required:
        if not Path(path).exists():
            missing.append(f"{name} ({path})")

    # Check write access to audit log directory
    log_dir = Path(settings.audit_log_path).parent
    if not os.access(log_dir, os.W_OK):
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            missing.append(f"Audit Log Dir Write Access ({log_dir})")

    if missing:
        msg = f"Environment check failed. Missing: {', '.join(missing)}"
        logger.error(msg)
        raise RuntimeError(msg)
    logger.info("Environment check passed.")


async def main_async() -> None:
    parser = argparse.ArgumentParser(description="Hardware-Isolated Agentic Operator (Async)")
    parser.add_argument("--goal", type=str, default="", help="Agent goal")
    parser.add_argument("--config", type=str, default="rng_operator/config/settings.json",
                        help="Path to settings JSON")
    parser.add_argument("--dry-run", action="store_true", help="No actual HID output")
    parser.add_argument("--software-estop", action="store_true",
                        help="Use software-only emergency stop")
    parser.add_argument("--webrtc", action="store_true", help="Enable WebRTC video input (RFC-003)")
    args = parser.parse_args()

    # Logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("/tmp/operator.log"),
        ],
    )

    settings = Settings.load(args.config)
    try:
        check_environment(settings, args.dry_run, args.webrtc)
    except RuntimeError as e:
        sys.exit(str(e))

    # Initialize Components
    humanizer = Humanizer(
        jitter_sigma=settings.humanizer_jitter_sigma,
        overshoot_ratio=settings.humanizer_overshoot,
    )
    ducky_parser = DuckyScriptParser(
        screen_w=settings.screen_width,
        screen_h=settings.screen_height,
        humanizer=humanizer,
    )

    # HAL Selection
    if args.dry_run:
        logger.info("Using Desktop Simulation HAL")
        video_source = DesktopVideoSource(width=settings.screen_width, height=settings.screen_height)
        hid_actuator = DesktopHIDActuator()
    else:
        logger.info("Using Pi Hardware HAL")
        video_source = PiVideoSource(device=settings.video_device, width=settings.screen_width, height=settings.screen_height)
        hid_actuator = PiHIDActuator(kbd_dev=settings.hid_keyboard_dev, mouse_dev=settings.hid_mouse_dev)

    # Legacy HIDGadget for backward compatibility with parser logic (internal usage)
    hid = HIDGadget(
        keyboard_dev=settings.hid_keyboard_dev,
        mouse_dev=settings.hid_mouse_dev,
        dry_run=args.dry_run,
    )

    # WebRTC Setup
    webrtc_receiver = None
    webrtc_server = None
    if args.webrtc:
        if not HAS_WEBRTC:
            logger.error("WebRTC requested but dependencies (aiortc, aiohttp) not found.")
            sys.exit(1)
        logger.info("Initializing WebRTC Receiver...")
        webrtc_receiver = WebRTCReceiver()
        webrtc_server = WebRTCServer(webrtc_receiver, port=8080) # Using 8080 or configurable?

    grabber = FrameGrabber(
        device=settings.video_device,
        width=settings.screen_width,
        height=settings.screen_height,
        fps=settings.capture_fps,
        receiver=webrtc_receiver
    )

    tracker = ReflexTracker(
        cursor_templates_dir=settings.cursor_templates_dir,
    )
    detector = FastDetector()
    servo = VisualServo()
    guardian = PolicyGuardian(allowlist_path=settings.allowlist_path)
    audit = AuditLogger(log_path=settings.audit_log_path)
    session_mgr = SessionManager(
        db_path=Path(settings.audit_log_path).parent / "session.db"
    )
    calibrator = HomographyCalibrator()

    # VLM Backend
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if gemini_key:
        vlm_backend = GeminiBackend(api_key=gemini_key, model=settings.vlm_model)
    else:
        vlm_backend = LocalVLMBackend(model_id=settings.local_vlm_model)
    reasoner = VLMReasoner(backend=vlm_backend)

    # E-Stop
    estop = EmergencyStop(
        gpio_line=settings.estop_gpio_line,
        on_stop=lambda: hid.release_all(),
        software_only=args.software_estop,
    )

    # State / Session
    goal = args.goal
    current_session = session_mgr.load_active_session()

    if current_session:
        logger.info("Resuming session %s (Step %d). Goal: %s",
                    current_session.session_id, current_session.step_index, current_session.goal)
        if goal and goal != current_session.goal:
             logger.warning("Overriding active session goal with CLI arg")
             current_session.goal = goal
        else:
             goal = current_session.goal
    else:
        if not goal:
            goal = input("Enter agent goal: ").strip()

        if not goal:
            logger.error("No goal specified. Exiting.")
            return

        session_id = f"sess_{int(time.time())}"
        current_session = AgentSession(session_id=session_id, goal=goal, step_index=0)
        logger.info("Started new session: %s", session_id)

    # --- Start Lifecycle ---
    try:
        hid.open()
        estop.start()

        loop = asyncio.get_running_loop()

        if webrtc_server:
            await webrtc_server.start()
            logger.info("WebRTC Server running. Waiting for connection...")
            # If WebRTC, we might want to wait for first frame BEFORE calibration?
            # Or trust wait_for_frame handles it.

        grabber.start_streaming(loop=loop)

        # Initial Calibration
        logger.info("Waiting for first frame...")
        await grabber.wait_for_frame()

        try:
             if not args.dry_run:
                 if args.webrtc:
                     logger.info("Waiting for WebRTC frame for calibration...")
                     # Implicitly wait_for_frame inside calibrate will block until connected
                 cal_res = await calibrator.calibrate(hid, grabber, tracker)
                 servo.set_scale(cal_res.sensitivity_x, cal_res.sensitivity_y)
                 logger.info("Calibration successful. Servo scale set to (%.2f, %.2f)",
                             cal_res.sensitivity_x, cal_res.sensitivity_y)
             else:
                 logger.info("Dry run: Skipping calibration")
        except Exception as e:
             logger.error("Calibration failed: %s", e)

        # Start Tasks
        action_queue = asyncio.Queue(maxsize=1)
        stop_event = asyncio.Event()

        def _signal_handler():
            logger.info("Stopping...")
            stop_event.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _signal_handler)

        logger.info("=== AGENT LOOP START ===")

        tasks = [
            asyncio.create_task(perception_task(
                action_queue, grabber, tracker, reasoner, detector,
                calibrator, session_mgr, current_session, stop_event, audit, goal
            )),
            asyncio.create_task(actuation_task(
                action_queue, hid, ducky_parser, calibrator, tracker,
                grabber, servo, guardian,
                estop, audit, session_mgr, current_session, stop_event
            ))
        ]

        await stop_event.wait()

        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    except Exception as e:
        logger.exception("Fatal error in main loop: %s", e)
    finally:
        logger.info("Shutting down...")
        if webrtc_server:
            await webrtc_server.stop()
        if webrtc_receiver:
            await webrtc_receiver.close()

        hid.release_all()
        estop.stop()
        grabber.close()
        hid.close()
        audit.close()

def main() -> None:
    asyncio.run(main_async())

if __name__ == "__main__":
    main()
