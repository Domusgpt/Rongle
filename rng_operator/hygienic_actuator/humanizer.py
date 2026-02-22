"""
Humanizer — Generates Bezier-curve mouse trajectories that mimic human hand jitter.

Instead of teleporting the cursor from (x0, y0) to (x1, y1), this module
computes a cubic Bezier path with:
  - Randomized control points (simulates hand overshoot/undershoot)
  - Gaussian noise per waypoint (simulates micro-tremor)
  - Variable step count proportional to distance
  - Slight velocity easing (slow start, fast middle, slow end)
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class BezierPoint:
    """A single waypoint along the Bezier path, expressed as relative deltas."""
    dx: int       # signed 8-bit relative X
    dy: int       # signed 8-bit relative Y
    dwell_ms: int  # how long to hold before emitting next point


class Humanizer:
    """
    Converts absolute (x0, y0) -> (x1, y1) movement into a list of
    ``BezierPoint`` micro-movements that feel organic when injected via HID.

    Parameters
    ----------
    jitter_sigma : float
        Standard deviation (pixels) of Gaussian noise added per waypoint.
    overshoot_ratio : float
        How far control points may deviate from the straight line (0..1).
    min_steps : int
        Minimum number of interpolation steps.
    max_steps : int
        Maximum number of interpolation steps.
    base_dwell_ms : int
        Base inter-report dwell time in milliseconds.
    """

    def __init__(
        self,
        jitter_sigma: float = 1.5,
        overshoot_ratio: float = 0.25,
        min_steps: int = 15,
        max_steps: int = 80,
        base_dwell_ms: int = 2,
    ) -> None:
        self.jitter_sigma = jitter_sigma
        self.overshoot_ratio = overshoot_ratio
        self.min_steps = min_steps
        self.max_steps = max_steps
        self.base_dwell_ms = base_dwell_ms

    def bezier_path(
        self,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
    ) -> list[BezierPoint]:
        """
        Compute a humanized Bezier path from (x0, y0) to (x1, y1).

        Returns a list of ``BezierPoint`` relative-delta waypoints ready to be
        injected as HID mouse reports.
        """
        dist = math.hypot(x1 - x0, y1 - y0)
        if dist < 1.0:
            return []

        # Adaptive step count: more steps for longer distances
        steps = int(min(self.max_steps, max(self.min_steps, dist / 8)))

        # Generate two random control points for a cubic Bezier curve
        cp1x, cp1y = self._random_control_point(x0, y0, x1, y1, 0.33)
        cp2x, cp2y = self._random_control_point(x0, y0, x1, y1, 0.66)

        # Interpolate absolute positions along the cubic Bezier
        abs_points: list[tuple[float, float]] = []
        for i in range(steps + 1):
            t = i / steps
            # Ease-in-out parameterization: slow-fast-slow
            t_eased = self._ease_in_out(t)
            bx = self._cubic_bezier(x0, cp1x, cp2x, x1, t_eased)
            by = self._cubic_bezier(y0, cp1y, cp2y, y1, t_eased)

            # Add micro-jitter (skip endpoints to ensure precision)
            if 0 < i < steps:
                bx += random.gauss(0, self.jitter_sigma)
                by += random.gauss(0, self.jitter_sigma)

            abs_points.append((bx, by))

        # Convert absolute positions to relative deltas
        points: list[BezierPoint] = []
        prev_x, prev_y = x0, y0
        accum_dx, accum_dy = 0.0, 0.0

        for ax, ay in abs_points[1:]:  # skip first (it's the start)
            accum_dx += ax - prev_x
            accum_dy += ay - prev_y
            prev_x, prev_y = ax, ay

            # HID mouse deltas are signed 8-bit (-127..127)
            # Emit a report whenever accumulated delta is >= 1 pixel
            while abs(accum_dx) >= 1.0 or abs(accum_dy) >= 1.0:
                emit_dx = max(-127, min(127, int(accum_dx)))
                emit_dy = max(-127, min(127, int(accum_dy)))

                if emit_dx == 0 and emit_dy == 0:
                    break

                # Vary dwell slightly for realism
                dwell = self.base_dwell_ms + random.randint(0, 2)
                points.append(BezierPoint(dx=emit_dx, dy=emit_dy, dwell_ms=dwell))

                accum_dx -= emit_dx
                accum_dy -= emit_dy

        # Flush any sub-pixel remainder
        remainder_dx = int(round(accum_dx))
        remainder_dy = int(round(accum_dy))
        if remainder_dx != 0 or remainder_dy != 0:
            points.append(BezierPoint(
                dx=max(-127, min(127, remainder_dx)),
                dy=max(-127, min(127, remainder_dy)),
                dwell_ms=self.base_dwell_ms,
            ))

        return points

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    @staticmethod
    def _cubic_bezier(p0: float, p1: float, p2: float, p3: float, t: float) -> float:
        """Evaluate cubic Bezier at parameter t."""
        u = 1.0 - t
        return u * u * u * p0 + 3 * u * u * t * p1 + 3 * u * t * t * p2 + t * t * t * p3

    @staticmethod
    def _ease_in_out(t: float) -> float:
        """Smoothstep ease-in-out for velocity profile."""
        return t * t * (3.0 - 2.0 * t)

    def _random_control_point(
        self,
        x0: float, y0: float,
        x1: float, y1: float,
        t_along: float,
    ) -> tuple[float, float]:
        """
        Generate a randomized control point near the line segment (x0,y0)-(x1,y1)
        at parametric position ``t_along``, offset perpendicular by overshoot_ratio.
        """
        # Point on the straight line
        mx = x0 + (x1 - x0) * t_along
        my = y0 + (y1 - y0) * t_along

        # Perpendicular direction
        dx = x1 - x0
        dy = y1 - y0
        length = math.hypot(dx, dy) or 1.0
        perp_x = -dy / length
        perp_y = dx / length

        # Random offset
        offset = random.gauss(0, self.overshoot_ratio * length)
        return mx + perp_x * offset, my + perp_y * offset
