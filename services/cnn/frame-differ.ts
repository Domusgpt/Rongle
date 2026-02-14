// ---------------------------------------------------------------------------
// Frame Differ — Fast canvas-based change detection between frames.
//
// No CNN required — uses pure pixel math for:
//   - Absolute pixel difference with threshold
//   - Structural Similarity (SSIM-like) metric
//   - Connected-component region extraction
//   - Edge density comparison for layout change detection
//
// All operations use Uint8 grayscale arrays for speed.
// ---------------------------------------------------------------------------

import type { BBox, FrameDiff } from './types';
import { toGrayscale } from './preprocessor';

/**
 * Compare two frames and return change metrics + changed regions.
 *
 * Both frames must be the same dimensions.
 * Uses downscaled grayscale comparison for speed.
 */
export function compareFrames(
  currentImageData: ImageData,
  previousImageData: ImageData,
  threshold: number = 0.02,
  blockSize: number = 16,
): FrameDiff {
  const { width, height } = currentImageData;

  // Convert to grayscale
  const grayA = toGrayscale(previousImageData);
  const grayB = toGrayscale(currentImageData);

  // Absolute pixel difference
  const diff = absoluteDifference(grayA, grayB, width, height);

  // Count changed pixels above threshold (threshold is 0-1, scale to 0-255)
  const pixelThreshold = Math.round(threshold * 255);
  let changedPixels = 0;
  for (let i = 0; i < diff.length; i++) {
    if (diff[i] > pixelThreshold) changedPixels++;
  }
  const changePercent = changedPixels / diff.length;

  // Structural similarity
  const similarity = computeSSIM(grayA, grayB, width, height);

  // Find changed regions using block-based analysis
  const changedRegions = findChangedRegions(diff, width, height, pixelThreshold, blockSize);

  return {
    changePercent,
    changedRegions,
    similarity,
    timestamp: Date.now(),
  };
}

/**
 * Absolute per-pixel difference between two grayscale arrays.
 */
function absoluteDifference(
  a: Uint8Array,
  b: Uint8Array,
  _width: number,
  _height: number,
): Uint8Array {
  const diff = new Uint8Array(a.length);
  for (let i = 0; i < a.length; i++) {
    diff[i] = Math.abs(a[i] - b[i]);
  }
  return diff;
}

/**
 * Simplified SSIM (Structural Similarity Index) computed over 8x8 blocks.
 *
 * Returns a value in [0, 1] where 1 = identical frames.
 * Uses the luminance and contrast components (not full SSIM structure term)
 * for speed.
 */
function computeSSIM(
  a: Uint8Array,
  b: Uint8Array,
  width: number,
  height: number,
  windowSize: number = 8,
): number {
  const C1 = 6.5025;   // (0.01 * 255)^2
  const C2 = 58.5225;  // (0.03 * 255)^2

  let ssimSum = 0;
  let windowCount = 0;

  for (let y = 0; y <= height - windowSize; y += windowSize) {
    for (let x = 0; x <= width - windowSize; x += windowSize) {
      let sumA = 0, sumB = 0;
      let sumA2 = 0, sumB2 = 0, sumAB = 0;
      const n = windowSize * windowSize;

      for (let dy = 0; dy < windowSize; dy++) {
        for (let dx = 0; dx < windowSize; dx++) {
          const idx = (y + dy) * width + (x + dx);
          const va = a[idx];
          const vb = b[idx];
          sumA += va;
          sumB += vb;
          sumA2 += va * va;
          sumB2 += vb * vb;
          sumAB += va * vb;
        }
      }

      const muA = sumA / n;
      const muB = sumB / n;
      const sigmaA2 = sumA2 / n - muA * muA;
      const sigmaB2 = sumB2 / n - muB * muB;
      const sigmaAB = sumAB / n - muA * muB;

      const numerator = (2 * muA * muB + C1) * (2 * sigmaAB + C2);
      const denominator = (muA * muA + muB * muB + C1) * (sigmaA2 + sigmaB2 + C2);

      ssimSum += numerator / denominator;
      windowCount++;
    }
  }

  return windowCount > 0 ? ssimSum / windowCount : 1.0;
}

/**
 * Block-based changed region detection.
 *
 * Divides the difference image into blocks, marks blocks with mean
 * difference above threshold, then merges adjacent marked blocks
 * into bounding-box regions.
 */
