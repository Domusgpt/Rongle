// ---------------------------------------------------------------------------
// OCR Type Definitions — Rongle Text Recognition System
// ---------------------------------------------------------------------------

import type { BBox } from '../cnn/types';

/** A single recognized text region with its bounding box. */
export interface TextRegion {
  bbox: BBox;
  text: string;
  confidence: number;
  /** Dominant direction: ltr or rtl. */
  direction: 'ltr' | 'rtl';
}

/** A single line of recognized text within a region. */
export interface TextLine {
  text: string;
  confidence: number;
  bbox: BBox;
  words: TextWord[];
}

/** A single recognized word. */
export interface TextWord {
  text: string;
  confidence: number;
  bbox: BBox;
}

/** Combined OCR output for one frame or image. */
export interface OCRResult {
  /** All recognized text regions. */
  regions: TextRegion[];
  /** Concatenated full text (reading order, top-to-bottom). */
  fullText: string;
  /** Lines (ordered top-to-bottom, left-to-right). */
  lines: TextLine[];
  /** Time taken in milliseconds. */
  processingMs: number;
  /** Image dimensions the OCR was run on. */
  imageWidth: number;
  imageHeight: number;
  timestamp: number;
}

/** Configuration for the OCR system. */
export interface OCRConfig {
  /** Language code(s) for Tesseract. Default: 'eng'. */
  language: string;
  /** Tesseract.js worker URL (CDN). */
  workerUrl: string;
  /** Core WASM URL. */
  coreUrl: string;
  /** Trained data path prefix. */
  langDataPath: string;
  /** Maximum concurrent OCR workers. */
  maxWorkers: number;
  /** Minimum confidence to include a text region. */
  minConfidence: number;
  /** Whether to use CNN detections to target OCR (faster). */
  useCNNRegions: boolean;
  /** Whitelist characters (empty = all). */
  charWhitelist: string;
  /** Page segmentation mode (0-13, Tesseract PSM). */
  pageSegMode: number;
}

/** Sensible defaults. */
export const DEFAULT_OCR_CONFIG: OCRConfig = {
  language: 'eng',
  workerUrl: 'https://cdn.jsdelivr.net/npm/tesseract.js@5/dist/worker.min.js',
  coreUrl: 'https://cdn.jsdelivr.net/npm/tesseract.js-core@5/tesseract-core-simd-lstm.wasm.js',
  langDataPath: 'https://tessdata.projectnaptha.com/4.0.0',
  maxWorkers: 2,
  minConfidence: 40,
  useCNNRegions: true,
  charWhitelist: '',
  pageSegMode: 3, // PSM_AUTO (fully automatic page segmentation)
};
