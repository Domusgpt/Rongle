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
from .visual_cortex import FrameGrabber, ReflexTracker, VLMReasoner
from .visual_cortex.vlm_reasoner import GeminiBackend, LocalVLMBackend

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
) -> tuple[int, int] | None:
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

        if abs(actual_dx - known_dx) <= tolerance and abs(actual_dy - known_dy) <= tolerance:
            logger.info(
                "Calibration PASSED: expected (%d,%d) observed (%d,%d)",
                known_dx, known_dy, actual_dx, actual_dy,
            )
            audit.log(
                "CALIBRATION_PASS",
                screenshot_hash=frame_after.sha256,
                action_detail=(
                    f"Verified: expected delta ({known_dx},{known_dy}), "
                    f"observed ({actual_dx},{actual_dy})"
                ),
            )
            return detection_after.x, detection_after.y
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
    previous_action = ""
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
        # STEP 2: DETECT — VLM identifies next target
        # ========================================
        state = AgentState.PLANNING
        prompt = goal
        if previous_action:
            prompt = f"{goal} (previous action: {previous_action})"

        element = reasoner.find_element(frame.image, prompt)
        if element is None:
            logger.info("No actionable element found — goal may be complete")
            audit.log("GOAL_COMPLETE", action_detail="VLM found no more targets")
            break

        logger.info(
            "Target: '%s' at (%d, %d) %dx%d conf=%.2f",
            element.label, element.x, element.y,
            element.width, element.height, element.confidence,
        )

        if element.confidence < confidence_threshold:
            logger.warning("Confidence %.2f below threshold %.2f — skipping",
                         element.confidence, confidence_threshold)
            retry_count += 1
            if retry_count >= max_retries:
                logger.error("Max retries reached — stopping")
                audit.log("MAX_RETRIES", action_detail="Confidence too low after retries")
                break
            continue

        retry_count = 0

        # ========================================
        # STEP 3: ACT — Generate and execute Ducky Script
        # ========================================
        state = AgentState.ACTING

        # Build Ducky Script to click the target element center
        target_cx, target_cy = element.center
        ducky_script = f"MOUSE_MOVE {target_cx} {target_cy}\nMOUSE_CLICK LEFT"

        audit.log(
            "PLAN",
            screenshot_hash=frame.sha256,
            action_detail=f"Target '{element.label}' → script: {ducky_script!r}",
        )

        # Parse into commands
        commands = parser.parse(ducky_script)

        # Execute each command through the policy gate
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

            # Execute via HID
            hid.execute(cmd)
            audit.log(
                "EXECUTE",
                action_detail=f"Executed: {cmd.raw_line}",
                policy_verdict="allowed",
            )

        previous_action = f"Clicked '{element.label}' at ({target_cx}, {target_cy})"

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

        # Check if cursor moved to expected position
        verify_cursor = tracker.detect(verify_frame.image)
        if verify_cursor:
            dist = ((verify_cursor.x - target_cx) ** 2 + (verify_cursor.y - target_cy) ** 2) ** 0.5
            if dist < 30:
                logger.info("Verification PASSED: cursor near target (dist=%.1f)", dist)
            else:
                logger.warning("Verification WARN: cursor drift %.1f px from target", dist)

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
    )
    audit = AuditLogger(
        log_path=settings.audit_log_path,
    )

    # VLM backend
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if gemini_key:
        vlm_backend = GeminiBackend(api_key=gemini_key, model=settings.vlm_model)
    else:
        vlm_backend = LocalVLMBackend(model_id=settings.local_vlm_model)
    reasoner = VLMReasoner(backend=vlm_backend)

    # Emergency stop
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

    # --- Start ---
    try:
        hid.open()
        grabber.open()
        estop.start()

        audit.log("SYSTEM_START", action_detail="All modules initialized")

        # Self-calibration
        cursor_pos = calibrate(grabber, tracker, hid, audit)
        if cursor_pos is None:
            logger.error("Calibration failed — entering safe mode")
            audit.log("SAFE_MODE", action_detail="Calibration failure, awaiting manual input")
        else:
            ducky_parser._cursor_x, ducky_parser._cursor_y = cursor_pos

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
            )

    except Exception as exc:
        logger.exception("Fatal error: %s", exc)
        audit.log("FATAL_ERROR", action_detail=str(exc))
    finally:
        logger.info("Shutting down...")
        hid.release_all()
        estop.stop()
        grabber.close()
        hid.close()
        audit.log("SYSTEM_STOP", action_detail="Clean shutdown")
        audit.close()


if __name__ == "__main__":
    main()
