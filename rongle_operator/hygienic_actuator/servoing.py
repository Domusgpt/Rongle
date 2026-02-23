from __future__ import annotations
import math
import time
import logging

logger = logging.getLogger(__name__)

def visual_servo_move(
    target_x: int,
    target_y: int,
    grabber,
    tracker,
    hid,
    ducky_parser,
    tolerance: int = 15,
    max_steps: int = 5,
    gain: float = 0.5  # lambda gain
) -> bool:
    """
    Closed-loop Visual Servoing.

    Instead of assuming a perfect open-loop move, this function iteratively:
    1. Looks at the cursor position
    2. Calculates error e(t) = target - current
    3. Moves by delta = gain * error

    This is a simplified implementation of q_dot = -lambda * J_pseudo * e(t).
    Here we assume J is somewhat diagonal/identity multiplied by scale (handled in parser/calibration).
    """

    # We need to know current position first
    frame = grabber.grab()
    current_cursor = tracker.detect(frame.image)

    if not current_cursor:
        # Fallback to blind move if we can't see the cursor
        logger.warning("Visual Servoing: Cursor not visible, falling back to open-loop")
        # We need to convert absolute target to relative move from *assumed* position?
        # Or just use absolute move logic if hid supports it (it doesn't, it's relative).
        # We'll try to use parser's internal state.

        # Calculate delta from parser's last known state
        dx = target_x - ducky_parser._cursor_x
        dy = target_y - ducky_parser._cursor_y

        # Scaling is handled inside ducky_parser logic usually, but here we are manual.
        # Let's rely on a direct relative move helper if we had one.
        # For now, let's just abort servoing and return False so caller uses open loop?
        return False

    current_x, current_y = current_cursor.x, current_cursor.y

    for step in range(max_steps):
        error_x = target_x - current_x
        error_y = target_y - current_y

        dist = math.sqrt(error_x**2 + error_y**2)
        if dist < tolerance:
            logger.info(f"Visual Servoing converged in {step} steps (dist={dist:.1f})")
            return True

        # Control Law: u = gain * error
        # We need to convert pixel error to HID units.
        # ducky_parser.scale_x is (HID / Pixel)

        move_x = int(error_x * gain * ducky_parser.scale_x)
        move_y = int(error_y * gain * ducky_parser.scale_y)

        # Clamp minimum movement to avoid Zeno's paradox if gain is small vs integer truncation
        if move_x == 0 and abs(error_x) > 5: move_x = 1 if error_x > 0 else -1
        if move_y == 0 and abs(error_y) > 5: move_y = 1 if error_y > 0 else -1

        from rongle_operator.hygienic_actuator.ducky_parser import MouseReport
        report = MouseReport(buttons=0, dx=move_x, dy=move_y, wheel=0)
        hid._write_mouse(report.pack())

        # Wait for movement + capture delay
        time.sleep(0.1)

        # Update state
        frame = grabber.grab()
        current_cursor = tracker.detect(frame.image)
        if not current_cursor:
             logger.warning("Visual Servoing: Lost cursor track")
             return False
        current_x, current_y = current_cursor.x, current_cursor.y

        # Update parser internal state to keep it in sync
        ducky_parser._cursor_x = current_x * ducky_parser.scale_x
        ducky_parser._cursor_y = current_y * ducky_parser.scale_y

    logger.warning("Visual Servoing did not converge")
    return False
