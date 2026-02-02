import sys
import os
import io
import unittest
from unittest.mock import MagicMock, patch, mock_open

# Add parent directory to path to import core
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.actuator import HygienicActuator

class TestHygienicActuator(unittest.TestCase):

    @patch('builtins.open', new_callable=mock_open)
    def test_init_simulation_mode(self, mock_file):
        # Simulate IOError to trigger simulation mode
        mock_file.side_effect = IOError("No HID device")

        actuator = HygienicActuator()

        self.assertTrue(actuator.simulation_mode)
        # Verify it tried to open the device
        mock_file.assert_called()

    @patch('builtins.open', new_callable=mock_open)
    def test_init_hardware_mode(self, mock_file):
        # Simulate successful file open
        mock_file.side_effect = None

        actuator = HygienicActuator()

        self.assertFalse(actuator.simulation_mode)
        self.assertEqual(mock_file.call_count, 2) # Keyboard and Mouse

    @patch('time.sleep')
    @patch('builtins.open', new_callable=mock_open)
    def test_execute_ducky_script_string(self, mock_file, mock_sleep):
        mock_file.side_effect = IOError # Sim mode
        actuator = HygienicActuator()

        # Capture stdout to verify simulation output
        with patch('sys.stdout', new=io.StringIO()) as mock_stdout:
            actuator.execute_ducky_script("STRING Hello")
            output = mock_stdout.getvalue()
            self.assertIn("[SIM] Typing: Hello", output)

    @patch('time.sleep')
    @patch('builtins.open', new_callable=mock_open)
    def test_execute_ducky_script_delay(self, mock_file, mock_sleep):
        mock_file.side_effect = IOError # Sim mode
        actuator = HygienicActuator()

        actuator.execute_ducky_script("DELAY 500")

        mock_sleep.assert_called_with(0.5)

    @patch('time.sleep')
    @patch('builtins.open', new_callable=mock_open)
    def test_move_mouse_humanized(self, mock_file, mock_sleep):
         # Hardware mode to check _send_mouse_report logic (though mocked)
         mock_file.side_effect = None
         actuator = HygienicActuator()

         # Mock _send_mouse_report logic indirectly by checking writes
         # Actually `_send_mouse_report` writes to `self.mouse_fd`

         target_x, target_y = 100, 100
         actuator.move_mouse_humanized(target_x, target_y, duration_sec=0.01)

         # Check that mouse_fd.write was called
         self.assertTrue(actuator.mouse_fd.write.called)

if __name__ == '__main__':
    unittest.main()
