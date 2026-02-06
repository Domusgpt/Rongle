// ---------------------------------------------------------------------------
// RongleCNN — Unified API for the built-in CNN vision system.
//
// Combines UI element detection, screen classification, and frame
// differencing into a single interface that the React app consumes.
//
// Usage:
//   import { rongleCNN } from './services/cnn';
//   await rongleCNN.init();
//   const result = await rongleCNN.processFrame(base64);
// ---------------------------------------------------------------------------

import type {
  CNNConfig,
  Detection,
  Classification,
  FrameDiff,
  InferenceResult,
  EngineStatus,
} from './types';
import { DEFAULT_CNN_CONFIG } from './types';
import { initBackend, getStatus, isReady } from './engine';
import { initDetector, detectFromBase64, detectFromVideo, isDetectorReady, disposeDetector } from './ui-detector';
import { initClassifier, classifyFromBase64, classifyFromVideo, isClassifierReady, disposeClassifier } from './screen-classifier';
import { compareFrames, perceptualHash, hammingDistance, edgeDensity } from './frame-differ';
import { decodeToImageData } from './preprocessor';

// Re-export everything consumers might need
export type {
  CNNConfig,
  Detection,
  Classification,
  FrameDiff,
  InferenceResult,
  EngineStatus,
  BBox,
  UIElementClass,
  ScreenClass,
} from './types';
export { DEFAULT_CNN_CONFIG, UI_CLASSES, SCREEN_CLASSES } from './types';
export { perceptualHash, hammingDistance, edgeDensity } from './frame-differ';

/**
 * RongleCNN — main facade class.
 *
 * Orchestrates all CNN sub-systems and provides a unified processFrame()
 * method that runs detection, classification, and frame differencing
 * in a single call.
 */
class RongleCNN {
  private config: CNNConfig;
  private _initialized = false;
  private _initializing = false;
  private _previousImageData: ImageData | null = null;
  private _previousHash: string = '';

  constructor(config?: Partial<CNNConfig>) {
    this.config = { ...DEFAULT_CNN_CONFIG, ...config };
  }

  /**
   * Initialise the CNN engine and all enabled models.
   *
   * Call this once at app startup.  Safe to call multiple times
   * (subsequent calls are no-ops).
   */
  async init(config?: Partial<CNNConfig>): Promise<boolean> {
    if (this._initialized) return true;
    if (this._initializing) return false;
    this._initializing = true;

    if (config) this.config = { ...this.config, ...config };

    try {
      // Step 1: Initialise TF.js backend
      const backend = await initBackend(this.config.backend);
      if (backend === 'none') {
        console.warn('[RongleCNN] No TF.js backend — running in frame-differ only mode');
        this._initialized = true;
        this._initializing = false;
        return true; // frame-differ still works
      }

      // Step 2: Build/load detector model
      if (this.config.enableDetector) {
        const ok = await initDetector(this.config);
        if (!ok) console.warn('[RongleCNN] Detector init failed — detection disabled');
      }

      // Step 3: Build/load classifier model
      if (this.config.enableClassifier) {
        const ok = await initClassifier(this.config);
        if (!ok) console.warn('[RongleCNN] Classifier init failed — classification disabled');
      }

      this._initialized = true;
      console.log('[RongleCNN] Fully initialized');
      return true;
    } catch (e) {
      console.error('[RongleCNN] Initialization error:', e);
      return false;
    } finally {
      this._initializing = false;
    }
  }

  /**
   * Process a single frame through all enabled CNN pipelines.
   *
   * Returns combined results from detection, classification, and
   * frame differencing in a single InferenceResult.
   */
  async processFrame(
    base64: string,
    imageWidth: number,
    imageHeight: number,
  ): Promise<InferenceResult> {
    const t0 = performance.now();
    const result: InferenceResult = {
      detections: [],
      classification: null,
      frameDiff: null,
      inferenceMs: 0,
      timestamp: Date.now(),
    };

    // Run detection, classification, and frame-diff concurrently
    const promises: Promise<void>[] = [];

    // UI Element Detection
    if (this.config.enableDetector && isDetectorReady()) {
      promises.push(
        detectFromBase64(base64, imageWidth, imageHeight).then(({ detections }) => {
          result.detections = detections;
        }).catch(e => console.warn('[RongleCNN] Detection error:', e))
      );
    }

    // Screen Classification
    if (this.config.enableClassifier && isClassifierReady()) {
      promises.push(
        classifyFromBase64(base64).then(({ classification }) => {
          result.classification = classification;
        }).catch(e => console.warn('[RongleCNN] Classification error:', e))
      );
    }

    // Frame Differencing (always available — no CNN needed)
    if (this.config.enableFrameDiff) {
      promises.push(
        this._computeFrameDiff(base64).then(diff => {
          result.frameDiff = diff;
        }).catch(e => console.warn('[RongleCNN] Frame diff error:', e))
      );
    }

    await Promise.all(promises);

    result.inferenceMs = performance.now() - t0;
    return result;
  }

