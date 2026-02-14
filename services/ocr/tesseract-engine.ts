// ---------------------------------------------------------------------------
// TesseractEngine — Lazy-loading Tesseract.js wrapper for browser OCR.
//
// Loads the Tesseract.js WASM engine from CDN on first use. Workers are
// pooled and reused across calls. All heavy lifting happens in Web Workers
// so the main thread stays responsive.
// ---------------------------------------------------------------------------

import type { OCRConfig, TextLine, TextWord, TextRegion } from './types';
import { DEFAULT_OCR_CONFIG } from './types';

// Tesseract.js is loaded dynamically — no static import needed.
// The library self-registers via the worker script.

interface TesseractWorker {
  recognize(
    image: string | HTMLCanvasElement | HTMLImageElement | ImageData,
    options?: Record<string, any>,
  ): Promise<TesseractResult>;
  terminate(): Promise<void>;
}

interface TesseractResult {
  data: {
    text: string;
    confidence: number;
    lines: Array<{
      text: string;
      confidence: number;
      bbox: { x0: number; y0: number; x1: number; y1: number };
      words: Array<{
        text: string;
        confidence: number;
        bbox: { x0: number; y0: number; x1: number; y1: number };
      }>;
    }>;
    blocks: Array<{
      text: string;
      confidence: number;
      bbox: { x0: number; y0: number; x1: number; y1: number };
      direction: string;
    }>;
  };
}

// ---------------------------------------------------------------------------
// Worker Pool
// ---------------------------------------------------------------------------

let _workerPool: TesseractWorker[] = [];
let _busy = new Set<TesseractWorker>();
let _config: OCRConfig = DEFAULT_OCR_CONFIG;
let _initialized = false;
let _initializing = false;
let _Tesseract: any = null;

/**
 * Initialize Tesseract.js engine. Lazy-loads from CDN on first call.
 * Safe to call multiple times — subsequent calls are no-ops.
 */
export async function initTesseract(config?: Partial<OCRConfig>): Promise<boolean> {
  if (_initialized) return true;
  if (_initializing) return false;
  _initializing = true;

  if (config) _config = { ..._config, ...config };

  try {
    // Dynamic import from CDN
    _Tesseract = await import(
      /* @vite-ignore */
      'https://cdn.jsdelivr.net/npm/tesseract.js@5/dist/tesseract.esm.min.js'
    );

    // Create initial worker pool
    const workerCount = Math.min(_config.maxWorkers, 2);
    for (let i = 0; i < workerCount; i++) {
      const worker = await _createWorker();
      _workerPool.push(worker);
    }

    _initialized = true;
    console.log(`[TesseractEngine] Initialized with ${workerCount} worker(s)`);
    return true;
  } catch (e) {
    console.error('[TesseractEngine] Init failed:', e);
    return false;
  } finally {
    _initializing = false;
  }
}

async function _createWorker(): Promise<TesseractWorker> {
  const worker = await _Tesseract.createWorker(_config.language, 1, {
    workerPath: _config.workerUrl,
    corePath: _config.coreUrl,
    langPath: _config.langDataPath,
    logger: () => {}, // silent
  });

  // Set parameters
  if (_config.charWhitelist) {
    await (worker as any).setParameters({
      tessedit_char_whitelist: _config.charWhitelist,
    });
  }
  await (worker as any).setParameters({
    tessedit_pageseg_mode: String(_config.pageSegMode),
  });

  return worker;
}

/**
 * Acquire a worker from the pool (or create one if under limit).
 */
async function acquireWorker(): Promise<TesseractWorker> {
  // Find a free worker
  for (const w of _workerPool) {
    if (!_busy.has(w)) {
      _busy.add(w);
      return w;
    }
  }

  // All busy — create a new one if under limit
  if (_workerPool.length < _config.maxWorkers) {
    const w = await _createWorker();
    _workerPool.push(w);
    _busy.add(w);
    return w;
  }

  // Wait for one to become available
  return new Promise<TesseractWorker>((resolve) => {
    const interval = setInterval(() => {
      for (const w of _workerPool) {
        if (!_busy.has(w)) {
          clearInterval(interval);
          _busy.add(w);
          resolve(w);
          return;
        }
      }
    }, 50);
  });
}

