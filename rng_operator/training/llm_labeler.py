"""
LLM-Guided Labeler — Uses a VLM (Gemini) to automatically generate
bounding box annotations for UI screenshots, then stores them as
training data for the CNN.

This creates a self-improving loop:
  1. VLM analyzes a screenshot and returns UI element bounding boxes
  2. Labels are saved to a JSONL dataset
  3. The CNN trains on those labels
  4. The CNN handles fast detection; VLM is called less often

The LLM can also refine labels by comparing its output to the CNN's
predictions and correcting errors (active learning).
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# The 17 UI element classes matching the browser CNN
UI_CLASSES = [
    "button", "text_input", "link", "icon", "dropdown", "checkbox",
    "radio", "toggle", "slider", "tab", "menu_item", "image",
    "heading", "paragraph", "dialog", "toolbar", "cursor",
]

SCREEN_CLASSES = [
    "desktop", "browser", "terminal", "file_manager", "settings",
    "dialog", "login", "editor", "spreadsheet", "media", "unknown",
]


@dataclass
class BBoxLabel:
    """A single labeled bounding box."""
    x: float
    y: float
    width: float
    height: float
    class_name: str
    confidence: float = 1.0


@dataclass
class ScreenLabel:
    """Screen-type classification label."""
    class_name: str
    confidence: float = 1.0


@dataclass
class LabeledFrame:
    """A fully labeled screenshot for training."""
    image_path: str
    image_hash: str
    width: int
    height: int
    boxes: list[BBoxLabel] = field(default_factory=list)
    screen_class: ScreenLabel | None = None
    source: str = "llm"  # "llm", "human", "cnn_corrected"
    timestamp: float = 0.0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


class LLMLabeler:
    """
    Uses a VLM to generate training labels from screenshots.

    Usage::

        labeler = LLMLabeler(api_key="...", dataset_dir="training/data")
        labels = await labeler.label_frame(image_bytes, width=1920, height=1080)
        labeler.save_labels(labels)

    For active learning (CNN → LLM correction)::

        corrections = await labeler.refine_labels(
            image_bytes, cnn_predictions, width=1920, height=1080
        )
    """

    DETECTION_PROMPT = """Analyze this screenshot and identify ALL interactive UI elements.

For each element, return a JSON object with:
- "label": element type (one of: button, text_input, link, icon, dropdown, checkbox, radio, toggle, slider, tab, menu_item, image, heading, paragraph, dialog, toolbar, cursor)
- "x": left edge X coordinate (pixels from left)
- "y": top edge Y coordinate (pixels from top)
- "width": element width in pixels
- "height": element height in pixels
- "text": visible text on the element (if any)

Also classify the overall screen type as one of:
desktop, browser, terminal, file_manager, settings, dialog, login, editor, spreadsheet, media, unknown

Return ONLY valid JSON in this format:
{
  "screen_type": "browser",
  "elements": [
    {"label": "button", "x": 100, "y": 50, "width": 80, "height": 30, "text": "Submit"},
    ...
  ]
}"""

    REFINEMENT_PROMPT = """I have a CNN that detected these UI elements in the screenshot:

{cnn_predictions}

