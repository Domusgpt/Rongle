// ---------------------------------------------------------------------------
// RongleOCR — Unified OCR API combining Tesseract.js with CNN-guided
// region targeting for fast, accurate text recognition.
//
// Usage:
//   import { rongleOCR } from './services/ocr';
//   await rongleOCR.init();
//   const result = await rongleOCR.recognizeText(base64, 1920, 1080);
//   const targeted = await rongleOCR.recognizeFromDetections(base64, cnnDetections);
// ---------------------------------------------------------------------------

import type { OCRConfig, OCRResult, TextRegion, TextLine } from './types';
import { DEFAULT_OCR_CONFIG } from './types';
import type { Detection, BBox } from '../cnn/types';
import {
  initTesseract,
  recognizeImage,
  recognizeRegion,
  isTesseractReady,
  disposeTesseract,
} from './tesseract-engine';
import {
  extractTextRegions,
  mergeOverlappingRegions,
  padRegion,
  detectTextByContrast,
} from './text-detector';

// Re-export types
export type { OCRConfig, OCRResult, TextRegion, TextLine, TextWord } from './types';
export { DEFAULT_OCR_CONFIG } from './types';

/**
 * RongleOCR — main facade class for browser-based text recognition.
 *
 * Combines:
 * - Tesseract.js for WASM-based OCR
 * - CNN detection targeting for speed
 * - Contrast-based fallback for text region detection
 */
class RongleOCR {
  private config: OCRConfig;
  private _initialized = false;
  private _initializing = false;

  constructor(config?: Partial<OCRConfig>) {
    this.config = { ...DEFAULT_OCR_CONFIG, ...config };
  }

  /**
   * Initialize the OCR engine. Loads Tesseract.js WASM from CDN.
   * Safe to call multiple times.
   */
  async init(config?: Partial<OCRConfig>): Promise<boolean> {
    if (this._initialized) return true;
    if (this._initializing) return false;
    this._initializing = true;

    if (config) this.config = { ...this.config, ...config };

    try {
      const ok = await initTesseract(this.config);
      this._initialized = ok;
      return ok;
    } catch (e) {
      console.error('[RongleOCR] Init failed:', e);
      return false;
    } finally {
      this._initializing = false;
    }
  }

  /**
   * Full-page OCR on a base64 image.
   *
   * This is the simplest API — sends the entire image to Tesseract.
   * For better performance on complex screens, use recognizeFromDetections().
   */
  async recognizeText(
    base64: string,
    imageWidth: number,
    imageHeight: number,
  ): Promise<OCRResult> {
    const t0 = performance.now();

    if (!this._initialized) {
      throw new Error('RongleOCR not initialized — call init() first');
    }

    const result = await recognizeImage(base64);

    return {
      regions: result.regions,
      fullText: result.text,
      lines: result.lines,
      processingMs: performance.now() - t0,
      imageWidth,
      imageHeight,
      timestamp: Date.now(),
    };
  }

  /**
   * Targeted OCR using CNN detections.
   *
   * Extracts text-bearing regions (buttons, inputs, headings, etc.)
   * from CNN detections, then runs OCR only on those cropped regions.
   * Much faster than full-page OCR on screens with mixed content.
   *
   * @param base64       Source image
   * @param detections   CNN detection results
   * @param imageWidth   Source image width
   * @param imageHeight  Source image height
   */
  async recognizeFromDetections(
    base64: string,
    detections: Detection[],
    imageWidth: number,
    imageHeight: number,
  ): Promise<OCRResult> {
    const t0 = performance.now();

    if (!this._initialized) {
      throw new Error('RongleOCR not initialized — call init() first');
    }

    // 1. Extract text-bearing regions from CNN detections
    let regions = extractTextRegions(detections);
    regions = mergeOverlappingRegions(regions);
    regions = regions.map(r => padRegion(r, 4, imageWidth, imageHeight));

    if (regions.length === 0) {
      return {
        regions: [],
        fullText: '',
        lines: [],
        processingMs: performance.now() - t0,
        imageWidth,
        imageHeight,
        timestamp: Date.now(),
      };
    }

    // 2. Decode base64 to a canvas for cropping
    const canvas = await base64ToCanvas(base64);

    // 3. OCR each region in parallel
    const regionResults = await Promise.all(
      regions.map(region =>
        recognizeRegion(
          canvas, region.x, region.y, region.width, region.height,
        ).catch(() => ({ text: '', confidence: 0, lines: [] as TextLine[] }))
      ),
    );

    // 4. Combine results
    const allRegions: TextRegion[] = [];
    const allLines: TextLine[] = [];
    const textParts: string[] = [];

    for (let i = 0; i < regions.length; i++) {
      const r = regionResults[i];
      if (r.text.trim()) {
        allRegions.push({
          bbox: regions[i],
          text: r.text.trim(),
          confidence: r.confidence,
          direction: 'ltr',
        });
        allLines.push(...r.lines);
        textParts.push(r.text.trim());
      }
    }

    return {
      regions: allRegions,
      fullText: textParts.join('\n'),
      lines: allLines,
      processingMs: performance.now() - t0,
      imageWidth,
      imageHeight,
      timestamp: Date.now(),
    };
  }

