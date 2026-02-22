
import unittest
from unittest.mock import MagicMock, patch
from rng_operator.policy_engine.guardian import PolicyGuardian, PolicyVerdict

class TestPolicyGuardianDevMode(unittest.TestCase):
    def test_dev_mode_permits_all(self):
        # Initialize in dev_mode
        guardian = PolicyGuardian(dev_mode=True)

        # Test blocked command
        verdict = guardian.check_command("STRING rm -rf /")
        self.assertTrue(verdict.allowed)

        # Test blocked region click (assuming blocked region 0,0,100,100)
        # In default mode this would block, but dev mode sets allow_all_regions=True
        # and doesn't load the file if it doesn't exist, or overrides it.
        # Actually in load() if dev_mode is set, we return early with permissive config.
        verdict = guardian.check_mouse_click(50, 50)
        self.assertTrue(verdict.allowed)

    def test_normal_mode_blocks(self):
        # Mock file loading to avoid dependency on actual config file
        # We also need to patch Path.exists to return True so it attempts to read the file
        with patch("pathlib.Path.exists", return_value=True), \
             patch("builtins.open", unittest.mock.mock_open(read_data='{"blocked_keystroke_patterns": ["rm -rf"]}')):
            guardian = PolicyGuardian(dev_mode=False)

            verdict = guardian.check_command("STRING rm -rf /")
            self.assertFalse(verdict.allowed)

if __name__ == "__main__":
    unittest.main()