Please review and correct these detections:
1. Remove false positives (elements that don't exist)
2. Add missed elements (false negatives)
3. Fix incorrect bounding boxes or labels
4. Rate the CNN's accuracy (0-100%)

Return corrected JSON:
{{
  "accuracy_score": 75,
  "corrections": [
    {{"action": "keep", "original_index": 0}},
    {{"action": "remove", "original_index": 1, "reason": "false positive"}},
    {{"action": "fix", "original_index": 2, "label": "button", "x": 105, "y": 52, "width": 78, "height": 28}},
    {{"action": "add", "label": "link", "x": 200, "y": 300, "width": 60, "height": 20, "text": "Help"}}
  ],
  "screen_type": "browser"
}}"""

    def __init__(
        self,
        api_key: str | None = None,
        dataset_dir: str = "training/data",
        model: str = "gemini-2.0-flash",
    ) -> None:
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.dataset_dir = Path(dataset_dir)
        self.model = model
        self.dataset_dir.mkdir(parents=True, exist_ok=True)
        (self.dataset_dir / "images").mkdir(exist_ok=True)

        self._labels_path = self.dataset_dir / "labels.jsonl"
        self._stats = {"total_labeled": 0, "total_boxes": 0}

    async def label_frame(
        self,
        image_bytes: bytes,
        width: int,
        height: int,
        save_image: bool = True,
    ) -> LabeledFrame:
        """
        Send a screenshot to the VLM and get back bounding box labels.

        Parameters
        ----------
        image_bytes : bytes
            Raw JPEG/PNG image bytes.
        width, height : int
            Image dimensions.
        save_image : bool
            Whether to save the image to disk for training.

        Returns
        -------
        LabeledFrame with all detected UI elements labeled.
        """
        image_hash = hashlib.sha256(image_bytes).hexdigest()[:16]
        image_b64 = base64.b64encode(image_bytes).decode("ascii")

        # Save image
        image_path = ""
        if save_image:
            image_path = str(self.dataset_dir / "images" / f"{image_hash}.jpg")
            Path(image_path).write_bytes(image_bytes)

        # Call VLM
        try:
            response = await self._call_vlm(image_b64, self.DETECTION_PROMPT)
            parsed = self._parse_detection_response(response)
        except Exception as e:
            logger.error("VLM labeling failed: %s", e)
            return LabeledFrame(
                image_path=image_path,
                image_hash=image_hash,
                width=width,
                height=height,
                timestamp=time.time(),
            )

        boxes = []
        for elem in parsed.get("elements", []):
            cls = elem.get("label", "").lower()
            if cls not in UI_CLASSES:
                continue
            boxes.append(BBoxLabel(
                x=float(elem.get("x", 0)),
                y=float(elem.get("y", 0)),
                width=float(elem.get("width", 0)),
                height=float(elem.get("height", 0)),
                class_name=cls,
            ))

        screen_type = parsed.get("screen_type", "unknown").lower()
        if screen_type not in SCREEN_CLASSES:
            screen_type = "unknown"

        frame = LabeledFrame(
            image_path=image_path,
            image_hash=image_hash,
            width=width,
            height=height,
            boxes=boxes,
            screen_class=ScreenLabel(class_name=screen_type),
            source="llm",
            timestamp=time.time(),
        )

        self._stats["total_labeled"] += 1
        self._stats["total_boxes"] += len(boxes)
        logger.info(
            "Labeled frame %s: %d elements, screen=%s",
            image_hash, len(boxes), screen_type,
        )
        return frame

    async def refine_labels(
        self,
        image_bytes: bytes,
        cnn_predictions: list[dict],
        width: int,
        height: int,
    ) -> LabeledFrame:
        """
        Active learning: send CNN predictions to VLM for correction.

        The VLM reviews CNN output and provides corrections, creating
        higher-quality training data from the CNN's mistakes.
        """
        image_hash = hashlib.sha256(image_bytes).hexdigest()[:16]
        image_b64 = base64.b64encode(image_bytes).decode("ascii")

        pred_str = json.dumps(cnn_predictions, indent=2)
        prompt = self.REFINEMENT_PROMPT.format(cnn_predictions=pred_str)

        try:
            response = await self._call_vlm(image_b64, prompt)
            parsed = self._parse_detection_response(response)
        except Exception as e:
            logger.error("VLM refinement failed: %s", e)
            # Return CNN predictions as-is
            boxes = [
                BBoxLabel(
                    x=p.get("x", 0), y=p.get("y", 0),
                    width=p.get("width", 0), height=p.get("height", 0),
                    class_name=p.get("class", "button"),
                )
                for p in cnn_predictions
            ]
            return LabeledFrame(
                image_path="", image_hash=image_hash,
                width=width, height=height, boxes=boxes,
                source="cnn", timestamp=time.time(),
            )

        # Apply corrections
        boxes = []
        corrections = parsed.get("corrections", [])
        for correction in corrections:
            action = correction.get("action", "keep")

            if action == "keep":
                idx = correction.get("original_index", -1)
                if 0 <= idx < len(cnn_predictions):
                    p = cnn_predictions[idx]
                    boxes.append(BBoxLabel(
                        x=p.get("x", 0), y=p.get("y", 0),
                        width=p.get("width", 0), height=p.get("height", 0),
                        class_name=p.get("class", "button"),
                    ))

            elif action == "fix":
                boxes.append(BBoxLabel(
                    x=float(correction.get("x", 0)),
                    y=float(correction.get("y", 0)),
                    width=float(correction.get("width", 0)),
                    height=float(correction.get("height", 0)),
                    class_name=correction.get("label", "button"),
                ))

            elif action == "add":
                boxes.append(BBoxLabel(
                    x=float(correction.get("x", 0)),
                    y=float(correction.get("y", 0)),
                    width=float(correction.get("width", 0)),
                    height=float(correction.get("height", 0)),
                    class_name=correction.get("label", "button"),
                ))
            # "remove" → just skip

        screen_type = parsed.get("screen_type", "unknown")
        accuracy = parsed.get("accuracy_score", 0)

        frame = LabeledFrame(
            image_path="", image_hash=image_hash,
            width=width, height=height, boxes=boxes,
            screen_class=ScreenLabel(class_name=screen_type),
            source="cnn_corrected",
            timestamp=time.time(),
            metadata={"cnn_accuracy": accuracy},
        )

        logger.info(
            "Refined %d CNN predictions → %d corrected labels (accuracy: %d%%)",
            len(cnn_predictions), len(boxes), accuracy,
        )
        return frame

    def save_labels(self, frame: LabeledFrame) -> None:
        """Append a labeled frame to the JSONL dataset."""
        with open(self._labels_path, "a") as f:
            f.write(json.dumps(frame.to_dict(), separators=(",", ":")) + "\n")

    def load_dataset(self) -> list[LabeledFrame]:
        """Load all labeled frames from the JSONL dataset."""
        frames = []
        if not self._labels_path.exists():
            return frames

        with open(self._labels_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                boxes = [BBoxLabel(**b) for b in data.get("boxes", [])]
                sc = data.get("screen_class")
                screen_class = ScreenLabel(**sc) if sc else None
                frames.append(LabeledFrame(
                    image_path=data["image_path"],
                    image_hash=data["image_hash"],
                    width=data["width"],
                    height=data["height"],
                    boxes=boxes,
                    screen_class=screen_class,
                    source=data.get("source", "llm"),
                    timestamp=data.get("timestamp", 0),
                    metadata=data.get("metadata", {}),
                ))
        return frames

    @property
    def stats(self) -> dict:
        return {**self._stats}

    # ------------------------------------------------------------------
    # VLM communication
    # ------------------------------------------------------------------
    async def _call_vlm(self, image_b64: str, prompt: str) -> str:
        """Call the Gemini VLM API with an image and prompt."""
        try:
            from google import genai
        except ImportError:
            # Fallback: use httpx directly
            return await self._call_vlm_http(image_b64, prompt)

        client = genai.Client(api_key=self.api_key)
        response = await client.aio.models.generate_content(
            model=self.model,
            contents=[
                genai.types.Part.from_bytes(
                    data=base64.b64decode(image_b64),
                    mime_type="image/jpeg",
                ),
                prompt,
            ],
        )
        return response.text or ""

    async def _call_vlm_http(self, image_b64: str, prompt: str) -> str:
        """Fallback HTTP call to Gemini API."""
        import httpx

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        payload = {
            "contents": [{
                "parts": [
                    {"inline_data": {"mime_type": "image/jpeg", "data": image_b64}},
                    {"text": prompt},
                ]
            }]
        }
        headers = {"Content-Type": "application/json"}
        params = {"key": self.api_key}

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, json=payload, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()

        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text", "")
        return ""

    def _parse_detection_response(self, text: str) -> dict:
        """Parse VLM response, handling markdown fences and malformed JSON."""
        text = text.strip()

        # Strip markdown code fences
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first and last fence lines
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON object in the text
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass

        logger.warning("Failed to parse VLM response as JSON")
        return {}
