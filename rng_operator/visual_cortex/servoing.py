"""
Visual Servoing — Closed-loop control for mouse movement.

Implements the control law:
    v = -lambda * J_pseudo_inv * error

Where:
    v = velocity vector (dx, dy)
    lambda = gain (speed factor)
    J_pseudo_inv = pseudo-inverse of Image Jacobian (transforms image space to motor space)
    error = (current_pos - target_pos) in image space
"""

import numpy as np
from dataclasses import dataclass

@dataclass
class ServoingConfig:
    gain: float = 0.5
    deadband_px: int = 5
    max_steps: int = 10

class VisualServo:
    def __init__(self, config: ServoingConfig = ServoingConfig()):
        self.config = config
        # Approximate Image Jacobian (identity if 1:1 mapping, or learned)
        # J maps (dx, dy)_mouse -> (du, dv)_image
        # Here we assume an identity-like relationship scaled by sensitivity
        # Ideally, this should be calibrated.
        self.J_inv = np.eye(2)

    def set_scale(self, scale_x: float, scale_y: float):
        """
        Update the Jacobian approximation based on calibration.
        scale_x = pixels_moved / hid_units_sent
        """
        # J = diag(scale_x, scale_y)
        # J_inv = diag(1/scale_x, 1/scale_y)
        if scale_x == 0 or scale_y == 0:
            return
        self.J_inv = np.array([[1.0/scale_x, 0], [0, 1.0/scale_y]])

    def compute_correction(self, current_x: int, current_y: int, target_x: int, target_y: int) -> tuple[int, int]:
        """
        Calculate the next mouse delta to reduce error.
        Target is where we want to go. Current is where we are.
        Error = Target - Current (Vector pointing TO target)
        """
        # Vector from Current to Target
        error_x = target_x - current_x
        error_y = target_y - current_y

        dist = (error_x**2 + error_y**2)**0.5
        if dist < self.config.deadband_px:
            return 0, 0

        # Control law: u = -lambda * e
        # We need to map this to mouse delta using J_inv

        # Error vector (in Image Frame)
        e = np.array([error_x, error_y])

        # We want to move ALONG the error vector, proportional to gain
        # If error is (100, 0), we want to move Right.
        # HID Delta = J_inv * (Gain * Error)

        v_image = self.config.gain * e

        # Velocity in mouse space (HID units)
        v_mouse = self.J_inv @ v_image

        return int(v_mouse[0]), int(v_mouse[1])
