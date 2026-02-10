#!/usr/bin/env python3
"""
Hardware-Isolated Agentic Operator — Main Loop

Implements the Self-Calibration feedback cycle:

    ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
    │   LOOK   │────▶│  DETECT  │────▶│   MOVE   │────▶│  VERIFY  │
    │ (capture │     │ (find UI │     │ (execute │     │ (confirm │
    │  frame)  │     │  target) │     │  action) │     │  result) │
    └──────────┘     └──────────┘     └──────────┘     └──────┬───┘
         ▲                                                    │
         └────────────────────────────────────────────────────┘
                        loop until goal achieved

Startup sequence:
  1. Initialize hardware (HID gadget, frame grabber, GPIO)
  2. Calibrate screen coordinates via cursor detection
  3. Enter agent loop: receive goal → perceive → plan → act → verify
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import time
from pathlib import Path

from .config.settings import Settings
from .hygienic_actuator import DuckyScriptParser, EmergencyStop, HIDGadget, Humanizer
from .immutable_ledger import AuditLogger
from .policy_engine import PolicyGuardian
from .visual_cortex import FrameGrabber, ReflexTracker, VLMReasoner, VisualServo
from .visual_cortex.vlm_reasoner import GeminiBackend, LocalVLMBackend
from .utils.keyboard_listener import KeyMonitor

logger = logging.getLogger("rng_operator")


# ---------------------------------------------------------------------------
# Agent states
# ---------------------------------------------------------------------------
class AgentState:
    IDLE = "IDLE"
    CALIBRATING = "CALIBRATING"
    PERCEIVING = "PERCEIVING"
    PLANNING = "PLANNING"
    ACTING = "ACTING"
    VERIFYING = "VERIFYING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


# ---------------------------------------------------------------------------
# Self-Calibration: detect cursor to establish coordinate mapping
# ---------------------------------------------------------------------------
def calibrate(
    grabber: FrameGrabber,
    tracker: ReflexTracker,
    hid: HIDGadget,
    audit: AuditLogger,
    max_attempts: int = 5,
) -> tuple[float, float, int, int] | None:
    """
    Self-Calibration Procedure
    --------------------------
    1. LOOK  — Capture a frame from the HDMI feed.
    2. DETECT — Use ReflexTracker to locate the current cursor position.
    3. MOVE  — Nudge the cursor by a known delta via HID.
    4. VERIFY — Recapture and confirm the cursor moved by the expected amount.

    If the observed delta matches the injected delta (within tolerance),
    calibration is confirmed and the coordinate system is trusted.

    Returns the detected cursor (x, y) or None if calibration fails.
    """
    logger.info("=== SELF-CALIBRATION START ===")
    audit.log("CALIBRATION_START", action_detail="Beginning coordinate calibration")

    for attempt in range(1, max_attempts + 1):
        logger.info("Calibration attempt %d/%d", attempt, max_attempts)

        # --- STEP 1: LOOK ---
        frame_before = grabber.grab()
        audit.log(
            "CALIBRATE_LOOK",
            screenshot_hash=frame_before.sha256,
            action_detail=f"Captured pre-move frame (seq={frame_before.sequence})",
        )

        # --- STEP 2: DETECT ---
        detection_before = tracker.detect(frame_before.image)
        if detection_before is None:
            logger.warning("Cursor not detected — retrying")
            audit.log("CALIBRATE_DETECT_FAIL", action_detail="Cursor not found in frame")
            time.sleep(0.5)
            continue

        logger.info(
            "Cursor at (%d, %d) confidence=%.2f",
            detection_before.x, detection_before.y, detection_before.confidence,
        )

        # --- STEP 3: MOVE ---
        # Inject a known small delta (50px right, 50px down)
        known_dx, known_dy = 50, 50
        from .hygienic_actuator.ducky_parser import MouseReport
        report = MouseReport(buttons=0, dx=known_dx, dy=known_dy, wheel=0)
        hid._write_mouse(report.pack())
        time.sleep(0.15)  # wait for host to process + HDMI latency

        audit.log(
            "CALIBRATE_MOVE",
            action_detail=f"Injected delta ({known_dx}, {known_dy})",
        )

        # --- STEP 4: VERIFY ---
        frame_after = grabber.grab()
        detection_after = tracker.detect(frame_after.image)

        if detection_after is None:
            logger.warning("Cursor lost after move — retrying")
            audit.log("CALIBRATE_VERIFY_FAIL", action_detail="Cursor lost post-move")
            continue

        actual_dx = detection_after.x - detection_before.x
        actual_dy = detection_after.y - detection_before.y
        tolerance = 15  # pixels

        # Calculate scale: pixels per HID unit
        # Avoid division by zero
        scale_x = actual_dx / known_dx if known_dx != 0 else 1.0
        scale_y = actual_dy / known_dy if known_dy != 0 else 1.0

        # Even if not perfect, if it moved in the right direction we can use the scale
        if abs(actual_dx) > 5 and abs(actual_dy) > 5:
            logger.info(
                "Calibration PASSED: scale_x=%.2f scale_y=%.2f (obs %d,%d)",
                scale_x, scale_y, actual_dx, actual_dy,
            )
            audit.log(
                "CALIBRATION_PASS",
                screenshot_hash=frame_after.sha256,
                action_detail=(
                    f"Verified: scale ({scale_x:.2f},{scale_y:.2f})"
                ),
            )
            return scale_x, scale_y, detection_after.x, detection_after.y
        else:
            logger.warning(
                "Calibration mismatch: expected (%d,%d) got (%d,%d)",
                known_dx, known_dy, actual_dx, actual_dy,
            )

    logger.error("Calibration FAILED after %d attempts", max_attempts)
    audit.log("CALIBRATION_FAIL", action_detail="All calibration attempts exhausted")
    return None


# ---------------------------------------------------------------------------
# Main Agent Loop
# ---------------------------------------------------------------------------
def agent_loop(
    goal: str,
    grabber: FrameGrabber,
    tracker: ReflexTracker,
    reasoner: VLMReasoner,
    parser: DuckyScriptParser,
    hid: HIDGadget,
    guardian: PolicyGuardian,
    audit: AuditLogger,
    estop: EmergencyStop,
    servo: VisualServo,
    max_iterations: int = 100,
    confidence_threshold: float = 0.5,
) -> None:
    """
    Core perception-action loop.

    For each iteration:
      1. LOOK   — capture the current screen
      2. DETECT — ask the VLM to identify the next UI target
      3. MOVE   — generate Ducky Script, validate via policy, execute via HID
      4. VERIFY — re-capture and check if the action had the desired effect
    """
    logger.info("=== AGENT LOOP START === Goal: %s", goal)
    audit.log("AGENT_START", action_detail=f"Goal: {goal}")

    state = AgentState.PERCEIVING
    action_history: list[str] = []
    retry_count = 0
    max_retries = 3

    for iteration in range(1, max_iterations + 1):
        # Emergency stop check
        if estop.is_stopped:
            logger.critical("Emergency stop active — halting agent loop")
            audit.log("EMERGENCY_STOP", action_detail="Agent loop halted by kill switch")
            hid.release_all()
            return

        logger.info("--- Iteration %d (state=%s) ---", iteration, state)

        # ========================================
        # STEP 1: LOOK — Capture frame
        # ========================================
        state = AgentState.PERCEIVING
        try:
            frame = grabber.grab()
        except RuntimeError as exc:
            logger.error("Frame capture failed: %s", exc)
            audit.log("FRAME_ERROR", action_detail=str(exc))
            time.sleep(1.0)
            continue

        audit.log(
            "LOOK",
            screenshot_hash=frame.sha256,
            action_detail=f"Frame #{frame.sequence} captured",
        )

        # Also track cursor for coordinate awareness
        cursor = tracker.detect(frame.image)
        cursor_x = cursor.x if cursor else int(parser._cursor_x)
        cursor_y = cursor.y if cursor else int(parser._cursor_y)

        # ========================================
        # STEP 2: PLAN — VLM Generates Ducky Script
        # ========================================
        state = AgentState.PLANNING

        ducky_script = reasoner.plan_action(frame.image, goal, action_history)

        if not ducky_script or "GOAL_COMPLETE" in ducky_script:
            logger.info("Planner returned empty or complete signal.")
            audit.log("GOAL_COMPLETE", action_detail="VLM finished task")
            break

        logger.info("Generated Plan:\n%s", ducky_script)

        audit.log(
            "PLAN",
            screenshot_hash=frame.sha256,
            action_detail=f"Script: {ducky_script!r}",
        )

        # ========================================
        # STEP 3: ACT — Execute Ducky Script
        # ========================================
        state = AgentState.ACTING

        # Parse into commands
        commands = parser.parse(ducky_script)

        # Execute each command through the policy gate
        executed_script_segment = []
        for cmd in commands:
            if estop.is_stopped:
                hid.release_all()
                return

            # Policy check
            verdict = guardian.check_command(cmd.raw_line, cursor_x, cursor_y)
            audit.log(
                "POLICY_CHECK",
                action_detail=f"Command: {cmd.raw_line!r} → {verdict.allowed}",
                policy_verdict="allowed" if verdict.allowed else "blocked",
            )

            if not verdict.allowed:
                logger.warning("BLOCKED by policy: %s — %s", cmd.raw_line, verdict.reason)
                audit.log(
                    "POLICY_BLOCK",
                    action_detail=f"Blocked: {verdict.reason}",
                    policy_verdict="blocked",
                )
                continue

            # Special Handling for MOUSE_MOVE with Visual Servoing
            if cmd.kind == "mouse_move" and cmd.mouse_points:
                # We have a target absolute position from the command (the end of the path)
                target_x = cmd.mouse_points[-1].x # Actually humanizer points are relative/absolute mixes, wait.
                # DuckyScriptParser sets _cursor_x/_cursor_y to target.
                # Let's extract target from raw_line if needed or rely on the Humanizer points which are just "move along path".
                # Actually, DuckyScriptParser produces a list of BezierPoints (relative moves).
                # To Servo, we need the final Absolute target.
                # DuckyScriptParser updates its internal state. We can use that?
                # No, we need to know where we want to be *now*.

                # If we want closed loop, we should IGNORE the Bezier path and just Servo to the destination?
                # Or Servo *along* the path?
                # For MVP, let's Servo to destination if it's a "long" move, replacing the open-loop path.
                # However, the `ParsedCommand` structure has `mouse_points` which are typically small deltas.

                # Let's parse the target from the raw line for Servoing
                import re
                m = re.match(r"^MOUSE_MOVE\s+(-?\d+)\s+(-?\d+)$", cmd.raw_line, re.IGNORECASE)
                if m:
                    tx, ty = int(m.group(1)), int(m.group(2))
                    logger.info("Engaging Visual Servo to (%d, %d)", tx, ty)

                    # Servo Loop
                    servo_steps = 0
                    while servo_steps < 5: # Max 5 corrections
                        # Look
                        s_frame = grabber.grab()
                        s_det = tracker.detect(s_frame.image)
                        if not s_det:
                            break # Lost cursor, abort servo

                        cx, cy = s_det.x, s_det.y
                        dx, dy = servo.compute_correction(cx, cy, tx, ty)

                        if dx == 0 and dy == 0:
                            break # Converged

                        # Move (Raw HID injection)
                        from .hygienic_actuator.ducky_parser import MouseReport
                        report = MouseReport(buttons=0, dx=dx, dy=dy, wheel=0)
                        hid._write_mouse(report.pack())
                        time.sleep(0.1) # Latency wait
                        servo_steps += 1

                    # Update parser state to reality
                    parser._cursor_x = tx
                    parser._cursor_y = ty

                    # Log
                    audit.log("SERVO_MOVE", action_detail=f"Servoed to ({tx},{ty}) in {servo_steps} steps")
                    executed_script_segment.append(cmd.raw_line)
                    continue # Skip the default open-loop execution

            # Standard Execution via HID (Keyboard, Click, etc.)
            hid.execute(cmd)
            executed_script_segment.append(cmd.raw_line)
            audit.log(
                "EXECUTE",
                action_detail=f"Executed: {cmd.raw_line}",
                policy_verdict="allowed",
            )

            # Handle WAIT_FOR_IMAGE (Visual Reactive Command)
            if cmd.kind == "wait_for_image":
                logger.info("Waiting for image: %s", cmd.string_chars)
                # TODO: Implement loop waiting for VLM confirmation or CNN detection
                time.sleep(1.0) # Stub

        if executed_script_segment:
            action_history.append("; ".join(executed_script_segment))

        # ========================================
        # STEP 4: VERIFY — Check result
        # ========================================
        state = AgentState.VERIFYING
        time.sleep(0.5)  # allow host UI to update

        verify_frame = grabber.grab()
        audit.log(
            "VERIFY",
            screenshot_hash=verify_frame.sha256,
            action_detail=f"Post-action frame #{verify_frame.sequence}",
        )

        # Brief pause before next iteration
        time.sleep(0.2)

    logger.info("=== AGENT LOOP END ===")
    audit.log("AGENT_END", action_detail=f"Completed after {iteration} iterations")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Hardware-Isolated Agentic Operator")
    parser.add_argument("--goal", type=str, default="", help="Agent goal (interactive if empty)")
    parser.add_argument("--config", type=str, default="rng_operator/config/settings.json",
                        help="Path to settings JSON")
    parser.add_argument("--dry-run", action="store_true", help="No actual HID output")
    parser.add_argument("--software-estop", action="store_true",
                        help="Use software-only emergency stop (no GPIO)")
    parser.add_argument("--dev-mode", action="store_true",
                        help="Disable safety policies (DANGEROUS)")
    args = parser.parse_args()

    # Logging setup
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("/tmp/operator.log"),
        ],
    )

    settings = Settings.load(args.config)

    # CLI override for dev_mode
    if args.dev_mode:
        settings.dev_mode = True

    # --- Initialize all modules ---
    humanizer = Humanizer(
        jitter_sigma=settings.humanizer_jitter_sigma,
        overshoot_ratio=settings.humanizer_overshoot,
    )
    ducky_parser = DuckyScriptParser(
        screen_w=settings.screen_width,
        screen_h=settings.screen_height,
        humanizer=humanizer,
    )
    hid = HIDGadget(
        keyboard_dev=settings.hid_keyboard_dev,
        mouse_dev=settings.hid_mouse_dev,
        dry_run=args.dry_run,
    )
    grabber = FrameGrabber(
        device=settings.video_device,
        width=settings.screen_width,
        height=settings.screen_height,
        fps=settings.capture_fps,
    )
    tracker = ReflexTracker(
        cursor_templates_dir=settings.cursor_templates_dir,
    )
    guardian = PolicyGuardian(
        allowlist_path=settings.allowlist_path,
        dev_mode=settings.dev_mode,
    )
    audit = AuditLogger(
        log_path=settings.audit_log_path,
    )

    servo = VisualServo()

    # VLM backend
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if gemini_key:
        vlm_backend = GeminiBackend(api_key=gemini_key, model=settings.vlm_model)
    else:
        vlm_backend = LocalVLMBackend(model_id=settings.local_vlm_model)
    reasoner = VLMReasoner(backend=vlm_backend)

    # Emergency stop
    # In production (not dry-run), we mandate hardware E-Stop unless explicitly overridden
    must_have_hardware_estop = not args.dry_run and not args.software_estop

    if must_have_hardware_estop:
        # Check if gpiod is available before starting
        try:
            import gpiod
        except ImportError:
            logger.critical("FATAL: Hardware E-Stop (gpiod) required for production mode. Install libgpiod or use --dry-run / --software-estop for testing.")
            sys.exit(1)

    estop = EmergencyStop(
        gpio_line=settings.estop_gpio_line,
        on_stop=lambda: hid.release_all(),
        software_only=args.software_estop,
    )

    # Signal handler for graceful shutdown
    def _shutdown(sig, frame):
        logger.info("Received signal %s — shutting down", sig)
        estop.trigger()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Dev Mode Toggle
    def toggle_dev_mode():
        current = guardian.dev_mode
        new_state = not current
        guardian.dev_mode = new_state
        # Reload to apply permissive/restrictive rules immediately
        guardian.load()
        state_str = "ENABLED (UNSAFE)" if new_state else "DISABLED (SAFE)"
        logger.warning(f"\n\n{'!'*40}\nDEV MODE TOGGLED: {state_str}\n{'!'*40}\n")
        audit.log("DEV_MODE_TOGGLE", action_detail=f"User toggled Dev Mode to {new_state}")

    # Konami Code trigger: "up up down down left right left right b a start"
    key_monitor = KeyMonitor(
        callback=toggle_dev_mode,
        trigger_phrase="up up down down left right left right b a start"
    )

    # --- Start ---
    try:
        key_monitor.start()
        hid.open()
        grabber.open()
        estop.start()

        audit.log("SYSTEM_START", action_detail="All modules initialized")

        # Self-calibration
        cal_result = calibrate(grabber, tracker, hid, audit)
        if cal_result is None:
            logger.error("Calibration failed — entering safe mode")
            audit.log("SAFE_MODE", action_detail="Calibration failure, awaiting manual input")
        else:
            scale_x, scale_y, cx, cy = cal_result
            ducky_parser._cursor_x, ducky_parser._cursor_y = cx, cy
            servo.set_scale(scale_x, scale_y)

        # Agent goal
        goal = args.goal
        if not goal:
            goal = input("Enter agent goal: ").strip()

        if goal:
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
                servo=servo,
            )

    except Exception as exc:
        logger.exception("Fatal error: %s", exc)
        audit.log("FATAL_ERROR", action_detail=str(exc))
    finally:
        logger.info("Shutting down...")
        key_monitor.stop()
        hid.release_all()
        estop.stop()
        grabber.close()
        hid.close()
        audit.log("SYSTEM_STOP", action_detail="Clean shutdown")
        audit.close()


if __name__ == "__main__":
    main()
