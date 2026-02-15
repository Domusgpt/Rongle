// ---------------------------------------------------------------------------
// Screen Classifier — Identifies the type of screen being viewed.
//
// Classifies captured frames into categories like: desktop, browser, terminal,
// dialog, login, editor, etc.  This contextual information helps the VLM
// generate better prompts and reduces wasted API calls.
// ---------------------------------------------------------------------------

import type { Classification, CNNConfig } from './types';
import { DEFAULT_CNN_CONFIG, SCREEN_CLASSES } from './types';
import { preprocessFrame, preprocessVideo } from './preprocessor';
import { softmax } from './postprocessor';
import {
  isReady, createTensor4D, runInference, recordInferenceTime,
  warmupModel, loadCachedModel, loadModelFromURL,
} from './engine';
import { buildClassifier } from './architecture';

let _model: any = null;
let _warmedUp = false;
let _config: CNNConfig = DEFAULT_CNN_CONFIG;

/**
 * Initialise the screen classifier.
 *
 * Same pattern as the detector: try cached weights, then build fresh.
 */
export async function initClassifier(
  config?: Partial<CNNConfig>,
  weightsUrl?: string,
): Promise<boolean> {
  if (config) _config = { ..._config, ...config };

  if (!isReady()) {
    console.warn('[Screen Classifier] TF.js engine not ready');
    return false;
  }

  try {
    if (weightsUrl) {
      _model = await loadModelFromURL(weightsUrl, 'classifier');
    }
    if (!_model) {
      _model = await loadCachedModel('classifier');
    }
    if (!_model) {
      _model = await buildClassifier(_config.classifierInputSize);
      console.log('[Screen Classifier] Built fresh model (random weights)');
    }

    const warmupMs = await warmupModel(
      _model,
      [_config.classifierInputSize, _config.classifierInputSize, 3],
    );
    _warmedUp = warmupMs >= 0;

    return true;
  } catch (e) {
    console.error('[Screen Classifier] Initialization failed:', e);
    return false;
  }
}

/**
 * Classify a base64-encoded frame.
 *
 * Returns the predicted screen class, confidence, and all class scores.
 */
export async function classifyFromBase64(
  base64: string,
): Promise<{ classification: Classification; inferenceMs: number }> {
  if (!_model) {
    return {
      classification: { class: 'unknown', confidence: 0, scores: {} },
      inferenceMs: 0,
    };
  }

  const t0 = performance.now();

  const { tensor } = await preprocessFrame(base64, _config.classifierInputSize);
  const inputTensor = createTensor4D(tensor, _config.classifierInputSize, _config.classifierInputSize);

  const outputs = await runInference(_model, inputTensor);
  const logits = outputs[0];

  // Apply softmax and find best class
  const probs = softmax(logits);
  let bestIdx = 0;
  let bestProb = 0;

  const scores: Partial<Record<typeof SCREEN_CLASSES[number], number>> = {};

  for (let i = 0; i < SCREEN_CLASSES.length; i++) {
    scores[SCREEN_CLASSES[i]] = probs[i];
    if (probs[i] > bestProb) {
      bestProb = probs[i];
      bestIdx = i;
    }
  }

  const inferenceMs = performance.now() - t0;
  recordInferenceTime(inferenceMs);

  return {
    classification: {
      class: SCREEN_CLASSES[bestIdx],
      confidence: bestProb,
      scores,
    },
    inferenceMs,
  };
}

/**
 * Classify from a live video element.
 */
export async function classifyFromVideo(
  video: HTMLVideoElement,
): Promise<{ classification: Classification; inferenceMs: number }> {
  if (!_model) {
    return {
      classification: { class: 'unknown', confidence: 0, scores: {} },
      inferenceMs: 0,
    };
  }

  const t0 = performance.now();

  const { tensor } = preprocessVideo(video, _config.classifierInputSize);
  const inputTensor = createTensor4D(tensor, _config.classifierInputSize, _config.classifierInputSize);

  const outputs = await runInference(_model, inputTensor);
  const probs = softmax(outputs[0]);

  let bestIdx = 0;
  let bestProb = 0;
  const scores: Partial<Record<typeof SCREEN_CLASSES[number], number>> = {};

  for (let i = 0; i < SCREEN_CLASSES.length; i++) {
    scores[SCREEN_CLASSES[i]] = probs[i];
    if (probs[i] > bestProb) {
      bestProb = probs[i];
      bestIdx = i;
    }
  }

  const inferenceMs = performance.now() - t0;
  recordInferenceTime(inferenceMs);

  return {
    classification: {
      class: SCREEN_CLASSES[bestIdx],
      confidence: bestProb,
      scores,
    },
    inferenceMs,
  };
}

/**
 * Check if classifier is ready.
 */
export function isClassifierReady(): boolean {
  return _model !== null && _warmedUp;
}

/**
 * Dispose classifier model.
 */
export function disposeClassifier(): void {
  if (_model?.dispose) {
    _model.dispose();
    _model = null;
  }
  _warmedUp = false;
}
