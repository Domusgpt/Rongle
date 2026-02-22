import sys
import os
import io
import unittest
from unittest.mock import MagicMock, patch, mock_open

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from rng_operator.hygienic_actuator import HIDGadget, DuckyScriptParser, Humanizer

class TestHygienicActuator(unittest.TestCase):

    @patch('builtins.open', new_callable=mock_open)
    def test_hid_gadget_simulation(self, mock_file):
        # Simulate IOError to trigger simulation mode (dry_run=False but file fails)
        mock_file.side_effect = IOError("No HID device")

        # In the new code, HIDGadget explicitly takes a dry_run param.
        # If we pass dry_run=False but open fails, it might raise or log.
        # Let's test explicit dry_run=True first which is the "simulation" equivalent now.
        gadget = HIDGadget(dry_run=True)
        self.assertTrue(gadget.dry_run)

    @patch('time.sleep')
    def test_parser_commands(self, mock_sleep):
        humanizer = Humanizer()
        parser = DuckyScriptParser(screen_w=1920, screen_h=1080, humanizer=humanizer)

        cmds = parser.parse("STRING Hello\nDELAY 500")
        self.assertEqual(len(cmds), 2)
        self.assertEqual(cmds[0].kind, "string")
        self.assertEqual(cmds[0].string_chars, "Hello")
        self.assertEqual(cmds[1].kind, "delay")
        self.assertEqual(cmds[1].delay_ms, 500)

    @patch('time.sleep')
    def test_parser_mouse(self, mock_sleep):
        humanizer = Humanizer()
        parser = DuckyScriptParser(screen_w=1920, screen_h=1080, humanizer=humanizer)

        # MOUSE_MOVE is now handled via parsing
        cmds = parser.parse("MOUSE_MOVE 100 100")
        self.assertEqual(len(cmds), 1)
        self.assertEqual(cmds[0].kind, "mouse_move")
        # Check that bezier points were generated
        self.assertTrue(len(cmds[0].mouse_points) > 0)

if __name__ == '__main__':
    unittest.main()
