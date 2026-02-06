"""Tests for Visual Servoing Logic."""

import pytest
from rng_operator.visual_cortex.servoing import VisualServo, ServoingConfig

def test_servo_deadband():
    servo = VisualServo(ServoingConfig(deadband_px=10))
    # Error is small (5px), should return (0,0)
    dx, dy = servo.compute_correction(100, 100, 105, 100)
    assert dx == 0
    assert dy == 0

def test_servo_correction_direction():
    servo = VisualServo(ServoingConfig(gain=0.5, deadband_px=1))
    # Target is at (200, 200), Current is at (100, 100)
    # Error = Current - Target = (-100, -100)
    # v_image = -gain * error = -0.5 * (-100) = 50
    # So we should move +50, +50
    dx, dy = servo.compute_correction(100, 100, 200, 200)
    assert dx > 0
    assert dy > 0
    assert dx == 50
    assert dy == 50

def test_servo_convergence():
    servo = VisualServo(ServoingConfig(gain=1.0, deadband_px=0))
    # If gain is 1, we should jump straight to target (in ideal identity jacobian)
    dx, dy = servo.compute_correction(0, 0, 10, 0)
    # Error = -10. v = -1 * -10 = 10.
    assert dx == 10
    assert dy == 0
