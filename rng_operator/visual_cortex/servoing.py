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

    def update_jacobian(self, dx_mouse: int, dy_mouse: int, dx_image: int, dy_image: int):
        """Update the Jacobian estimate based on observed motion."""
        if dx_image == 0 and dy_image == 0:
            return

        # Simple online update (Broden's method or similar could be used here)
        # For now, we just log it or keep it static as per MVP
        pass

    def compute_correction(self, current_x: int, current_y: int, target_x: int, target_y: int) -> tuple[int, int]:
        """
        Calculate the next mouse delta to reduce error.
        """
        error_x = current_x - target_x
        error_y = current_y - target_y

        dist = (error_x**2 + error_y**2)**0.5
        if dist < self.config.deadband_px:
            return 0, 0

        # Control law: u = -lambda * e
        # We need to map this to mouse delta using J_inv

        # Error vector
        e = np.array([error_x, error_y])

        # Velocity in image space
        v_image = -self.config.gain * e

        # Velocity in mouse space
        v_mouse = self.J_inv @ v_image

        return int(v_mouse[0]), int(v_mouse[1])
