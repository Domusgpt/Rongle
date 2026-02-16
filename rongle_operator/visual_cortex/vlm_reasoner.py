"""
VLMReasoner — Vision-Language Model interface for high-level UI understanding.

Sub-Task B: Accepts a natural-language query (e.g., "Find the 'Connect' button")
and a screenshot frame, then returns bounding boxes of identified UI elements.

Supports two backends:
  1. Local VLM (e.g., SmolVLM, PaliGemma via Hugging Face Transformers)
  2. Remote API (Google Gemini, OpenAI GPT-4V, Anthropic Claude)
"""

from __future__ import annotations

import json
import base64
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class UIElement:
    """A detected UI element with bounding box and label."""
    label: str
    x: int           # top-left X
    y: int           # top-left Y
    width: int
    height: int
    confidence: float = 0.0
    element_type: str = ""  # "button", "input", "link", "text", etc.

    @property
    def center(self) -> tuple[int, int]:
        return self.x + self.width // 2, self.y + self.height // 2

    @property
    def bbox(self) -> tuple[int, int, int, int]:
        return self.x, self.y, self.x + self.width, self.y + self.height


@dataclass
class VLMResponse:
    """Structured response from the VLM."""
    elements: list[UIElement] = field(default_factory=list)
    description: str = ""
    raw_response: str = ""
    latency_ms: float = 0.0


# ---------------------------------------------------------------------------
# Abstract backend
# ---------------------------------------------------------------------------
class VLMBackend(ABC):
    """Abstract interface for VLM inference backends."""

    @abstractmethod
    def query(self, frame: np.ndarray, prompt: str) -> VLMResponse:
        """Send a frame + prompt and return structured UI element data."""
        ...


# ---------------------------------------------------------------------------
# Backend: Google Gemini API
# ---------------------------------------------------------------------------
class GeminiBackend(VLMBackend):
    """
    Uses Google Gemini (gemini-2.0-flash or similar) for vision reasoning.

    Requires the ``google-genai`` package and a valid API key.
    """

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash") -> None:
        self.api_key = api_key
        self.model = model
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            from google import genai  # type: ignore[import-untyped]
            self._client = genai.Client(api_key=self.api_key)

    def query(self, frame: np.ndarray, prompt: str) -> VLMResponse:
        import time
        self._ensure_client()
        from google.genai import types  # type: ignore[import-untyped]

        t0 = time.time()

        # Encode frame to JPEG
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            raise RuntimeError("Failed to encode frame for VLM")

        image_data = base64.b64encode(buf.tobytes()).decode("utf-8")

        system_prompt = (
            "You are a UI element detector. Given a screenshot, identify all UI elements "
            "matching the user's query. Return a JSON array of objects with keys: "
            '"label", "x", "y", "width", "height", "confidence", "element_type". '
            "Coordinates are in pixels relative to the image top-left corner. "
            "Return ONLY the JSON array, no other text."
        )

        response = self._client.models.generate_content(
            model=self.model,
            contents=[
                types.Content(parts=[
                    types.Part(text=f"{system_prompt}\n\nUser query: {prompt}"),
                    types.Part(inline_data=types.Blob(
                        mime_type="image/jpeg",
                        data=base64.b64decode(image_data),
                    )),
                ]),
            ],
        )

        latency = (time.time() - t0) * 1000
        raw_text = response.text if response.text else ""

        return VLMResponse(
            elements=self._parse_elements(raw_text),
            description=raw_text,
            raw_response=raw_text,
            latency_ms=latency,
        )

    @staticmethod
    def _parse_elements(raw: str) -> list[UIElement]:
        """Parse JSON array from VLM response text."""
        # Extract JSON from possible markdown code fences
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            return []
        try:
            items = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []
        elements = []
        for item in items:
            if isinstance(item, dict):
                elements.append(UIElement(
                    label=item.get("label", ""),
                    x=int(item.get("x", 0)),
                    y=int(item.get("y", 0)),
                    width=int(item.get("width", 0)),
                    height=int(item.get("height", 0)),
                    confidence=float(item.get("confidence", 0.0)),
                    element_type=item.get("element_type", ""),
                ))
        return elements


