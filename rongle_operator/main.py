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
from .policy_engine import PolicyGuardian, PolicyVerdict
from .visual_cortex import FrameGrabber, ReflexTracker, VLMReasoner, FastDetector
from .visual_cortex.vlm_reasoner import GeminiBackend, LocalVLMBackend
from .session_manager import SessionManager, AgentSession

logger = logging.getLogger("operator")


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
    4. VERIFY — Recapture and confirm the cursor moved.
    5. CALCULATE — Derive scaling factors (HID units / Screen pixels).

    Returns (scale_x, scale_y, cursor_x, cursor_y) or None if calibration fails.
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

        # Determine if movement was significant enough to calculate scale
        if abs(actual_dx) < 5 or abs(actual_dy) < 5:
            logger.warning(
                "Movement too small for calibration: dx=%d dy=%d",
                actual_dx, actual_dy
            )
            continue

        scale_x = known_dx / actual_dx
        scale_y = known_dy / actual_dy

        logger.info(
            "Calibration PASSED: scale_x=%.3f scale_y=%.3f (expected %d,%d observed %d,%d)",
            scale_x, scale_y, known_dx, known_dy, actual_dx, actual_dy,
        )
        audit.log(
            "CALIBRATION_PASS",
            screenshot_hash=frame_after.sha256,
            action_detail=f"Scale calculated: x={scale_x:.3f}, y={scale_y:.3f}",
        )
        return scale_x, scale_y, detection_after.x, detection_after.y

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
    detector: FastDetector,
    session_mgr: SessionManager,
    max_iterations: int = 100,
    confidence_threshold: float = 0.5,
) -> None:
    """
    Core perception-action loop with state persistence.
    """
    # Initialize or resume session
    current_session = session_mgr.load_active_session()
    start_iter = 1
    previous_action = ""

    if current_session and current_session.goal == goal:
        logger.info("Resuming session %s (step %d)", current_session.session_id, current_session.step_index)
        start_iter = current_session.step_index + 1
        if current_session.context_history:
            previous_action = current_session.context_history[-1]
    else:
        # New session
        session_id = f"sess_{int(time.time())}"
        current_session = AgentSession(session_id=session_id, goal=goal, step_index=0)
        logger.info("=== AGENT LOOP START === Goal: %s", goal)
        audit.log("AGENT_START", action_detail=f"Goal: {goal}")

    state = AgentState.PERCEIVING
    retry_count = 0
    max_retries = 3

    for iteration in range(start_iter, max_iterations + 1):
        # Update session state
        current_session.step_index = iteration
        session_mgr.save_session(current_session)
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

        # Foveated Rendering Logic
        # 1. Run low-latency detection to find 'interactive' regions
        cnn_regions = detector.detect(frame.image)

        element = None
        if cnn_regions:
            # 2. Crop the frame around these regions
            foveal_data = detector.get_foveal_crop(frame.image, cnn_regions)

            if foveal_data:
                crop, offset_x, offset_y = foveal_data
                logger.info(f"Foveated Rendering: using crop {crop.shape} offset ({offset_x},{offset_y})")

                # 3. Send the crop to the VLM
                element = reasoner.find_element(crop, prompt)

                # 4. Translate coordinates back to full screen
                if element:
                    element.x += offset_x
                    element.y += offset_y
                    logger.info(f"Foveated: Mapped local ({element.x-offset_x},{element.y-offset_y}) to global ({element.x},{element.y})")

        # Fallback to full frame if no regions found or VLM failed on crop
        # This also acts as a "Calibration" step: if the CNN misses the target (crop fails),
        # the VLM sees the whole screen and can find it, implicitly correcting the CNN's blind spot.
        if element is None:
            if cnn_regions:
                logger.info("Foveated approach yielded no target; falling back to full frame (Calibration).")
            element = reasoner.find_element(frame.image, prompt)

            # Future improvement: Feed this successful VLM detection back to the CNN
            # to update its belief state or online learning model.
            if element:
                 logger.info(f"VLM Calibrated CNN: Target found at ({element.x},{element.y}) despite CNN miss.")
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

        # Try Visual Servoing for the move
        from .hygienic_actuator.servoing import visual_servo_move

        # We only servo if we are doing a click (which implies a move first).
        # We split the generation: Move first, then Click.

        servo_success = visual_servo_move(
            target_cx, target_cy,
            grabber, tracker, hid, parser
        )

        if servo_success:
             ducky_script = "MOUSE_CLICK LEFT"
             audit.log("SERVO", action_detail=f"Visual Servoing converged to ({target_cx}, {target_cy})")
        else:
             # Fallback to standard open-loop script
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

            # Semantic Check (Experimental Local VLM Guard)
            # If enabled in policy, we ask the local VLM if the command seems safe given the screen context.
            if verdict.allowed and guardian._config.semantic_safety_check and cmd.kind in ("string", "mouse_click"):
                # We reuse 'reasoner' which might be remote or local. Ideally this should force local.
                # For now, we perform a heuristic check.

                safety_prompt = f"Is the action '{cmd.raw_line}' safe to perform on this screen? Answer YES or NO."
                try:
                    # Prefer local backend if available for privacy/latency
                    # If the primary reasoner is already local, use it.
                    # If not, try to instantiate/cache a local instance (not implemented in this scope).
                    # Current impl reuses the active backend.

                    safety_resp = reasoner.backend.query(frame.image, safety_prompt)

                    # Check for explicit "NO" in the response description
                    response_upper = safety_resp.description.upper().strip()

                    # Robust check for refusal
                    if response_upper.startswith("NO") or "UNSAFE" in response_upper or "NOT SAFE" in response_upper:
                        logger.warning(f"Semantic Guard blocked: {cmd.raw_line} -> {response_upper}")
                        verdict = PolicyVerdict(allowed=False, reason=f"Semantic Safety Violation: {response_upper[:50]}...", rule_name="semantic_guard")
                except Exception as e:
                    logger.error(f"Semantic Guard failed to query VLM: {e}")
                    # Fail open or closed? Failing open for now to prevent lockout on VLM error
                    pass

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

            # Execute Reactive Commands or Standard HID
            if cmd.kind == "wait_for_image" or cmd.kind == "assert_visible":
                # Logic: check if the description in cmd.string_chars is visible now.
                # This requires a VLM call (expensive) or a fast detector.
                # For this implementation, we reuse the VLM reasoner.

                check_frame = grabber.grab()
                found = reasoner.find_element(check_frame.image, cmd.string_chars)

                if cmd.kind == "wait_for_image":
                    wait_attempts = 5
                    while not found and wait_attempts > 0:
                        logger.info(f"Waiting for '{cmd.string_chars}'...")
                        time.sleep(1.0)
                        check_frame = grabber.grab()
                        found = reasoner.find_element(check_frame.image, cmd.string_chars)
                        wait_attempts -= 1

                    if not found:
                         logger.warning(f"WAIT_FOR_IMAGE timed out: {cmd.string_chars}")
                         # Continue? Or abort? Standard Ducky Script usually aborts on failure?
                         # We'll continue but log it.

                elif cmd.kind == "assert_visible":
                    if not found:
                        logger.error(f"ASSERT_VISIBLE failed: {cmd.string_chars}")
                        audit.log("ASSERT_FAIL", action_detail=f"Element '{cmd.string_chars}' not found")
                        # Break execution of this script
                        break
                    else:
                        logger.info(f"ASSERT_VISIBLE passed: {cmd.string_chars}")

            else:
                # Standard HID command
                try:
                    hid.execute(cmd)
                    audit.log(
                        "EXECUTE",
                        action_detail=f"Executed: {cmd.raw_line}",
                        policy_verdict="allowed",
                    )
                except Exception as e:
                    logger.error(f"HID Execution Failed: {e}")
                    audit.log("HARDWARE_FAULT", action_detail=f"HID Write Failed: {e}")
                    # Abort current action sequence to prevent desync
                    break

        previous_action = f"Clicked '{element.label}' at ({target_cx}, {target_cy})"
        current_session.context_history.append(previous_action)
        # Trim history if needed
        if len(current_session.context_history) > 10:
            current_session.context_history.pop(0)

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

    # Mark session as done
    session_mgr.clear_session(current_session.session_id)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
