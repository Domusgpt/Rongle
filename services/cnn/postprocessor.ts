// ---------------------------------------------------------------------------
// Postprocessor — Non-Maximum Suppression, box decoding, confidence filtering.
// ---------------------------------------------------------------------------

import type { BBox, Detection, UIElementClass, Anchor } from './types';
import { UI_CLASSES } from './types';

/**
 * Decode SSD-style raw model output into Detection objects.
 *
 * rawBoxes: Float32Array of shape [numAnchors, 4] — (cx_offset, cy_offset, w_offset, h_offset)
 * rawScores: Float32Array of shape [numAnchors, numClasses + 1] — (objectness, class0, class1, ...)
 * anchors: pre-computed anchor boxes
 * imageWidth/imageHeight: original image dimensions for coordinate scaling
 */
export function decodeDetections(
  rawBoxes: Float32Array,
  rawScores: Float32Array,
  anchors: Anchor[],
  imageWidth: number,
  imageHeight: number,
  confidenceThreshold: number,
): Detection[] {
  const numClasses = UI_CLASSES.length;
  const detections: Detection[] = [];

  for (let i = 0; i < anchors.length; i++) {
    const scoreOffset = i * (numClasses + 1);
    const objectness = sigmoid(rawScores[scoreOffset]);

    if (objectness < confidenceThreshold) continue;

    // Find best class
    let bestClass = 0;
    let bestScore = -Infinity;
    for (let c = 0; c < numClasses; c++) {
      const score = rawScores[scoreOffset + 1 + c];
      if (score > bestScore) {
        bestScore = score;
        bestClass = c;
      }
    }

    const classConf = objectness * sigmoid(bestScore);
    if (classConf < confidenceThreshold) continue;

    // Decode box offsets relative to anchor
    const boxOffset = i * 4;
    const cx = anchors[i].cx + rawBoxes[boxOffset] * anchors[i].w;
    const cy = anchors[i].cy + rawBoxes[boxOffset + 1] * anchors[i].h;
    const w = anchors[i].w * Math.exp(rawBoxes[boxOffset + 2]);
    const h = anchors[i].h * Math.exp(rawBoxes[boxOffset + 3]);

    // Convert center-format to corner-format, scale to image coordinates
    const bbox: BBox = {
      x: Math.max(0, (cx - w / 2) * imageWidth),
      y: Math.max(0, (cy - h / 2) * imageHeight),
      width: Math.min(w * imageWidth, imageWidth),
      height: Math.min(h * imageHeight, imageHeight),
    };

    const className = UI_CLASSES[bestClass] as UIElementClass;
    detections.push({
      bbox,
      class: className,
      confidence: classConf,
      label: className,
    });
  }

  return detections;
}

/**
 * Non-Maximum Suppression (NMS) — removes overlapping detections.
 *
 * Greedy algorithm: sort by confidence, suppress boxes with IoU > threshold.
 */
export function nms(
  detections: Detection[],
  iouThreshold: number,
  maxDetections: number,
): Detection[] {
  if (detections.length === 0) return [];

  // Sort descending by confidence
  const sorted = [...detections].sort((a, b) => b.confidence - a.confidence);
  const kept: Detection[] = [];
  const suppressed = new Set<number>();

  for (let i = 0; i < sorted.length && kept.length < maxDetections; i++) {
    if (suppressed.has(i)) continue;

    kept.push(sorted[i]);

    for (let j = i + 1; j < sorted.length; j++) {
      if (suppressed.has(j)) continue;
      if (computeIoU(sorted[i].bbox, sorted[j].bbox) > iouThreshold) {
        suppressed.add(j);
      }
    }
  }

  return kept;
}

/**
 * Compute Intersection over Union between two bounding boxes.
 */
export function computeIoU(a: BBox, b: BBox): number {
  const x1 = Math.max(a.x, b.x);
  const y1 = Math.max(a.y, b.y);
  const x2 = Math.min(a.x + a.width, b.x + b.width);
  const y2 = Math.min(a.y + a.height, b.y + b.height);

  const intersection = Math.max(0, x2 - x1) * Math.max(0, y2 - y1);
  if (intersection === 0) return 0;

  const areaA = a.width * a.height;
  const areaB = b.width * b.height;
  return intersection / (areaA + areaB - intersection);
}

/**
 * Generate anchor boxes for SSD-style detection.
 *
 * Creates anchors at multiple scales from feature maps of different sizes.
 * Anchor aspect ratios: [1:1, 2:1, 1:2] at each feature map cell.
 */
export function generateAnchors(
  featureMapSizes: number[],
  inputSize: number,
  anchorsPerCell: number = 3,
): Anchor[] {
  const anchors: Anchor[] = [];

  // Base sizes relative to input: each feature map level detects different scales
  const minScale = 0.1;
  const maxScale = 0.9;
  const numLevels = featureMapSizes.length;

  for (let level = 0; level < numLevels; level++) {
    const fmSize = featureMapSizes[level];
    const scale = minScale + (maxScale - minScale) * (level / Math.max(1, numLevels - 1));

    // Aspect ratios: 1:1, 2:1, 1:2
    const aspectRatios = [1.0, 2.0, 0.5];

    for (let row = 0; row < fmSize; row++) {
      for (let col = 0; col < fmSize; col++) {
        const cx = (col + 0.5) / fmSize;
        const cy = (row + 0.5) / fmSize;

        for (let a = 0; a < Math.min(anchorsPerCell, aspectRatios.length); a++) {
          const ar = aspectRatios[a];
          const w = scale * Math.sqrt(ar);
          const h = scale / Math.sqrt(ar);
          anchors.push({ cx, cy, w, h });
        }
      }
    }
  }

  return anchors;
}

/**
 * Top-K softmax for classification output.
 */
export function softmax(logits: Float32Array | number[]): number[] {
  const max = Math.max(...logits);
  const exps = Array.from(logits, v => Math.exp(v - max));
  const sum = exps.reduce((a, b) => a + b, 0);
  return exps.map(e => e / sum);
}

/** Sigmoid activation. */
function sigmoid(x: number): number {
  return 1 / (1 + Math.exp(-x));
}
