"""
FastDetector — Stub for local CNN-based "Reflex" layer.

In production, this would load an ONNX or TFLite model (MobileNet-SSD)
to perform ultra-low-latency (<30ms) detection of UI elements.

For now, it acts as a stub or simple template matcher to allow
architectural development of the Foveated Rendering pipeline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class FastRegion:
    """A region of interest identified by the fast detector."""
    x: int
    y: int
    width: int
    height: int
    score: float
    label: str

    @property
    def area(self) -> int:
        return self.width * self.height


class FastDetector:
    """
    Placeholder for local CNN inference.
    """

    def __init__(self, model_path: str | None = None) -> None:
        self.model_path = model_path
        if model_path:
            logger.info("FastDetector initialized with model: %s", model_path)
        else:
            logger.warning("FastDetector running in stub mode (no model)")

    def detect(self, frame: np.ndarray) -> list[FastRegion]:
        """
        Run detection on the frame.

        Returns a list of regions that might be interactive UI elements.
        """
        # In a real implementation:
        # 1. Preprocess frame (resize, normalize)
        # 2. Run inference (ONNX Runtime / TFLite)
        # 3. Postprocess (NMS, decode boxes)

        # Stub: Return an empty list or a dummy region for testing
        return []

    def get_foveal_crop(self, frame: np.ndarray, regions: list[FastRegion], margin: int = 50) -> tuple[np.ndarray, int, int] | None:
        """
        Calculate a bounding box that encompasses all interesting regions,
        plus a margin, and return the cropped image + offset.

        Returns: (cropped_image, offset_x, offset_y)
        """
        if not regions:
            return None

        # Find extents
        min_x = min(r.x for r in regions)
        min_y = min(r.y for r in regions)
        max_x = max(r.x + r.width for r in regions)
        max_y = max(r.y + r.height for r in regions)

        # Apply margin
        h, w = frame.shape[:2]
        x1 = max(0, min_x - margin)
        y1 = max(0, min_y - margin)
        x2 = min(w, max_x + margin)
        y2 = min(h, max_y + margin)

        if x2 <= x1 or y2 <= y1:
            return None

        crop = frame[y1:y2, x1:x2]
        return crop, x1, y1
