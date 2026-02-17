// ---------------------------------------------------------------------------
// Preprocessor — Fast canvas-based image preparation for CNN inference.
//
// Uses OffscreenCanvas (or fallback <canvas>) for GPU-accelerated resize
// and normalisation.  Outputs Float32Array tensors ready for tf.tensor4d().
// ---------------------------------------------------------------------------

/**
 * Decode a base64 JPEG/PNG string into an ImageBitmap (non-blocking).
 */
export async function decodeBase64(base64: string): Promise<ImageBitmap> {
  const binary = atob(base64.replace(/^data:image\/\w+;base64,/, ''));
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  const blob = new Blob([bytes], { type: 'image/jpeg' });
  return createImageBitmap(blob);
}

/**
 * Resize an ImageBitmap or HTMLVideoElement to targetSize x targetSize
 * using a canvas draw.  Returns the canvas for further use.
 */
export function resizeToCanvas(
  source: ImageBitmap | HTMLVideoElement | HTMLCanvasElement,
  targetSize: number,
): OffscreenCanvas | HTMLCanvasElement {
  let canvas: OffscreenCanvas | HTMLCanvasElement;
  let ctx: OffscreenCanvasRenderingContext2D | CanvasRenderingContext2D;

  if (typeof OffscreenCanvas !== 'undefined') {
    canvas = new OffscreenCanvas(targetSize, targetSize);
    ctx = canvas.getContext('2d')!;
  } else {
    canvas = document.createElement('canvas');
    canvas.width = targetSize;
    canvas.height = targetSize;
    ctx = canvas.getContext('2d')!;
  }

  ctx.drawImage(source, 0, 0, targetSize, targetSize);
  return canvas;
}

/**
 * Extract pixel data from a canvas and normalise to [0, 1] Float32Array.
 * Layout: NHWC — [1, height, width, 3] flattened.
 */
export function canvasToFloat32(
  canvas: OffscreenCanvas | HTMLCanvasElement,
  size: number,
): Float32Array {
  let ctx: OffscreenCanvasRenderingContext2D | CanvasRenderingContext2D;
  if (canvas instanceof OffscreenCanvas) {
    ctx = canvas.getContext('2d')!;
  } else {
    ctx = canvas.getContext('2d')!;
  }

  const imageData = ctx.getImageData(0, 0, size, size);
  const { data } = imageData;
  const float32 = new Float32Array(size * size * 3);

  // RGBA → RGB, normalise 0..255 → 0..1
  for (let i = 0, j = 0; i < data.length; i += 4, j += 3) {
    float32[j]     = data[i]     / 255;
    float32[j + 1] = data[i + 1] / 255;
    float32[j + 2] = data[i + 2] / 255;
  }

  return float32;
}

/**
 * Full pipeline: base64 → resized Float32Array tensor + canvas.
 * Returns both the tensor data and the resized canvas (for display).
 */
export async function preprocessFrame(
  base64: string,
  targetSize: number,
): Promise<{ tensor: Float32Array; canvas: OffscreenCanvas | HTMLCanvasElement }> {
  const bitmap = await decodeBase64(base64);
  const canvas = resizeToCanvas(bitmap, targetSize);
  const tensor = canvasToFloat32(canvas, targetSize);
  bitmap.close();
  return { tensor, canvas };
}

/**
 * Same pipeline but from a live HTMLVideoElement (zero-copy path).
 */
export function preprocessVideo(
  video: HTMLVideoElement,
  targetSize: number,
): { tensor: Float32Array; canvas: OffscreenCanvas | HTMLCanvasElement } {
  const canvas = resizeToCanvas(video, targetSize);
  const tensor = canvasToFloat32(canvas, targetSize);
  return { tensor, canvas };
}

/**
 * Extract raw RGBA Uint8ClampedArray from a base64 image at original size.
 * Useful for the frame-differ which operates on full-res pixels.
 */
export async function decodeToImageData(
  base64: string,
): Promise<ImageData> {
  const bitmap = await decodeBase64(base64);
  let canvas: OffscreenCanvas | HTMLCanvasElement;
  let ctx: OffscreenCanvasRenderingContext2D | CanvasRenderingContext2D;

  if (typeof OffscreenCanvas !== 'undefined') {
    canvas = new OffscreenCanvas(bitmap.width, bitmap.height);
    ctx = canvas.getContext('2d')!;
  } else {
    canvas = document.createElement('canvas');
    canvas.width = bitmap.width;
    canvas.height = bitmap.height;
    ctx = canvas.getContext('2d')!;
  }

  ctx.drawImage(bitmap, 0, 0);
  bitmap.close();
  return ctx.getImageData(0, 0, canvas.width, canvas.height);
}

/**
 * Convert an ImageData to grayscale Uint8Array (single channel).
 * Uses luminance formula: 0.299R + 0.587G + 0.114B
 */
export function toGrayscale(imageData: ImageData): Uint8Array {
  const { data, width, height } = imageData;
  const gray = new Uint8Array(width * height);
  for (let i = 0, j = 0; i < data.length; i += 4, j++) {
    gray[j] = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
  }
  return gray;
}