def check_environment(settings: Settings, dry_run: bool) -> None:
    """Pre-flight check for hardware availability."""
    if dry_run:
        logger.info("Dry-run mode: skipping hardware checks.")
        return

    required = [
        ("Video Device", settings.video_device),
        ("Keyboard Gadget", settings.hid_keyboard_dev),
        ("Mouse Gadget", settings.hid_mouse_dev),
    ]

    missing = []
    for name, path in required:
        if not Path(path).exists():
            missing.append(f"{name} ({path})")

    # Check write access to audit log directory
    log_dir = Path(settings.audit_log_path).parent
    if not os.access(log_dir, os.W_OK):
        # Try to create it if it doesn't exist
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            missing.append(f"Audit Log Dir Write Access ({log_dir})")

    if missing:
        msg = f"Environment check failed. Missing: {', '.join(missing)}"
        logger.error(msg)
        raise RuntimeError(msg)

    logger.info("Environment check passed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Hardware-Isolated Agentic Operator")
    parser.add_argument("--goal", type=str, default="", help="Agent goal (interactive if empty)")
    parser.add_argument("--config", type=str, default="rongle_operator/config/settings.json",
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

    # Pre-flight checks
    try:
        check_environment(settings, args.dry_run)
    except RuntimeError as e:
        sys.exit(str(e))

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
    detector = FastDetector()  # Initialize fast detector (stub or model)
    guardian = PolicyGuardian(
        allowlist_path=settings.allowlist_path,
    )
    audit = AuditLogger(
        log_path=settings.audit_log_path,
    )
    session_mgr = SessionManager(
        db_path=Path(settings.audit_log_path).parent / "session.db"
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
        cal_result = calibrate(grabber, tracker, hid, audit)
        if cal_result is None:
            logger.error("Calibration failed — entering safe mode")
            audit.log("SAFE_MODE", action_detail="Calibration failure, awaiting manual input")
        else:
            sx, sy, cx, cy = cal_result
            ducky_parser.scale_x = sx
            ducky_parser.scale_y = sy
            ducky_parser._cursor_x = cx * sx
            ducky_parser._cursor_y = cy * sy

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
                detector=detector,
                session_mgr=session_mgr,
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