function findChangedRegions(
  diff: Uint8Array,
  width: number,
  height: number,
  threshold: number,
  blockSize: number,
): BBox[] {
  const cols = Math.ceil(width / blockSize);
  const rows = Math.ceil(height / blockSize);
  const blockChanged = new Uint8Array(rows * cols);

  // Score each block
  for (let by = 0; by < rows; by++) {
    for (let bx = 0; bx < cols; bx++) {
      let sum = 0;
      let count = 0;

      const yStart = by * blockSize;
      const xStart = bx * blockSize;
      const yEnd = Math.min(yStart + blockSize, height);
      const xEnd = Math.min(xStart + blockSize, width);

      for (let y = yStart; y < yEnd; y++) {
        for (let x = xStart; x < xEnd; x++) {
          sum += diff[y * width + x];
          count++;
        }
      }

      if (count > 0 && sum / count > threshold) {
        blockChanged[by * cols + bx] = 1;
      }
    }
  }

  // Connected component labelling (4-connected flood fill)
  const labels = new Int32Array(rows * cols);
  let nextLabel = 1;
  const regionBlocks: Map<number, { minX: number; minY: number; maxX: number; maxY: number }> = new Map();

  for (let by = 0; by < rows; by++) {
    for (let bx = 0; bx < cols; bx++) {
      const idx = by * cols + bx;
      if (blockChanged[idx] === 0 || labels[idx] !== 0) continue;

      // Flood fill
      const label = nextLabel++;
      const stack = [{ bx, by }];
      let minX = bx, maxX = bx, minY = by, maxY = by;

      while (stack.length > 0) {
        const { bx: cx, by: cy } = stack.pop()!;
        const cidx = cy * cols + cx;
        if (cx < 0 || cx >= cols || cy < 0 || cy >= rows) continue;
        if (blockChanged[cidx] === 0 || labels[cidx] !== 0) continue;

        labels[cidx] = label;
        minX = Math.min(minX, cx);
        maxX = Math.max(maxX, cx);
        minY = Math.min(minY, cy);
        maxY = Math.max(maxY, cy);

        stack.push({ bx: cx + 1, by: cy });
        stack.push({ bx: cx - 1, by: cy });
        stack.push({ bx: cx, by: cy + 1 });
        stack.push({ bx: cx, by: cy - 1 });
      }

      regionBlocks.set(label, { minX, minY, maxX, maxY });
    }
  }

  // Convert block coordinates to pixel bounding boxes
  const regions: BBox[] = [];
  for (const [, region] of regionBlocks) {
    regions.push({
      x: region.minX * blockSize,
      y: region.minY * blockSize,
      width: (region.maxX - region.minX + 1) * blockSize,
      height: (region.maxY - region.minY + 1) * blockSize,
    });
  }

  return regions;
}

/**
 * Fast perceptual hash (pHash) for frame deduplication.
 *
 * Downscales to 8x8 grayscale, computes DCT-like mean comparison,
 * returns a 64-bit hash as a hex string.
 */
export function perceptualHash(imageData: ImageData): string {
  // Downscale to 8x8
  const size = 8;
  const { width, height } = imageData;
  const gray = toGrayscale(imageData);
  const small = new Float32Array(size * size);

  // Bilinear downscale
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const srcX = (x / size) * width;
      const srcY = (y / size) * height;
      const sx = Math.floor(srcX);
      const sy = Math.floor(srcY);
      small[y * size + x] = gray[sy * width + sx];
    }
  }

  // Mean-based hash
  let mean = 0;
  for (let i = 0; i < small.length; i++) mean += small[i];
  mean /= small.length;

  let hash = '';
  for (let i = 0; i < small.length; i += 4) {
    let nibble = 0;
    for (let b = 0; b < 4 && i + b < small.length; b++) {
      if (small[i + b] > mean) nibble |= (1 << b);
    }
    hash += nibble.toString(16);
  }

  return hash;
}

/**
 * Compute Hamming distance between two perceptual hashes.
 * Lower = more similar. 0 = identical.
 */
export function hammingDistance(hashA: string, hashB: string): number {
  let dist = 0;
  const len = Math.min(hashA.length, hashB.length);
  for (let i = 0; i < len; i++) {
    const a = parseInt(hashA[i], 16);
    const b = parseInt(hashB[i], 16);
    let xor = a ^ b;
    while (xor) {
      dist += xor & 1;
      xor >>= 1;
    }
  }
  return dist;
}

/**
 * Compute edge density of a grayscale image using Sobel-like operators.
 * Returns a value 0-1 indicating how "busy" the image is with edges.
 * Useful for detecting layout changes vs. content-only changes.
 */
export function edgeDensity(imageData: ImageData): number {
  const { width, height } = imageData;
  const gray = toGrayscale(imageData);
  let edgeCount = 0;
  const threshold = 30;

  for (let y = 1; y < height - 1; y++) {
    for (let x = 1; x < width - 1; x++) {
      const idx = y * width + x;
      // Sobel X
      const gx =
        -gray[idx - width - 1] + gray[idx - width + 1] +
        -2 * gray[idx - 1] + 2 * gray[idx + 1] +
        -gray[idx + width - 1] + gray[idx + width + 1];
      // Sobel Y
      const gy =
        -gray[idx - width - 1] - 2 * gray[idx - width] - gray[idx - width + 1] +
        gray[idx + width - 1] + 2 * gray[idx + width] + gray[idx + width + 1];

      const magnitude = Math.sqrt(gx * gx + gy * gy);
      if (magnitude > threshold) edgeCount++;
    }
  }

  return edgeCount / ((width - 2) * (height - 2));
}