function releaseWorker(worker: TesseractWorker): void {
  _busy.delete(worker);
}

// ---------------------------------------------------------------------------
// Recognition
// ---------------------------------------------------------------------------

/**
 * Run OCR on an image. Accepts base64, canvas, img element, or ImageData.
 */
export async function recognizeImage(
  image: string | HTMLCanvasElement | HTMLImageElement | ImageData,
): Promise<{
  text: string;
  confidence: number;
  regions: TextRegion[];
  lines: TextLine[];
}> {
  if (!_initialized) throw new Error('TesseractEngine not initialized');

  const worker = await acquireWorker();
  try {
    // If base64 string, prepend data URI if missing
    let input = image;
    if (typeof input === 'string' && !input.startsWith('data:')) {
      input = `data:image/jpeg;base64,${input}`;
    }

    const result = await worker.recognize(input);
    const { data } = result;

    // Convert Tesseract output to our types
    const regions: TextRegion[] = (data.blocks || [])
      .filter((b: any) => b.confidence >= _config.minConfidence)
      .map((block: any) => ({
        bbox: {
          x: block.bbox.x0,
          y: block.bbox.y0,
          width: block.bbox.x1 - block.bbox.x0,
          height: block.bbox.y1 - block.bbox.y0,
        },
        text: block.text.trim(),
        confidence: block.confidence,
        direction: (block.direction === 'rtl' ? 'rtl' : 'ltr') as 'ltr' | 'rtl',
      }));

    const lines: TextLine[] = (data.lines || [])
      .filter((l: any) => l.confidence >= _config.minConfidence)
      .map((line: any) => ({
        text: line.text.trim(),
        confidence: line.confidence,
        bbox: {
          x: line.bbox.x0,
          y: line.bbox.y0,
          width: line.bbox.x1 - line.bbox.x0,
          height: line.bbox.y1 - line.bbox.y0,
        },
        words: (line.words || []).map((w: any) => ({
          text: w.text,
          confidence: w.confidence,
          bbox: {
            x: w.bbox.x0,
            y: w.bbox.y0,
            width: w.bbox.x1 - w.bbox.x0,
            height: w.bbox.y1 - w.bbox.y0,
          },
        })),
      }));

    return {
      text: data.text.trim(),
      confidence: data.confidence,
      regions,
      lines,
    };
  } finally {
    releaseWorker(worker);
  }
}

/**
 * Crop a region from a canvas and run OCR on just that region.
 * More efficient than full-page OCR when you know where text is.
 */
export async function recognizeRegion(
  sourceCanvas: HTMLCanvasElement,
  x: number, y: number,
  width: number, height: number,
): Promise<{
  text: string;
  confidence: number;
  lines: TextLine[];
}> {
  // Crop the region to a temporary canvas
  const cropCanvas = document.createElement('canvas');
  cropCanvas.width = Math.max(1, Math.round(width));
  cropCanvas.height = Math.max(1, Math.round(height));
  const ctx = cropCanvas.getContext('2d')!;

  ctx.drawImage(
    sourceCanvas,
    Math.round(x), Math.round(y), Math.round(width), Math.round(height),
    0, 0, cropCanvas.width, cropCanvas.height,
  );

  const result = await recognizeImage(cropCanvas);

  // Offset line/word bboxes back to source coordinates
  for (const line of result.lines) {
    line.bbox.x += x;
    line.bbox.y += y;
    for (const word of line.words) {
      word.bbox.x += x;
      word.bbox.y += y;
    }
  }

  return result;
}

/**
 * Check if the engine is ready.
 */
export function isTesseractReady(): boolean {
  return _initialized;
}

/**
 * Terminate all workers and free resources.
 */
export async function disposeTesseract(): Promise<void> {
  for (const w of _workerPool) {
    try { await w.terminate(); } catch {}
  }
  _workerPool = [];
  _busy.clear();
  _initialized = false;
  console.log('[TesseractEngine] Disposed all workers');
}