  /**
   * Recognize text in specific bounding boxes.
   *
   * Useful when you already know where text is (e.g., from manual
   * annotation or a specific UI element you want to read).
   */
  async recognizeRegions(
    base64: string,
    boxes: BBox[],
    imageWidth: number,
    imageHeight: number,
  ): Promise<OCRResult> {
    const t0 = performance.now();

    if (!this._initialized) {
      throw new Error('RongleOCR not initialized — call init() first');
    }

    const canvas = await base64ToCanvas(base64);
    const regionResults = await Promise.all(
      boxes.map(box =>
        recognizeRegion(canvas, box.x, box.y, box.width, box.height)
          .catch(() => ({ text: '', confidence: 0, lines: [] as TextLine[] }))
      ),
    );

    const allRegions: TextRegion[] = [];
    const allLines: TextLine[] = [];
    const textParts: string[] = [];

    for (let i = 0; i < boxes.length; i++) {
      const r = regionResults[i];
      if (r.text.trim()) {
        allRegions.push({
          bbox: boxes[i],
          text: r.text.trim(),
          confidence: r.confidence,
          direction: 'ltr',
        });
        allLines.push(...r.lines);
        textParts.push(r.text.trim());
      }
    }

    return {
      regions: allRegions,
      fullText: textParts.join('\n'),
      lines: allLines,
      processingMs: performance.now() - t0,
      imageWidth,
      imageHeight,
      timestamp: Date.now(),
    };
  }

  /**
   * Auto-detect text regions using contrast heuristics (no CNN needed),
   * then OCR them. Slower than CNN-guided but works without models.
   */
  async recognizeWithContrastDetection(
    base64: string,
    imageWidth: number,
    imageHeight: number,
  ): Promise<OCRResult> {
    const t0 = performance.now();

    if (!this._initialized) {
      throw new Error('RongleOCR not initialized — call init() first');
    }

    const canvas = await base64ToCanvas(base64);
    const ctx = canvas.getContext('2d')!;
    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);

    // Detect text regions by contrast
    let regions = detectTextByContrast(imageData);
    regions = mergeOverlappingRegions(regions);

    if (regions.length === 0) {
      // Fallback to full-page OCR
      return this.recognizeText(base64, imageWidth, imageHeight);
    }

    // OCR each region
    return this.recognizeRegions(base64, regions, imageWidth, imageHeight);
  }

  /**
   * Check if the OCR engine is ready.
   */
  isReady(): boolean {
    return this._initialized && isTesseractReady();
  }

  /**
   * Update configuration at runtime.
   */
  updateConfig(config: Partial<OCRConfig>): void {
    this.config = { ...this.config, ...config };
  }

  /**
   * Get current configuration.
   */
  getConfig(): OCRConfig {
    return { ...this.config };
  }

  /**
   * Clean up all workers and free resources.
   */
  async dispose(): Promise<void> {
    await disposeTesseract();
    this._initialized = false;
    console.log('[RongleOCR] Disposed');
  }
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

async function base64ToCanvas(base64: string): Promise<HTMLCanvasElement> {
  const img = await new Promise<HTMLImageElement>((resolve, reject) => {
    const el = new Image();
    el.onload = () => resolve(el);
    el.onerror = reject;
    el.src = `data:image/jpeg;base64,${base64}`;
  });

  const canvas = document.createElement('canvas');
  canvas.width = img.width;
  canvas.height = img.height;
  const ctx = canvas.getContext('2d')!;
  ctx.drawImage(img, 0, 0);
  return canvas;
}

// ---------------------------------------------------------------------------
// Singleton
// ---------------------------------------------------------------------------

/** Global OCR instance. Import and use directly. */
export const rongleOCR = new RongleOCR();

/** Also export the class for advanced usage. */
export { RongleOCR };
