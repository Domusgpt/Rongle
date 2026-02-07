
import unittest
import numpy as np
from rng_operator.visual_cortex.servoing import VisualServo, ServoingConfig

class TestServoing(unittest.TestCase):
    def test_servo_deadband(self):
        servo = VisualServo(config=ServoingConfig(deadband_px=10))
        # Error is small (5 px)
        dx, dy = servo.compute_correction(100, 100, 105, 100)
        self.assertEqual(dx, 0)
        self.assertEqual(dy, 0)

    def test_servo_correction_direction(self):
        servo = VisualServo(config=ServoingConfig(gain=1.0))
        servo.J_inv = np.eye(2) # 1:1 mapping

        # Target is at (200, 100), Current is (100, 100). Error = +100 X.
        # Should move +100 * gain
        dx, dy = servo.compute_correction(100, 100, 200, 100)
        self.assertGreater(dx, 0)
        self.assertEqual(dy, 0)

    def test_servo_convergence(self):
        servo = VisualServo(config=ServoingConfig(gain=0.5))
        servo.set_scale(1.0, 1.0) # 1 px = 1 hid unit

        target = 200
        current = 100

        for _ in range(5):
            dx, _ = servo.compute_correction(current, 100, target, 100)
            current += dx # Simulate perfect movement

        self.assertTrue(abs(current - target) < 10)

if __name__ == "__main__":
    unittest.main()
