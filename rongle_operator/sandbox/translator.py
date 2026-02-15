"""
Agentic Ducky Translator

This module integrates with LLMs (e.g., Claude, Gemini) to translate natural language
intent into advanced Ducky Script, optimized for the current sandbox environment.
"""

from typing import List, Dict, Any, Optional
import os
import json
import logging
import re
from dataclasses import dataclass

logger = logging.getLogger("translator")

@dataclass
class TranslationRequest:
    intent: str
    sandbox_state: str  # Text description of the sandbox state
    history: List[str]  # Previous actions

class AgenticDuckyTranslator:
    def __init__(self, backend="mock", api_key: Optional[str] = None):
        self.backend = backend
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")

        if self.backend == "gemini":
            if not self.api_key:
                logger.warning("Gemini backend requested but no API Key found. Falling back to mock.")
                self.backend = "mock"
            else:
                try:
                    from google import genai
                    self.client = genai.Client(api_key=self.api_key)
                    self.model_id = "gemini-2.0-flash"
                except ImportError:
                    logger.error("google-genai library not installed. Falling back to mock.")
                    self.backend = "mock"

    def translate(self, request: TranslationRequest) -> List[str]:
        """
        Convert natural language intent to Ducky Script.
        """
        logger.info(f"Translating intent: '{request.intent}' via {self.backend}")

        # Construct Prompt for the LLM
        prompt = self._build_prompt(request)

        # Call LLM
        if self.backend == "mock":
            return self._mock_translation(request)
        else:
            return self._call_llm(prompt)

    def _build_prompt(self, request: TranslationRequest) -> str:
        return f"""
        You are an expert Ducky Script automation engineer.
        Your task is to generate Ducky Script commands to achieve the user's intent.

        System Context:
        - Screen Size: 1920x1080 (assumed unless specified in state)
        - Available Commands: MOUSE_MOVE x y, MOUSE_CLICK LEFT/RIGHT, STRING text, DELAY ms, ENTER, ALT F4

        Current System State:
        {request.sandbox_state}

        Action History:
        {json.dumps(request.history, indent=2)}

        User Intent: "{request.intent}"

        Instructions:
        1. Analyze the 'Current System State' to find coordinates of UI elements mentioned in the intent.
        2. Generate a sequence of Ducky Script commands.
        3. Output ONLY the raw Ducky Script commands, one per line. No markdown formatting, no explanations.
        """

    def _mock_translation(self, request: TranslationRequest) -> List[str]:
        """Simple rule-based mock for testing without API keys."""
        intent = request.intent.lower()

        if "open browser" in intent:
            return [
                "MOUSE_MOVE 80 80", # Center of icon (50,50 60x60) -> 80,80
                "MOUSE_CLICK LEFT",
                "DELAY 1000",
                "STRING google.com",
                "ENTER"
            ]
        elif "search" in intent:
             return [
                 "MOUSE_MOVE 500 215", # Search bar
                 "MOUSE_CLICK LEFT",
                 "STRING " + intent.replace("search ", ""),
                 "ENTER"
             ]
        elif "close" in intent:
             return ["ALT F4"]

        return []

    def _call_llm(self, prompt: str) -> List[str]:
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt
            )

            raw_text = response.text

            # Clean up response (remove markdown code blocks if present)
            # The prompt asks for raw text, but LLMs often add ```ducky ... ```
            cleaned_lines = []

            # Simple regex to strip code blocks
            code_block_pattern = r"```(?:ducky)?\n(.*?)```"
            match = re.search(code_block_pattern, raw_text, re.DOTALL)
            if match:
                raw_text = match.group(1)

            for line in raw_text.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    cleaned_lines.append(line)

            return cleaned_lines

        except Exception as e:
            logger.error(f"LLM Call Failed: {e}")
            return []
