// ---------------------------------------------------------------------------
// TextDetector — Identifies text-bearing regions in a frame.
//
// Uses CNN detections (text_input, heading, paragraph, link, menu_item,
// tab, button) to locate text, then crops and sends those regions to
// Tesseract for targeted OCR. This is much faster than full-page OCR
// because we only process small regions where text is likely.
//
// Also provides a simple canvas-based contrast heuristic to find
// text regions when CNN detections aren't available.
// ---------------------------------------------------------------------------

import type { Detection, BBox } from '../cnn/types';

/** UI classes that typically contain readable text. */
const TEXT_BEARING_CLASSES = new Set([
  'text_input', 'heading', 'paragraph', 'link',
  'menu_item', 'tab', 'button', 'toolbar',
]);

/**
 * Filter CNN detections to only text-bearing UI elements.
 *
 * Returns bounding boxes sorted top-to-bottom, left-to-right
 * (natural reading order).
 */
export function extractTextRegions(detections: Detection[]): BBox[] {
  return detections
    .filter(d => TEXT_BEARING_CLASSES.has(d.class))
    .sort((a, b) => {
      // Sort by Y first (top-to-bottom), then X (left-to-right)
      const yDiff = a.bbox.y - b.bbox.y;
      if (Math.abs(yDiff) > 10) return yDiff;
      return a.bbox.x - b.bbox.x;
    })
    .map(d => d.bbox);
}

/**
 * Merge overlapping text regions to avoid duplicate OCR.
 *
 * Regions that overlap by more than 50% (IoU) are merged into
 * the bounding rectangle that contains both.
 */
export function mergeOverlappingRegions(regions: BBox[], overlapThreshold = 0.5): BBox[] {
  if (regions.length <= 1) return regions;

  const merged: BBox[] = [];
  const used = new Set<number>();

  for (let i = 0; i < regions.length; i++) {
    if (used.has(i)) continue;

    let current = { ...regions[i] };
    used.add(i);

    // Try to merge with all subsequent regions
    let changed = true;
    while (changed) {
      changed = false;
      for (let j = i + 1; j < regions.length; j++) {
        if (used.has(j)) continue;
        if (computeOverlap(current, regions[j]) > overlapThreshold) {
          current = mergeBoxes(current, regions[j]);
          used.add(j);
          changed = true;
        }
      }
    }

    merged.push(current);
  }

  return merged;
}

/**
 * Compute overlap ratio between two boxes (intersection / min area).
 */
function computeOverlap(a: BBox, b: BBox): number {
  const x1 = Math.max(a.x, b.x);
  const y1 = Math.max(a.y, b.y);
  const x2 = Math.min(a.x + a.width, b.x + b.width);
  const y2 = Math.min(a.y + a.height, b.y + b.height);

  if (x2 <= x1 || y2 <= y1) return 0;

  const intersection = (x2 - x1) * (y2 - y1);
  const minArea = Math.min(a.width * a.height, b.width * b.height);

  return minArea > 0 ? intersection / minArea : 0;
}

/**
 * Merge two boxes into their bounding rectangle.
 */
function mergeBoxes(a: BBox, b: BBox): BBox {
  const x = Math.min(a.x, b.x);
  const y = Math.min(a.y, b.y);
  const x2 = Math.max(a.x + a.width, b.x + b.width);
  const y2 = Math.max(a.y + a.height, b.y + b.height);
  return { x, y, width: x2 - x, height: y2 - y };
}

/**
 * Pad a bounding box by a margin (pixels). Clamps to image bounds.
 */
export function padRegion(
  region: BBox,
  padding: number,
  imageWidth: number,
  imageHeight: number,
): BBox {
  const x = Math.max(0, region.x - padding);
  const y = Math.max(0, region.y - padding);
  const x2 = Math.min(imageWidth, region.x + region.width + padding);
  const y2 = Math.min(imageHeight, region.y + region.height + padding);
  return { x, y, width: x2 - x, height: y2 - y };
}

/**
 * Simple contrast-based text region detector for when CNN is unavailable.
 *
 * Divides the image into a grid and scores each cell by local contrast
 * (standard deviation of pixel intensities). High-contrast cells likely
 * contain text against a background.
 *
 * @param imageData  The source image
 * @param gridSize   Number of cells per dimension (default 16)
 * @param threshold  Contrast threshold (0-128, default 25)
 * @returns Array of bounding boxes for high-contrast regions
 */
export function detectTextByContrast(
  imageData: ImageData,
  gridSize = 16,
  threshold = 25,
): BBox[] {
  const { width, height, data } = imageData;
  const cellW = Math.floor(width / gridSize);
  const cellH = Math.floor(height / gridSize);
  const hotCells: Array<{ gx: number; gy: number; contrast: number }> = [];

  for (let gy = 0; gy < gridSize; gy++) {
    for (let gx = 0; gx < gridSize; gx++) {
      const x0 = gx * cellW;
      const y0 = gy * cellH;

      // Compute mean luminance
      let sum = 0;
      let count = 0;
      for (let y = y0; y < y0 + cellH && y < height; y++) {
        for (let x = x0; x < x0 + cellW && x < width; x++) {
          const idx = (y * width + x) * 4;
          const lum = 0.299 * data[idx] + 0.587 * data[idx + 1] + 0.114 * data[idx + 2];
          sum += lum;
          count++;
        }
      }
      const mean = sum / count;

      // Compute standard deviation
      let variance = 0;
      for (let y = y0; y < y0 + cellH && y < height; y++) {
        for (let x = x0; x < x0 + cellW && x < width; x++) {
          const idx = (y * width + x) * 4;
          const lum = 0.299 * data[idx] + 0.587 * data[idx + 1] + 0.114 * data[idx + 2];
          variance += (lum - mean) ** 2;
        }
      }
      const stddev = Math.sqrt(variance / count);

      if (stddev > threshold) {
        hotCells.push({ gx, gy, contrast: stddev });
      }
    }
  }

  // Group adjacent hot cells into regions
  const visited = new Set<string>();
  const regions: BBox[] = [];

  for (const cell of hotCells) {
    const key = `${cell.gx},${cell.gy}`;
    if (visited.has(key)) continue;

    // Flood fill to find connected hot cells
    const group: Array<{ gx: number; gy: number }> = [];
    const queue = [cell];
    visited.add(key);

    while (queue.length > 0) {
      const c = queue.shift()!;
      group.push(c);

      // Check 4 neighbors
      for (const [dx, dy] of [[0, 1], [0, -1], [1, 0], [-1, 0]]) {
        const nx = c.gx + dx;
        const ny = c.gy + dy;
        const nk = `${nx},${ny}`;
        if (!visited.has(nk) && hotCells.some(h => h.gx === nx && h.gy === ny)) {
          visited.add(nk);
          queue.push({ gx: nx, gy: ny, contrast: 0 });
        }
      }
    }

    // Convert group to bounding box
    let minGx = Infinity, minGy = Infinity;
    let maxGx = -Infinity, maxGy = -Infinity;
    for (const g of group) {
      minGx = Math.min(minGx, g.gx);
      minGy = Math.min(minGy, g.gy);
      maxGx = Math.max(maxGx, g.gx);
      maxGy = Math.max(maxGy, g.gy);
    }

    regions.push({
      x: minGx * cellW,
      y: minGy * cellH,
      width: (maxGx - minGx + 1) * cellW,
      height: (maxGy - minGy + 1) * cellH,
    });
  }

  return regions;
}
