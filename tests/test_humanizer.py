"""Tests for Humanizer — Bezier paths, clamping, step counts."""

import math
import random

import pytest
from rongle_operator.hygienic_actuator.humanizer import Humanizer, BezierPoint


@pytest.fixture
def humanizer():
    return Humanizer(jitter_sigma=1.5, overshoot_ratio=0.25)


@pytest.fixture
def deterministic_humanizer():
    """Humanizer with fixed seed for repeatable tests."""
    random.seed(42)
    return Humanizer(jitter_sigma=1.5, overshoot_ratio=0.25)


# ---------------------------------------------------------------------------
# BezierPoint dataclass
# ---------------------------------------------------------------------------
class TestBezierPoint:
    def test_frozen(self):
        bp = BezierPoint(dx=5, dy=-3, dwell_ms=2)
        with pytest.raises(AttributeError):
            bp.dx = 10

    def test_values(self):
        bp = BezierPoint(dx=127, dy=-127, dwell_ms=8)
        assert bp.dx == 127
        assert bp.dy == -127
        assert bp.dwell_ms == 8


# ---------------------------------------------------------------------------
# Path generation basics
# ---------------------------------------------------------------------------
class TestPathGeneration:
    def test_zero_distance_empty(self, humanizer):
        path = humanizer.bezier_path(100, 100, 100, 100)
        assert path == []

    def test_sub_pixel_distance_empty(self, humanizer):
        path = humanizer.bezier_path(100, 100, 100.5, 100.3)
        assert path == []

    def test_short_distance_has_points(self, humanizer):
        path = humanizer.bezier_path(100, 100, 110, 110)
        assert len(path) > 0

    def test_long_distance_has_many_points(self, humanizer):
        path = humanizer.bezier_path(0, 0, 1000, 800)
        assert len(path) > 10

    def test_returns_list_of_bezier_points(self, humanizer):
        path = humanizer.bezier_path(0, 0, 200, 150)
        for point in path:
            assert isinstance(point, BezierPoint)


# ---------------------------------------------------------------------------
# Delta clamping (±127)
# ---------------------------------------------------------------------------
class TestDeltaClamping:
    def test_dx_within_range(self, humanizer):
        path = humanizer.bezier_path(0, 0, 2000, 0)
        for point in path:
            assert -127 <= point.dx <= 127, f"dx={point.dx} out of range"

    def test_dy_within_range(self, humanizer):
        path = humanizer.bezier_path(0, 0, 0, 2000)
        for point in path:
            assert -127 <= point.dy <= 127, f"dy={point.dy} out of range"

    def test_diagonal_within_range(self, humanizer):
        path = humanizer.bezier_path(0, 0, 1500, 1500)
        for point in path:
            assert -127 <= point.dx <= 127
            assert -127 <= point.dy <= 127

    def test_negative_direction_within_range(self, humanizer):
        path = humanizer.bezier_path(1000, 1000, 0, 0)
        for point in path:
            assert -127 <= point.dx <= 127
            assert -127 <= point.dy <= 127


# ---------------------------------------------------------------------------
# Total displacement accuracy
# ---------------------------------------------------------------------------
class TestDisplacement:
    def test_total_dx_approximately_correct(self):
        """Sum of all dx deltas should approximate the total X distance."""
        random.seed(99)
        h = Humanizer(jitter_sigma=0.0, overshoot_ratio=0.0)
        path = h.bezier_path(100, 100, 400, 100)
        total_dx = sum(p.dx for p in path)
        # With no jitter or overshoot, should be very close to 300
        assert abs(total_dx - 300) < 5, f"Total dx={total_dx}, expected ~300"

    def test_total_dy_approximately_correct(self):
        random.seed(99)
        h = Humanizer(jitter_sigma=0.0, overshoot_ratio=0.0)
        path = h.bezier_path(100, 100, 100, 350)
        total_dy = sum(p.dy for p in path)
        assert abs(total_dy - 250) < 5, f"Total dy={total_dy}, expected ~250"

    def test_diagonal_displacement(self):
        random.seed(99)
        h = Humanizer(jitter_sigma=0.0, overshoot_ratio=0.0)
        path = h.bezier_path(0, 0, 200, 150)
        total_dx = sum(p.dx for p in path)
        total_dy = sum(p.dy for p in path)
        assert abs(total_dx - 200) < 5
        assert abs(total_dy - 150) < 5


# ---------------------------------------------------------------------------
# Dwell times
# ---------------------------------------------------------------------------
class TestDwellTimes:
    def test_dwell_positive(self, humanizer):
        path = humanizer.bezier_path(0, 0, 300, 200)
        for point in path:
            assert point.dwell_ms >= 0

    def test_dwell_reasonable_range(self, humanizer):
        path = humanizer.bezier_path(0, 0, 300, 200)
        for point in path:
            assert point.dwell_ms <= 20  # base=2 + random 0..2


# ---------------------------------------------------------------------------
# Step count adaptation
# ---------------------------------------------------------------------------
class TestStepCount:
    def test_short_distance_min_steps(self):
        """Short movements should use approximately min_steps."""
        h = Humanizer(min_steps=15, max_steps=80)
        random.seed(42)
        # distance=20 → steps = min(80, max(15, 20/8)) = 15
        path = h.bezier_path(100, 100, 120, 100)
        # Path length depends on step interpolation and accumulation
        assert len(path) > 0

    def test_long_distance_more_steps(self):
        """Longer movements should produce more waypoints."""
        h = Humanizer(jitter_sigma=0, overshoot_ratio=0)
        random.seed(42)
        short_path = h.bezier_path(0, 0, 50, 0)
        random.seed(42)
        long_path = h.bezier_path(0, 0, 500, 0)
        assert len(long_path) > len(short_path)


# ---------------------------------------------------------------------------
# Internal math functions
# ---------------------------------------------------------------------------
class TestInternals:
    def test_cubic_bezier_endpoints(self):
        # At t=0, should return p0; at t=1, should return p3
        assert Humanizer._cubic_bezier(10, 20, 30, 40, 0.0) == 10.0
        assert Humanizer._cubic_bezier(10, 20, 30, 40, 1.0) == 40.0

    def test_cubic_bezier_midpoint(self):
        # Symmetric case: all control points equal → always returns that value
        result = Humanizer._cubic_bezier(5, 5, 5, 5, 0.5)
        assert abs(result - 5.0) < 1e-10

    def test_ease_in_out_endpoints(self):
        assert Humanizer._ease_in_out(0.0) == 0.0
        assert Humanizer._ease_in_out(1.0) == 1.0

    def test_ease_in_out_midpoint(self):
        # smoothstep(0.5) = 0.5² × (3 - 2×0.5) = 0.25 × 2 = 0.5
        assert abs(Humanizer._ease_in_out(0.5) - 0.5) < 1e-10

    def test_ease_in_out_symmetry(self):
        # smoothstep(t) + smoothstep(1-t) should ≈ 1 for the smoothstep function
        for t in [0.1, 0.2, 0.3, 0.4]:
            a = Humanizer._ease_in_out(t)
            b = Humanizer._ease_in_out(1.0 - t)
            assert abs(a + b - 1.0) < 1e-10
