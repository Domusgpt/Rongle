"""Tests for CNN postprocessor — NMS, anchor generation, softmax, box decoding."""

import math
import pytest


# ---------------------------------------------------------------------------
# Inline implementations for testing (mirrors services/cnn/postprocessor.ts)
# These are Python equivalents of the TypeScript implementations.
# ---------------------------------------------------------------------------

def sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    ex = math.exp(x)
    return ex / (1.0 + ex)


def softmax(logits: list[float]) -> list[float]:
    max_val = max(logits)
    exps = [math.exp(x - max_val) for x in logits]
    total = sum(exps)
    return [e / total for e in exps]


def iou(a: dict, b: dict) -> float:
    """Intersection over Union for two boxes {x, y, width, height}."""
    x1 = max(a["x"], b["x"])
    y1 = max(a["y"], b["y"])
    x2 = min(a["x"] + a["width"], b["x"] + b["width"])
    y2 = min(a["y"] + a["height"], b["y"] + b["height"])

    inter = max(0, x2 - x1) * max(0, y2 - y1)
    area_a = a["width"] * a["height"]
    area_b = b["width"] * b["height"]
    union = area_a + area_b - inter

    return inter / union if union > 0 else 0


def nms(detections: list[dict], iou_threshold: float = 0.45) -> list[dict]:
    """Non-Maximum Suppression: keep highest-confidence, remove overlapping."""
    sorted_dets = sorted(detections, key=lambda d: d["confidence"], reverse=True)
    keep = []

    for det in sorted_dets:
        suppressed = False
        for kept in keep:
            if iou(det["bbox"], kept["bbox"]) > iou_threshold:
                suppressed = True
                break
        if not suppressed:
            keep.append(det)

    return keep


def generate_anchors(
    feature_size: int,
    input_size: int,
    aspect_ratios: list[float],
) -> list[dict]:
    """Generate anchor boxes for one feature map scale."""
    stride = input_size / feature_size
    anchors = []
    for y in range(feature_size):
        for x in range(feature_size):
            cx = (x + 0.5) * stride
            cy = (y + 0.5) * stride
            for ar in aspect_ratios:
                w = stride * math.sqrt(ar)
                h = stride / math.sqrt(ar)
                anchors.append({"cx": cx, "cy": cy, "w": w, "h": h})
    return anchors