  /**
   * Process a live video element (faster than base64 — avoids encode/decode).
   */
  async processVideo(video: HTMLVideoElement): Promise<InferenceResult> {
    const t0 = performance.now();
    const result: InferenceResult = {
      detections: [],
      classification: null,
      frameDiff: null,
      inferenceMs: 0,
      timestamp: Date.now(),
    };

    const promises: Promise<void>[] = [];

    if (this.config.enableDetector && isDetectorReady()) {
      promises.push(
        detectFromVideo(video).then(({ detections }) => {
          result.detections = detections;
        }).catch(e => console.warn('[RongleCNN] Detection error:', e))
      );
    }

    if (this.config.enableClassifier && isClassifierReady()) {
      promises.push(
        classifyFromVideo(video).then(({ classification }) => {
          result.classification = classification;
        }).catch(e => console.warn('[RongleCNN] Classification error:', e))
      );
    }

    // Frame diff from video requires extracting ImageData
    // Skipped for video path to maintain speed — use processFrame for diff

    await Promise.all(promises);

    result.inferenceMs = performance.now() - t0;
    return result;
  }

  /**
   * Run only frame differencing (no CNN models needed).
   * Works even if TF.js is not available.
   */
  async diffFrame(base64: string): Promise<FrameDiff | null> {
    return this._computeFrameDiff(base64);
  }

  /**
   * Run only UI detection.
   */
  async detect(
    base64: string,
    imageWidth: number,
    imageHeight: number,
  ): Promise<Detection[]> {
    if (!isDetectorReady()) return [];
    const { detections } = await detectFromBase64(base64, imageWidth, imageHeight);
    return detections;
  }

  /**
   * Run only screen classification.
   */
  async classify(base64: string): Promise<Classification | null> {
    if (!isClassifierReady()) return null;
    const { classification } = await classifyFromBase64(base64);
    return classification;
  }

  /**
   * Get engine status for UI display.
   */
  getStatus(): EngineStatus {
    return getStatus(isDetectorReady(), isClassifierReady(), this._initialized);
  }

  /**
   * Update configuration at runtime.
   */
  updateConfig(config: Partial<CNNConfig>): void {
    this.config = { ...this.config, ...config };
  }

  /**
   * Check whether any models have trained (non-random) weights.
   * Without trained weights, detection/classification output is random.
   */
  hasTrainedWeights(): boolean {
    // In the current version, models start with random weights.
    // This will return true once pre-trained weights are loaded.
    return false;
  }

  /**
   * Clean up all models and free GPU memory.
   */
  dispose(): void {
    disposeDetector();
    disposeClassifier();
    this._initialized = false;
    this._previousImageData = null;
    console.log('[RongleCNN] Disposed all models');
  }

  // -----------------------------------------------------------------------
  // Private
  // -----------------------------------------------------------------------

  private async _computeFrameDiff(base64: string): Promise<FrameDiff | null> {
    const currentImageData = await decodeToImageData(base64);

    if (!this._previousImageData) {
      this._previousImageData = currentImageData;
      this._previousHash = perceptualHash(currentImageData);
      return null; // No previous frame to compare
    }

    // Quick check: if perceptual hash is identical, skip detailed diff
    const currentHash = perceptualHash(currentImageData);
    if (currentHash === this._previousHash) {
      this._previousImageData = currentImageData;
      this._previousHash = currentHash;
      return {
        changePercent: 0,
        changedRegions: [],
        similarity: 1.0,
        timestamp: Date.now(),
      };
    }

    // Only compare if dimensions match
    if (
      currentImageData.width !== this._previousImageData.width ||
      currentImageData.height !== this._previousImageData.height
    ) {
      this._previousImageData = currentImageData;
      this._previousHash = currentHash;
      return null;
    }

    const diff = compareFrames(
      currentImageData,
      this._previousImageData,
      this.config.diffThreshold,
    );

    this._previousImageData = currentImageData;
    this._previousHash = currentHash;

    return diff;
  }
}

// ---------------------------------------------------------------------------
// Singleton instance — import and use directly
// ---------------------------------------------------------------------------

/** Global CNN instance. Import this in your React components. */
export const rongleCNN = new RongleCNN();

/** Also export the class for advanced usage (custom instances). */
export { RongleCNN };