# ---------------------------------------------------------------------------
# Backend: Local HuggingFace model
# ---------------------------------------------------------------------------
class LocalVLMBackend(VLMBackend):
    """
    Runs a local Vision-Language Model via HuggingFace Transformers.

    Suitable for small models like SmolVLM-256M or PaliGemma-3B that can
    run on the Pi Zero 2 W (with quantization) or on a connected GPU node.
    """

    def __init__(
        self,
        model_id: str = "HuggingFaceTB/SmolVLM-256M-Instruct",
        device: str = "cpu",
    ) -> None:
        self.model_id = model_id
        self.device = device
        self._model = None
        self._processor = None

    def _ensure_model(self):
        if self._model is not None:
            return
        try:
            from transformers import AutoProcessor, AutoModelForVision2Seq  # type: ignore
            self._processor = AutoProcessor.from_pretrained(self.model_id)
            self._model = AutoModelForVision2Seq.from_pretrained(self.model_id)
            self._model = self._model.to(self.device)
            logger.info("Loaded local VLM: %s on %s", self.model_id, self.device)
        except Exception as exc:
            logger.error("Failed to load local VLM: %s", exc)
            raise

    def query(self, frame: np.ndarray, prompt: str) -> VLMResponse:
        import time
        from PIL import Image  # type: ignore

        self._ensure_model()
        t0 = time.time()

        # Convert BGR (OpenCV) to RGB (PIL)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb)

        # Chat template handling for SmolVLM
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image"},
                    {"type": "text", "text": f"Identify all UI elements matching: {prompt}\nReturn JSON array with keys: label, x, y, width, height, confidence, element_type."}
                ]
            },
        ]

        # Apply chat template
        prompt_text = self._processor.apply_chat_template(messages, add_generation_prompt=True)

        inputs = self._processor(
            text=prompt_text,
            images=pil_image,
            return_tensors="pt",
        ).to(self.device)

        import torch
        with torch.no_grad():
            generated_ids = self._model.generate(**inputs, max_new_tokens=512)

        raw_text = self._processor.batch_decode(
            generated_ids, skip_special_tokens=True
        )[0]

        latency = (time.time() - t0) * 1000

        return VLMResponse(
            elements=GeminiBackend._parse_elements(raw_text),
            description=raw_text,
            raw_response=raw_text,
            latency_ms=latency,
        )


# ---------------------------------------------------------------------------
# Composite Reasoner
# ---------------------------------------------------------------------------
class VLMReasoner:
    """
    High-level reasoner that dispatches to a configured VLM backend.

    Usage::

        reasoner = VLMReasoner(backend=GeminiBackend(api_key="..."))
        elements = reasoner.find_element(frame, "the Connect button")
    """

    def __init__(self, backend: VLMBackend) -> None:
        self.backend = backend

    def find_element(self, frame: np.ndarray, description: str) -> UIElement | None:
        """Find a single UI element matching the natural-language description."""
        response = self.backend.query(frame, description)
        if not response.elements:
            logger.info("VLM found no elements for: %s", description)
            return None
        # Return highest-confidence match
        best = max(response.elements, key=lambda e: e.confidence)
        logger.info(
            "VLM found '%s' at (%d, %d) conf=%.2f in %.0fms",
            best.label, best.x, best.y, best.confidence, response.latency_ms,
        )
        return best

    def find_all_elements(self, frame: np.ndarray, description: str) -> list[UIElement]:
        """Find all UI elements matching the description."""
        response = self.backend.query(frame, description)
        return response.elements

    def describe_screen(self, frame: np.ndarray) -> str:
        """Get a natural-language description of the current screen state."""
        response = self.backend.query(frame, "Describe what is shown on this screen.")
        return response.description
