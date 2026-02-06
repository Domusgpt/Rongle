// ---------------------------------------------------------------------------
// Engine — TensorFlow.js backend management, model lifecycle, and warmup.
//
// Lazy-loads TF.js from the importmap.  If TF.js fails to load, the engine
// degrades gracefully: frame-differ and preprocessor still work, only model
// inference is disabled.
// ---------------------------------------------------------------------------

import type { EngineStatus } from './types';

// TF.js is loaded lazily to avoid blocking app startup
let tf: any = null;
let _backendReady = false;
let _backendName = 'none';

/**
 * Lazy-load TensorFlow.js.  Returns the `tf` namespace or null if unavailable.
 */
export async function loadTF(): Promise<any> {
  if (tf) return tf;
  try {
    tf = await import('@tensorflow/tfjs');
    return tf;
  } catch (e) {
    console.warn('[CNN Engine] TF.js not available — model inference disabled.', e);
    return null;
  }
}

/**
 * Initialise the best available TF.js backend.
 *
 * Priority: webgl > wasm > cpu
 * On Android Chrome, WebGL is almost always available and gives 5-10x
 * speedup over CPU for convolutions.
 */
export async function initBackend(preferred?: 'webgl' | 'wasm' | 'cpu'): Promise<string> {
  const lib = await loadTF();
  if (!lib) return 'none';

  const backends = preferred ? [preferred, 'webgl', 'wasm', 'cpu'] : ['webgl', 'wasm', 'cpu'];

  for (const backend of backends) {
    try {
      await lib.setBackend(backend);
      await lib.ready();
      _backendReady = true;
      _backendName = backend;
      console.log(`[CNN Engine] Backend ready: ${backend}`);
      return backend;
    } catch {
      console.warn(`[CNN Engine] Backend "${backend}" unavailable, trying next...`);
    }
  }

  _backendName = 'none';
  console.error('[CNN Engine] No TF.js backend available');
  return 'none';
}

/**
 * Get the TF.js namespace.  Throws if not loaded.
 */
export function getTF(): any {
  if (!tf) throw new Error('TF.js not loaded — call loadTF() first');
  return tf;
}

/**
 * Check whether TF.js is loaded and a backend is ready.
 */
export function isReady(): boolean {
  return tf !== null && _backendReady;
}

/**
 * Get current backend name.
 */
export function getBackend(): string {
  return _backendName;
}

// ---------------------------------------------------------------------------
// Model cache (IndexedDB for offline use)
// ---------------------------------------------------------------------------
const MODEL_CACHE_PREFIX = 'rongle-cnn-';

/**
 * Save a TF.js LayersModel to IndexedDB.
 */
export async function saveModel(model: any, name: string): Promise<void> {
  if (!model?.save) return;
  try {
    await model.save(`indexeddb://${MODEL_CACHE_PREFIX}${name}`);
    console.log(`[CNN Engine] Model "${name}" cached to IndexedDB`);
  } catch (e) {
    console.warn(`[CNN Engine] Failed to cache model "${name}":`, e);
  }
}

/**
 * Load a TF.js LayersModel from IndexedDB cache.
 * Returns null if not cached.
 */
export async function loadCachedModel(name: string): Promise<any | null> {
  const lib = await loadTF();
  if (!lib) return null;
  try {
    const model = await lib.loadLayersModel(`indexeddb://${MODEL_CACHE_PREFIX}${name}`);
    console.log(`[CNN Engine] Model "${name}" loaded from IndexedDB cache`);
    return model;
  } catch {
    return null;
  }
}

/**
 * Load a TF.js LayersModel from a URL (model.json + weight shards).
 * Falls back to IndexedDB cache if fetch fails.
 */
export async function loadModelFromURL(url: string, name: string): Promise<any | null> {
  const lib = await loadTF();
  if (!lib) return null;

  try {
    const model = await lib.loadLayersModel(url);
    // Cache for offline use
    await saveModel(model, name);
    console.log(`[CNN Engine] Model "${name}" loaded from ${url}`);
    return model;
  } catch (e) {
    console.warn(`[CNN Engine] Failed to load model from URL, trying cache:`, e);
    return loadCachedModel(name);
  }
}

// ---------------------------------------------------------------------------
// Warmup — pre-compile WebGL shaders by running a dummy inference
// ---------------------------------------------------------------------------

/**
 * Run a single dummy inference to warm up WebGL shader compilation.
 * This prevents the first real inference from having a 500ms+ delay.
 */
export async function warmupModel(model: any, inputShape: number[]): Promise<number> {
  const lib = await loadTF();
  if (!lib || !model) return -1;

  const t0 = performance.now();
  const dummyInput = lib.zeros([1, ...inputShape]);

  try {
    const output = model.predict(dummyInput);
    // Dispose outputs (handles single tensor or array of tensors)
    if (Array.isArray(output)) {
      output.forEach((t: any) => t.dispose());
    } else {
      output.dispose();
    }
  } catch (e) {
    console.warn('[CNN Engine] Warmup inference failed:', e);
  }

  dummyInput.dispose();
  const elapsed = performance.now() - t0;
  console.log(`[CNN Engine] Warmup completed in ${elapsed.toFixed(1)}ms`);
  return elapsed;
}

// ---------------------------------------------------------------------------
// Performance tracking
// ---------------------------------------------------------------------------
const _inferenceTimes: number[] = [];
const MAX_HISTORY = 50;

export function recordInferenceTime(ms: number): void {
  _inferenceTimes.push(ms);
  if (_inferenceTimes.length > MAX_HISTORY) _inferenceTimes.shift();
}

export function getAverageInferenceMs(): number {
  if (_inferenceTimes.length === 0) return 0;
  const sum = _inferenceTimes.reduce((a, b) => a + b, 0);
  return sum / _inferenceTimes.length;
}

export function getInferenceFPS(): number {
  const avg = getAverageInferenceMs();
  return avg > 0 ? 1000 / avg : 0;
}

/**
 * Full engine status snapshot.
 */
export function getStatus(detectorLoaded: boolean, classifierLoaded: boolean, warmupDone: boolean): EngineStatus {
  return {
    ready: isReady(),
    backend: _backendName,
    detectorLoaded,
    classifierLoaded,
    warmupDone,
    avgInferenceMs: Math.round(getAverageInferenceMs()),
    fps: Math.round(getInferenceFPS()),
  };
}

// ---------------------------------------------------------------------------
// Tensor utilities
// ---------------------------------------------------------------------------

/**
 * Create a TF.js tensor from a Float32Array, handling the batch dimension.
 */
export function createTensor4D(
  data: Float32Array,
  height: number,
  width: number,
  channels: number = 3,
): any {
  const lib = getTF();
  return lib.tensor4d(data, [1, height, width, channels]);
}

/**
 * Run inference and extract Float32Arrays from output tensors.
 * Automatically disposes input and output tensors.
 */
export async function runInference(
  model: any,
  inputTensor: any,
): Promise<Float32Array[]> {
  const output = model.predict(inputTensor);
  inputTensor.dispose();

  const outputs: Float32Array[] = [];
  if (Array.isArray(output)) {
    for (const t of output) {
      outputs.push(await t.data());
      t.dispose();
    }
  } else {
    outputs.push(await output.data());
    output.dispose();
  }

  return outputs;
}