def decode_box(
    anchor: dict,
    tx: float, ty: float, tw: float, th: float,
) -> dict:
    """Decode SSD-style box offsets relative to anchor."""
    cx = anchor["cx"] + tx * anchor["w"]
    cy = anchor["cy"] + ty * anchor["h"]
    w = anchor["w"] * math.exp(tw)
    h = anchor["h"] * math.exp(th)
    return {
        "x": cx - w / 2,
        "y": cy - h / 2,
        "width": w,
        "height": h,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestSigmoid:
    def test_zero(self):
        assert abs(sigmoid(0) - 0.5) < 1e-10

    def test_large_positive(self):
        assert sigmoid(100) > 0.999

    def test_large_negative(self):
        assert sigmoid(-100) < 0.001

    def test_symmetry(self):
        assert abs(sigmoid(2) + sigmoid(-2) - 1.0) < 1e-10

    def test_range(self):
        for x in [-10, -1, 0, 1, 10]:
            s = sigmoid(x)
            assert 0 <= s <= 1


class TestSoftmax:
    def test_sums_to_one(self):
        probs = softmax([1.0, 2.0, 3.0])
        assert abs(sum(probs) - 1.0) < 1e-10

    def test_highest_logit_highest_prob(self):
        probs = softmax([1.0, 5.0, 2.0])
        assert probs[1] > probs[0]
        assert probs[1] > probs[2]

    def test_uniform_input(self):
        probs = softmax([1.0, 1.0, 1.0])
        for p in probs:
            assert abs(p - 1 / 3) < 1e-10

    def test_large_values_no_overflow(self):
        probs = softmax([1000, 1001, 1002])
        assert abs(sum(probs) - 1.0) < 1e-10

    def test_negative_values(self):
        probs = softmax([-1.0, -2.0, -3.0])
        assert abs(sum(probs) - 1.0) < 1e-10
        assert probs[0] > probs[1] > probs[2]


class TestIoU:
    def test_identical_boxes(self):
        a = {"x": 0, "y": 0, "width": 100, "height": 100}
        assert abs(iou(a, a) - 1.0) < 1e-10

    def test_no_overlap(self):
        a = {"x": 0, "y": 0, "width": 50, "height": 50}
        b = {"x": 100, "y": 100, "width": 50, "height": 50}
        assert iou(a, b) == 0

    def test_partial_overlap(self):
        a = {"x": 0, "y": 0, "width": 100, "height": 100}
        b = {"x": 50, "y": 50, "width": 100, "height": 100}
        # Intersection: 50x50 = 2500
        # Union: 10000 + 10000 - 2500 = 17500
        expected = 2500 / 17500
        assert abs(iou(a, b) - expected) < 1e-10

    def test_contained_box(self):
        outer = {"x": 0, "y": 0, "width": 200, "height": 200}
        inner = {"x": 50, "y": 50, "width": 50, "height": 50}
        # Intersection = 2500, Union = 40000 + 2500 - 2500 = 40000
        assert abs(iou(outer, inner) - 2500 / 40000) < 1e-10

    def test_zero_area(self):
        a = {"x": 0, "y": 0, "width": 0, "height": 0}
        b = {"x": 0, "y": 0, "width": 100, "height": 100}
        assert iou(a, b) == 0


class TestNMS:
    def test_no_overlap_keeps_all(self):
        dets = [
            {"bbox": {"x": 0, "y": 0, "width": 50, "height": 50}, "confidence": 0.9},
            {"bbox": {"x": 200, "y": 200, "width": 50, "height": 50}, "confidence": 0.8},
        ]
        result = nms(dets, iou_threshold=0.5)
        assert len(result) == 2

    def test_overlapping_suppresses_lower(self):
        dets = [
            {"bbox": {"x": 0, "y": 0, "width": 100, "height": 100}, "confidence": 0.9},
            {"bbox": {"x": 10, "y": 10, "width": 100, "height": 100}, "confidence": 0.7},
        ]
        result = nms(dets, iou_threshold=0.5)
        assert len(result) == 1
        assert result[0]["confidence"] == 0.9

    def test_keeps_highest_confidence(self):
        dets = [
            {"bbox": {"x": 0, "y": 0, "width": 100, "height": 100}, "confidence": 0.5},
            {"bbox": {"x": 5, "y": 5, "width": 100, "height": 100}, "confidence": 0.95},
            {"bbox": {"x": 10, "y": 10, "width": 100, "height": 100}, "confidence": 0.7},
        ]
        result = nms(dets, iou_threshold=0.5)
        assert result[0]["confidence"] == 0.95

    def test_empty_input(self):
        assert nms([], iou_threshold=0.5) == []

    def test_single_detection(self):
        dets = [{"bbox": {"x": 0, "y": 0, "width": 50, "height": 50}, "confidence": 0.9}]
        assert len(nms(dets)) == 1

    def test_strict_threshold_keeps_more(self):
        """Lower IoU threshold = more aggressive suppression."""
        dets = [
            {"bbox": {"x": 0, "y": 0, "width": 100, "height": 100}, "confidence": 0.9},
            {"bbox": {"x": 30, "y": 30, "width": 100, "height": 100}, "confidence": 0.8},
        ]
        # With high threshold, less suppression
        result_lenient = nms(dets, iou_threshold=0.9)
        result_strict = nms(dets, iou_threshold=0.1)
        assert len(result_lenient) >= len(result_strict)


class TestAnchorGeneration:
    def test_anchor_count(self):
        anchors = generate_anchors(10, 320, [0.5, 1.0, 2.0])
        assert len(anchors) == 10 * 10 * 3  # 300

    def test_anchor_centers_in_range(self):
        anchors = generate_anchors(10, 320, [1.0])
        for a in anchors:
            assert 0 < a["cx"] < 320
            assert 0 < a["cy"] < 320

    def test_anchor_spacing(self):
        anchors = generate_anchors(4, 320, [1.0])
        # Stride should be 80
        assert abs(anchors[0]["cx"] - 40) < 1e-5  # first center
        assert abs(anchors[1]["cx"] - 120) < 1e-5  # second center

    def test_multi_scale(self):
        a80 = generate_anchors(80, 320, [0.5, 1.0, 2.0])
        a10 = generate_anchors(10, 320, [0.5, 1.0, 2.0])
        assert len(a80) == 19200
        assert len(a10) == 300
        # Larger feature map = smaller anchors
        assert a80[0]["w"] < a10[0]["w"]


class TestBoxDecoding:
    def test_zero_offsets_returns_anchor(self):
        anchor = {"cx": 160, "cy": 160, "w": 32, "h": 32}
        box = decode_box(anchor, 0, 0, 0, 0)
        assert abs(box["x"] - 144) < 1e-5
        assert abs(box["y"] - 144) < 1e-5
        assert abs(box["width"] - 32) < 1e-5
        assert abs(box["height"] - 32) < 1e-5

    def test_positive_offset_shifts_box(self):
        anchor = {"cx": 100, "cy": 100, "w": 50, "h": 50}
        box = decode_box(anchor, 0.5, 0.5, 0, 0)
        # cx = 100 + 0.5*50 = 125
        assert abs(box["x"] + box["width"] / 2 - 125) < 1e-5

    def test_scale_offset(self):
        anchor = {"cx": 100, "cy": 100, "w": 50, "h": 50}
        box = decode_box(anchor, 0, 0, math.log(2), 0)
        # w = 50 * exp(log(2)) = 100
        assert abs(box["width"] - 100) < 1e-5
        assert abs(box["height"] - 50) < 1e-5
