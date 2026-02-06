// ---------------------------------------------------------------------------
// CNN Type Definitions — Rongle Built-in Vision System
// ---------------------------------------------------------------------------

/** Bounding box in pixel coordinates relative to the source image. */
export interface BBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

/**
 * UI element classes the detector is trained to recognise.
 * Order matters — indices map to model output neurons.
 */
export const UI_CLASSES = [
  'button', 'text_input', 'link', 'icon', 'dropdown', 'checkbox',
  'radio', 'toggle', 'slider', 'tab', 'menu_item', 'image',
  'heading', 'paragraph', 'dialog', 'toolbar', 'cursor',
] as const;

export type UIElementClass = typeof UI_CLASSES[number];

/** Screen-level classification labels. */
export const SCREEN_CLASSES = [
  'desktop', 'browser', 'terminal', 'file_manager', 'settings',
  'dialog', 'login', 'editor', 'spreadsheet', 'media', 'unknown',
] as const;

export type ScreenClass = typeof SCREEN_CLASSES[number];

/** A single detected UI element. */
export interface Detection {
  bbox: BBox;
  class: UIElementClass;
  confidence: number;
  label: string;
}

/** Result of screen-level classification. */
export interface Classification {
  class: ScreenClass;
  confidence: number;
  scores: Partial<Record<ScreenClass, number>>;
}

/** Result of frame-to-frame change detection (no CNN needed). */
export interface FrameDiff {
  changePercent: number;
  changedRegions: BBox[];
  similarity: number;
  timestamp: number;
}

/** Combined output from all CNN sub-systems for one frame. */
export interface InferenceResult {
  detections: Detection[];
  classification: Classification | null;
  frameDiff: FrameDiff | null;
  inferenceMs: number;
  timestamp: number;
}

/** Configures which CNN features are active and their thresholds. */
export interface CNNConfig {
  backend: 'webgl' | 'wasm' | 'cpu';
  detectorInputSize: number;
  classifierInputSize: number;
  confidenceThreshold: number;
  iouThreshold: number;
  maxDetections: number;
  enableDetector: boolean;
  enableClassifier: boolean;
  enableFrameDiff: boolean;
  diffThreshold: number;
}

/** Live engine status for UI display. */
export interface EngineStatus {
  ready: boolean;
  backend: string;
  detectorLoaded: boolean;
  classifierLoaded: boolean;
  warmupDone: boolean;
  avgInferenceMs: number;
  fps: number;
}

/** Anchor box definition for SSD-style detection. */
export interface Anchor {
  cx: number;
  cy: number;
  w: number;
  h: number;
}

/** Model weight manifest for loading pre-trained weights. */
export interface WeightManifest {
  modelName: string;
  version: string;
  url: string;
  inputShape: number[];
  numClasses: number;
  anchorsPerCell: number;
  featureMapSizes: number[];
}

/** Sensible defaults. */
export const DEFAULT_CNN_CONFIG: CNNConfig = {
  backend: 'webgl',
  detectorInputSize: 320,
  classifierInputSize: 224,
  confidenceThreshold: 0.35,
  iouThreshold: 0.45,
  maxDetections: 50,
  enableDetector: true,
  enableClassifier: true,
  enableFrameDiff: true,
  diffThreshold: 0.02,
};
