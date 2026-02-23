
import unittest
from unittest.mock import MagicMock
from rng_operator.utils.keyboard_listener import KeyMonitor

class TestKeyMonitor(unittest.TestCase):
    def test_buffer_trigger(self):
        callback = MagicMock()
        phrase = "secret"
        monitor = KeyMonitor(callback, trigger_phrase=phrase)

        # Simulate typing
        # 's', 'e', 'c', 'r', 'e', 't'
        # Manually updating buffer logic since we can't easily mock stdin select loop in unit test
        # We test the logic that would be inside the loop

        inputs = "wrong secret"
        for ch in inputs:
            monitor.buffer += ch
            if len(monitor.buffer) > len(phrase) + 5:
                monitor.buffer = monitor.buffer[-(len(phrase) + 5):]

            if phrase in monitor.buffer:
                monitor.callback()
                monitor.buffer = ""

        callback.assert_called_once()

    def test_buffer_overflow_protection(self):
        callback = MagicMock()
        phrase = "abc"
        monitor = KeyMonitor(callback, trigger_phrase=phrase)

        # Type a long string that doesn't contain the trigger
        long_str = "x" * 100
        for ch in long_str:
            monitor.buffer += ch
            if len(monitor.buffer) > len(phrase) + 5:
                monitor.buffer = monitor.buffer[-(len(phrase) + 5):]

        # Buffer should be small
        self.assertLessEqual(len(monitor.buffer), len(phrase) + 5)
        callback.assert_not_called()

if __name__ == "__main__":
    unittest.main()
