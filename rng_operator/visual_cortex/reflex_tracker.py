"""
ReflexTracker — Fast feedback loop for mouse cursor tracking.

Sub-Task A: Uses lightweight computer vision to detect and track the
mouse cursor coordinates (x, y) in real-time from the captured HDMI feed.

Two strategies are provided:
  1. Template matching (OpenCV) — fast, works with known cursor images.
  2. YOLO-based detection — more robust, handles varying cursor styles.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class CursorDetection:
    """Result of cursor detection on a single frame."""
    x: int
    y: int
    confidence: float
    method: str  # "template" or "yolo"


class ReflexTracker:
    """
    Detects the mouse cursor position in HDMI-captured frames.

    Parameters
    ----------
    cursor_templates_dir : str | Path
        Directory containing cursor template images (PNG, with alpha).
        Templates are matched against each frame at multiple scales.
    yolo_model_path : str | Path | None
        Optional path to a YOLO/ONNX model fine-tuned for cursor detection.
        If provided and loadable, YOLO takes priority over template matching.
    template_threshold : float
        Minimum confidence for template match to be accepted.
    """

    def __init__(
        self,
        cursor_templates_dir: str | Path = "assets/cursors",
        yolo_model_path: str | Path | None = None,
        template_threshold: float = 0.70,
    ) -> None:
        self.cursor_templates_dir = Path(cursor_templates_dir)
        self.template_threshold = template_threshold
        self._templates: list[np.ndarray] = []
        self._yolo_net: cv2.dnn.Net | None = None

        self._load_templates()
        if yolo_model_path:
            self._load_yolo(Path(yolo_model_path))

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------
    def _load_templates(self) -> None:
        """Load cursor template images from disk."""
        if not self.cursor_templates_dir.exists():
            logger.warning(
                "Cursor templates directory not found: %s",
                self.cursor_templates_dir,
            )
            # Synthesize a default arrow cursor template (white arrow, 16x20)
            self._templates.append(self._synthesize_default_cursor())
            return

        for path in sorted(self.cursor_templates_dir.glob("*.png")):
            img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                self._templates.append(img)
                logger.debug("Loaded cursor template: %s", path.name)

        if not self._templates:
            self._templates.append(self._synthesize_default_cursor())

    def _load_yolo(self, model_path: Path) -> None:
        """Load a YOLO/ONNX model for cursor detection."""
        if not model_path.exists():
            logger.warning("YOLO model not found: %s", model_path)
            return
        try:
            self._yolo_net = cv2.dnn.readNetFromONNX(str(model_path))
            logger.info("Loaded YOLO cursor detector: %s", model_path)
        except cv2.error as exc:
            logger.warning("Failed to load YOLO model: %s", exc)

    @staticmethod
    def _synthesize_default_cursor() -> np.ndarray:
        """Create a synthetic white-arrow cursor template for fallback."""
        cursor = np.zeros((20, 16), dtype=np.uint8)
        pts = np.array([
            [1, 0], [1, 16], [5, 12], [8, 18], [10, 17], [7, 11], [12, 11], [1, 0]
        ], dtype=np.int32)
        cv2.fillPoly(cursor, [pts], 255)
        return cursor

    # ------------------------------------------------------------------
    # Detection — public API
    # ------------------------------------------------------------------
    def detect(self, frame: np.ndarray) -> CursorDetection | None:
        """
        Detect cursor position in a BGR frame.

        Tries YOLO first (if available), then falls back to template matching.
        Returns None if no cursor is found above the confidence threshold.
        """
        if self._yolo_net is not None:
            result = self._detect_yolo(frame)
            if result is not None:
                return result

        return self._detect_template(frame)

    # ------------------------------------------------------------------
    # Strategy 1: Template matching
    # ------------------------------------------------------------------
    def _detect_template(self, frame: np.ndarray) -> CursorDetection | None:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame

        best_val = 0.0
        best_loc = (0, 0)
        best_template_shape = (0, 0)

        for template in self._templates:
            # Multi-scale matching
            for scale in (1.0, 0.75, 1.25, 0.5, 1.5):
                th, tw = template.shape[:2]
                new_w = max(4, int(tw * scale))
                new_h = max(4, int(th * scale))

                if new_w >= gray.shape[1] or new_h >= gray.shape[0]:
                    continue

                scaled = cv2.resize(template, (new_w, new_h))
                result = cv2.matchTemplate(gray, scaled, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(result)

                if max_val > best_val:
                    best_val = max_val
                    best_loc = max_loc
                    best_template_shape = (new_h, new_w)

        if best_val < self.template_threshold:
            return None

        # Return the center of the matched region
        cx = best_loc[0] + best_template_shape[1] // 2
        cy = best_loc[1] + best_template_shape[0] // 2

        return CursorDetection(
            x=cx, y=cy, confidence=float(best_val), method="template"
        )

    # ------------------------------------------------------------------
    # Strategy 2: YOLO inference
    # ------------------------------------------------------------------
    def _detect_yolo(self, frame: np.ndarray) -> CursorDetection | None:
        if self._yolo_net is None:
            return None

        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(
            frame, scalefactor=1 / 255.0, size=(640, 640),
            swapRB=True, crop=False,
        )
        self._yolo_net.setInput(blob)

        try:
            outputs = self._yolo_net.forward()
        except cv2.error as exc:
            logger.warning("YOLO inference failed: %s", exc)
            return None

        # Parse YOLO output — assume single-class (cursor) detection
        # Output shape: (1, N, 5+num_classes) or (1, N, 5)
        if outputs.ndim == 3:
            detections = outputs[0]
        else:
            return None

        best_conf = 0.0
        best_box = None

        for det in detections:
            conf = float(det[4])
            if conf > best_conf:
                best_conf = conf
                best_box = det[:4]

        if best_box is None or best_conf < self.template_threshold:
            return None

        cx = int(best_box[0] * w / 640)
        cy = int(best_box[1] * h / 640)

        return CursorDetection(x=cx, y=cy, confidence=best_conf, method="yolo")
