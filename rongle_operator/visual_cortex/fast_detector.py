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

import cv2
import numpy as np

logger = logging.getLogger(__name__)

try:
    import onnxruntime as ort
    HAS_ONNX = True
except ImportError:
    HAS_ONNX = False


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
        self._session = None

        if model_path and HAS_ONNX:
            try:
                self._session = ort.InferenceSession(model_path)
                logger.info("FastDetector initialized with ONNX model: %s", model_path)
            except Exception as e:
                logger.error("Failed to load ONNX model: %s", e)
        else:
            if model_path and not HAS_ONNX:
                logger.warning("ONNX Runtime not available, falling back to stub.")
            logger.warning("FastDetector running in stub mode (no model)")

    def detect(self, frame: np.ndarray) -> list[FastRegion]:
        """
        Run detection on the frame.
        """
        if self._session is None:
            return []

        # ONNX Inference Logic (MobileNet-SSD specific preprocessing)
        try:
            # 1. Preprocess (300x300, normalize to -1..1 or 0..1 depending on model)
            # Assuming standard MobileNet-SSD input: 1x3x300x300
            input_shape = (300, 300)
            img = cv2.resize(frame, input_shape)
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            img = img.transpose(2, 0, 1) # HWC -> CHW
            img = np.expand_dims(img, axis=0).astype(np.float32)

            # Normalize (approximate, model specific)
            img = (img - 127.5) / 127.5

            # 2. Run inference
            input_name = self._session.get_inputs()[0].name
            # Output format depends on model. Usually [boxes, classes, scores]
            outputs = self._session.run(None, {input_name: img})

            # 3. Postprocess (Placeholder for standard SSD output decoding)
            # This part is highly model-specific.
            # We assume output[0] is boxes [N, 4] and output[1] is scores [N]
            # Since we don't have the model file to verify output shape,
            # we wrap this in a try-except to avoid crashing the agent loop.

            # Returning empty for now even if inference runs, as we can't map
            # output tensors without knowing the exact model export format.
            # But the ARCHITECTURE is now in place.
            return []

        except Exception as e:
            logger.error("Inference failed: %s", e)
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
