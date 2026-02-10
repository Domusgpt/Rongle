"""
Integration Test for Agentic Ducky Script Evolution.

This test:
1. Initializes a virtual `DuckySandbox`.
2. Uses `AgenticDuckyTranslator` to generate scripts from natural language.
3. Executes the generated scripts against the sandbox.
4. Verifies the sandbox state has evolved as expected (e.g., browser opened).
"""

import unittest
import logging
from rongle_operator.sandbox.ducky_sandbox import DuckySandbox
from rongle_operator.sandbox.translator import AgenticDuckyTranslator, TranslationRequest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_evolution")

class TestDuckyEvolution(unittest.TestCase):
    def setUp(self):
        self.sandbox = DuckySandbox()
        self.translator = AgenticDuckyTranslator(backend="mock")

    def test_open_browser_flow(self):
        logger.info("=== TEST: Open Browser ===")

        # 1. Inspect Initial State
        initial_state = self.sandbox.render()
        logger.info("Initial State:\n" + initial_state)

        self.assertEqual(self.sandbox.state.active_window, "Desktop")

        # 2. Translate Intent
        request = TranslationRequest(
            intent="Open Browser and go to google.com",
            sandbox_state=initial_state,
            history=[]
        )

        script = self.translator.translate(request)
        logger.info(f"Generated Script: {script}")

        self.assertTrue(len(script) > 0, "Translator failed to generate script")

        # 3. Execute Script
        for line in script:
            self.sandbox.execute_ducky_command(line)
            # Render intermediate state for debugging
            # logger.info(self.sandbox.render())

        # 4. Verify Final State
        final_state = self.sandbox.render()
        logger.info("Final State:\n" + final_state)

        # Expect active window to be Chrome (mock translator clicks (80,80) which hits icon_browser)
        # Sandbox logic: clicking icon_browser sets active_window="Google Chrome"
        self.assertEqual(self.sandbox.state.active_window, "Google Chrome")

        # Check typed buffer contains URL
        self.assertIn("google.com", self.sandbox.state.typed_buffer)

    def test_search_interaction(self):
        logger.info("=== TEST: Search Interaction ===")

        # Pre-condition: Browser open
        # We manually simulate opening it first
        self.sandbox._trigger_element_action(self.sandbox.state.elements[1]) # Chrome Icon

        request = TranslationRequest(
            intent="search python tutorial",
            sandbox_state=self.sandbox.render(),
            history=["opened browser"]
        )

        script = self.translator.translate(request)
        logger.info(f"Generated Script: {script}")

        for line in script:
            self.sandbox.execute_ducky_command(line)

        self.assertIn("python tutorial", self.sandbox.state.typed_buffer)

if __name__ == "__main__":
    unittest.main()
