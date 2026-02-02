// ---------------------------------------------------------------------------
// UI Detector — Full detection pipeline: preprocess → infer → NMS → results.
//
// Wraps the RongleNet-Detect model and anchor generation into a single
// callable pipeline that accepts a base64 image and returns Detection[].
// ---------------------------------------------------------------------------

import type { Detection, CNNConfig } from './types';
import { DEFAULT_CNN_CONFIG } from './types';
import { preprocessFrame, preprocessVideo } from './preprocessor';
import { decodeDetections, nms, generateAnchors } from './postprocessor';
import {
  isReady, createTensor4D, runInference, recordInferenceTime,
  warmupModel, loadCachedModel, loadModelFromURL, saveModel,
} from './engine';
import {
  buildDetector,
  DETECTOR_FEATURE_MAPS,
  DETECTOR_ANCHORS_PER_CELL,
} from './architecture';
import type { Anchor } from './types';

let _model: any = null;
let _anchors: Anchor[] = [];
let _warmedUp = false;
let _config: CNNConfig = DEFAULT_CNN_CONFIG;

/**
 * Initialise the UI detector.
 *
 * 1. Try loading pre-trained weights from IndexedDB cache.
 * 2. If no cached weights, build a fresh (random-weights) model.
 * 3. Generate anchor boxes.
 * 4. Run warmup inference.
 *
 * Returns true if the model is ready for inference.
 */
export async function initDetector(
  config?: Partial<CNNConfig>,
  weightsUrl?: string,
): Promise<boolean> {
  if (config) _config = { ..._config, ...config };

  if (!isReady()) {
    console.warn('[UI Detector] TF.js engine not ready');
    return false;
  }

  try {
    // Try loading from URL or cache first
    if (weightsUrl) {
      _model = await loadModelFromURL(weightsUrl, 'detector');
    }
    if (!_model) {
      _model = await loadCachedModel('detector');
    }
    if (!_model) {
      // Build fresh model with random weights
      const result = await buildDetector(_config.detectorInputSize);
      _model = result.model;
      console.log('[UI Detector] Built fresh model (random weights — load trained weights for accuracy)');
    }

    // Generate anchors
    _anchors = generateAnchors(
      DETECTOR_FEATURE_MAPS,
      _config.detectorInputSize,
      DETECTOR_ANCHORS_PER_CELL,
    );
    console.log(`[UI Detector] Generated ${_anchors.length} anchor boxes`);

    // Warmup
    const warmupMs = await warmupModel(
      _model,
      [_config.detectorInputSize, _config.detectorInputSize, 3],
    );
    _warmedUp = warmupMs >= 0;

    return true;
  } catch (e) {
    console.error('[UI Detector] Initialization failed:', e);
    return false;
  }
}

/**
 * Run UI element detection on a base64-encoded frame.
 *
 * Returns detected UI elements with bounding boxes, classes, and confidence scores.
 */
export async function detectFromBase64(
  base64: string,
  imageWidth: number,
  imageHeight: number,
): Promise<{ detections: Detection[]; inferenceMs: number }> {
  if (!_model) {
    return { detections: [], inferenceMs: 0 };
  }

  const t0 = performance.now();

  // Preprocess: base64 → resize → Float32 tensor
  const { tensor } = await preprocessFrame(base64, _config.detectorInputSize);
  const inputTensor = createTensor4D(tensor, _config.detectorInputSize, _config.detectorInputSize);

  // Run model inference
  const outputs = await runInference(_model, inputTensor);

  // outputs[0] shape: [1, totalAnchors, 4 + numClasses + 1]
  // We need to split into boxes and scores
  const raw = outputs[0];
  const numAnchors = _anchors.length;
  const numValues = 4 + 17 + 1; // 4 box + 17 classes + 1 objectness

  const rawBoxes = new Float32Array(numAnchors * 4);
  const rawScores = new Float32Array(numAnchors * (17 + 1));

  for (let i = 0; i < numAnchors; i++) {
    const offset = i * numValues;
    // Boxes: first 4 values
    rawBoxes[i * 4] = raw[offset];
    rawBoxes[i * 4 + 1] = raw[offset + 1];
    rawBoxes[i * 4 + 2] = raw[offset + 2];
    rawBoxes[i * 4 + 3] = raw[offset + 3];
    // Scores: objectness + 17 class scores
    for (let c = 0; c < 18; c++) {
      rawScores[i * 18 + c] = raw[offset + 4 + c];
    }
  }

  // Decode and filter
  const decoded = decodeDetections(
    rawBoxes,
    rawScores,
    _anchors,
    imageWidth,
    imageHeight,
    _config.confidenceThreshold,
  );

  // Non-maximum suppression
  const detections = nms(decoded, _config.iouThreshold, _config.maxDetections);

  const inferenceMs = performance.now() - t0;
  recordInferenceTime(inferenceMs);

  return { detections, inferenceMs };
}

/**
 * Run UI element detection on a live video element (zero-copy path).
 */
export function detectFromVideo(
  video: HTMLVideoElement,
): Promise<{ detections: Detection[]; inferenceMs: number }> {
  if (!_model) {
    return Promise.resolve({ detections: [], inferenceMs: 0 });
  }

  const t0 = performance.now();

  const { tensor } = preprocessVideo(video, _config.detectorInputSize);
  const inputTensor = createTensor4D(tensor, _config.detectorInputSize, _config.detectorInputSize);

  return runInference(_model, inputTensor).then(outputs => {
    const raw = outputs[0];
    const numAnchors = _anchors.length;
    const numValues = 22; // 4 + 17 + 1

    const rawBoxes = new Float32Array(numAnchors * 4);
    const rawScores = new Float32Array(numAnchors * 18);

    for (let i = 0; i < numAnchors; i++) {
      const offset = i * numValues;
      rawBoxes[i * 4] = raw[offset];
      rawBoxes[i * 4 + 1] = raw[offset + 1];
      rawBoxes[i * 4 + 2] = raw[offset + 2];
      rawBoxes[i * 4 + 3] = raw[offset + 3];
      for (let c = 0; c < 18; c++) {
        rawScores[i * 18 + c] = raw[offset + 4 + c];
      }
    }

    const decoded = decodeDetections(
      rawBoxes, rawScores, _anchors,
      video.videoWidth, video.videoHeight,
      _config.confidenceThreshold,
    );

    const detections = nms(decoded, _config.iouThreshold, _config.maxDetections);
    const inferenceMs = performance.now() - t0;
    recordInferenceTime(inferenceMs);

    return { detections, inferenceMs };
  });
}

/**
 * Get current detector status.
 */
export function isDetectorReady(): boolean {
  return _model !== null && _warmedUp;
}

/**
 * Dispose the detector model and free GPU memory.
 */
export function disposeDetector(): void {
  if (_model?.dispose) {
    _model.dispose();
    _model = null;
  }
  _anchors = [];
  _warmedUp = false;
}
