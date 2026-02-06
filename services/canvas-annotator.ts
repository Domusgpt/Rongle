/**
 * CanvasAnnotator — Set-of-Mark style frame annotation engine.
 *
 * Takes a raw camera frame and composites visual annotations onto it:
 *   - Numbered circle marks (like Set-of-Mark prompting)
 *   - Bounding boxes around detected elements
 *   - Zone overlays (allowed/blocked regions)
 *   - Text labels
 *
 * The composite image is what gets sent to the VLM, so the model can
 * reference elements by their mark number instead of re-detecting them.
 * This is more token-efficient and more accurate.
 *
 * Also generates a text prompt suffix describing all annotations.
 */

import type { Annotation, AnnotatedFrame, BoundingBox } from '../types';

// Mark colors — high contrast on any background
const MARK_COLORS = [
  '#FF3366', '#33FF66', '#3366FF', '#FFCC33',
  '#FF66CC', '#66FFCC', '#CC66FF', '#FF9933',
  '#33CCFF', '#FF3333', '#33FF33', '#3333FF',
];

let _markCounter = 0;

/**
 * Generate a unique annotation ID.
 */
function uid(): string {
  return `ann_${Date.now().toString(36)}_${(++_markCounter).toString(36)}`;
}

// ---------------------------------------------------------------------------
// Annotation builders
// ---------------------------------------------------------------------------

/**
 * Create a numbered mark annotation (colored circle with index).
 */
export function createMark(
  x: number, y: number,
  label: string,
  index?: number,
): Annotation {
  const idx = index ?? _markCounter;
  return {
    id: uid(),
    type: 'mark',
    x, y,
    label,
    color: MARK_COLORS[idx % MARK_COLORS.length],
    markIndex: idx,
  };
}

/**
 * Create a bounding box annotation.
 */
export function createBox(
  x: number, y: number,
  width: number, height: number,
  label: string,
  color?: string,
): Annotation {
  const idx = _markCounter;
  return {
    id: uid(),
    type: 'box',
    x, y, width, height,
    label,
    color: color || MARK_COLORS[idx % MARK_COLORS.length],
    markIndex: idx,
  };
}

/**
 * Create a zone overlay (semi-transparent rectangle).
 */
export function createZone(
  x: number, y: number,
  width: number, height: number,
  label: string,
  color = '#00FF4140',
): Annotation {
  return {
    id: uid(),
    type: 'zone',
    x, y, width, height,
    label,
    color,
  };
}

/**
 * Convert VisionAnalysisResult bounding boxes into annotations.
 */
export function annotationsFromDetections(boxes: BoundingBox[]): Annotation[] {
  _markCounter = 0;
  return boxes.map((box, i) => createBox(
    box.x, box.y, box.width, box.height,
    `[${i + 1}] ${box.label}`,
    MARK_COLORS[i % MARK_COLORS.length],
  ));
}

// ---------------------------------------------------------------------------
// Canvas rendering
// ---------------------------------------------------------------------------

/**
 * Render annotations onto an offscreen canvas.
 *
 * @param imageBase64  Raw camera frame (JPEG base64, no data: prefix)
 * @param annotations  Array of annotations to render
 * @returns Promise resolving to the composited base64 JPEG
 */
export async function renderAnnotatedFrame(
  imageBase64: string,
  annotations: Annotation[],
): Promise<string> {
  const img = await loadImage(`data:image/jpeg;base64,${imageBase64}`);
  const canvas = document.createElement('canvas');
  canvas.width = img.width;
  canvas.height = img.height;
  const ctx = canvas.getContext('2d')!;

  // Draw original frame
  ctx.drawImage(img, 0, 0);

  // Scale factors: annotations use normalized coords (0-100) or pixel coords
  // We'll support pixel coords directly since that's what the VLM returns
  for (const ann of annotations) {
    switch (ann.type) {
      case 'mark':
        drawMark(ctx, ann);
        break;
      case 'box':
        drawBox(ctx, ann);
        break;
      case 'zone':
        drawZone(ctx, ann);
        break;
      case 'label':
        drawLabel(ctx, ann);
        break;
      case 'arrow':
        drawArrow(ctx, ann);
        break;
    }
  }

  // Export as JPEG base64 (strip data: prefix)
  const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
  return dataUrl.split(',')[1];
}

function drawMark(ctx: CanvasRenderingContext2D, ann: Annotation) {
  const r = 14;
  const x = ann.x;
  const y = ann.y;

  // Outer circle with glow
  ctx.beginPath();
  ctx.arc(x, y, r + 2, 0, Math.PI * 2);
  ctx.fillStyle = 'rgba(0,0,0,0.7)';
  ctx.fill();

  ctx.beginPath();
  ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.fillStyle = ann.color;
  ctx.fill();

  // Number
  ctx.fillStyle = '#FFFFFF';
  ctx.font = 'bold 14px sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(String(ann.markIndex ?? ''), x, y);

  // Label below
  if (ann.label) {
    ctx.font = '11px sans-serif';
    ctx.fillStyle = ann.color;
    const tw = ctx.measureText(ann.label).width;
    ctx.fillStyle = 'rgba(0,0,0,0.8)';
    ctx.fillRect(x - tw / 2 - 3, y + r + 2, tw + 6, 16);
    ctx.fillStyle = ann.color;
    ctx.fillText(ann.label, x, y + r + 12);
  }
}

function drawBox(ctx: CanvasRenderingContext2D, ann: Annotation) {
  const w = ann.width || 50;
  const h = ann.height || 50;

  // Box outline
  ctx.strokeStyle = ann.color;
  ctx.lineWidth = 2;
  ctx.setLineDash([]);
  ctx.strokeRect(ann.x, ann.y, w, h);

  // Corner accents
  const corner = 8;
  ctx.lineWidth = 3;
  // Top-left
  ctx.beginPath();
  ctx.moveTo(ann.x, ann.y + corner);
  ctx.lineTo(ann.x, ann.y);
  ctx.lineTo(ann.x + corner, ann.y);
  ctx.stroke();
  // Top-right
  ctx.beginPath();
  ctx.moveTo(ann.x + w - corner, ann.y);
  ctx.lineTo(ann.x + w, ann.y);
  ctx.lineTo(ann.x + w, ann.y + corner);
  ctx.stroke();
  // Bottom-left
  ctx.beginPath();
  ctx.moveTo(ann.x, ann.y + h - corner);
  ctx.lineTo(ann.x, ann.y + h);
  ctx.lineTo(ann.x + corner, ann.y + h);
  ctx.stroke();
  // Bottom-right
  ctx.beginPath();
  ctx.moveTo(ann.x + w - corner, ann.y + h);
  ctx.lineTo(ann.x + w, ann.y + h);
  ctx.lineTo(ann.x + w, ann.y + h - corner);
  ctx.stroke();

  // Label tag
  if (ann.label) {
    ctx.font = 'bold 11px sans-serif';
    const tw = ctx.measureText(ann.label).width;
    ctx.fillStyle = ann.color;
    ctx.fillRect(ann.x, ann.y - 18, tw + 8, 18);
    ctx.fillStyle = '#000000';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    ctx.fillText(ann.label, ann.x + 4, ann.y - 9);
  }
}

function drawZone(ctx: CanvasRenderingContext2D, ann: Annotation) {
  ctx.fillStyle = ann.color;
  ctx.fillRect(ann.x, ann.y, ann.width || 100, ann.height || 100);

  ctx.strokeStyle = ann.color.slice(0, 7); // strip alpha
  ctx.lineWidth = 1;
  ctx.setLineDash([6, 4]);
  ctx.strokeRect(ann.x, ann.y, ann.width || 100, ann.height || 100);
  ctx.setLineDash([]);

  if (ann.label) {
    ctx.font = '10px sans-serif';
    ctx.fillStyle = ann.color.slice(0, 7);
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    ctx.fillText(ann.label, ann.x + 4, ann.y + 4);
  }
}

function drawLabel(ctx: CanvasRenderingContext2D, ann: Annotation) {
  ctx.font = '12px sans-serif';
  const tw = ctx.measureText(ann.label).width;
  ctx.fillStyle = 'rgba(0,0,0,0.8)';
  ctx.fillRect(ann.x - 2, ann.y - 14, tw + 4, 18);
  ctx.fillStyle = ann.color;
  ctx.textAlign = 'left';
  ctx.textBaseline = 'middle';
  ctx.fillText(ann.label, ann.x, ann.y - 5);
}

function drawArrow(ctx: CanvasRenderingContext2D, ann: Annotation) {
  const ex = ann.width ?? ann.x + 50;
  const ey = ann.height ?? ann.y + 50;

  ctx.strokeStyle = ann.color;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(ann.x, ann.y);
  ctx.lineTo(ex, ey);
  ctx.stroke();

  // Arrowhead
  const angle = Math.atan2(ey - ann.y, ex - ann.x);
  const headLen = 10;
  ctx.beginPath();
  ctx.moveTo(ex, ey);
  ctx.lineTo(
    ex - headLen * Math.cos(angle - Math.PI / 6),
    ey - headLen * Math.sin(angle - Math.PI / 6),
  );
  ctx.lineTo(
    ex - headLen * Math.cos(angle + Math.PI / 6),
    ey - headLen * Math.sin(angle + Math.PI / 6),
  );
  ctx.closePath();
  ctx.fillStyle = ann.color;
  ctx.fill();
}

// ---------------------------------------------------------------------------
// Prompt generation
// ---------------------------------------------------------------------------

/**
 * Generate a text description of all annotations for the VLM prompt.
 *
 * Example output:
 *   "The image has numbered markers: [1] 'Settings button' at (540, 320),
 *    [2] 'OK button' at (960, 700). Refer to elements by their number."
 */
export function generateAnnotationPrompt(annotations: Annotation[]): string {
  if (annotations.length === 0) return '';

  const marks = annotations.filter(a => a.markIndex !== undefined);
  if (marks.length === 0) return '';

  const items = marks.map(a => {
    const pos = a.width && a.height
      ? `bbox (${a.x},${a.y},${a.x + a.width},${a.y + a.height})`
      : `at (${a.x},${a.y})`;
    return `[${a.markIndex}] "${a.label}" ${pos}`;
  });

  return (
    '\n\nThe image has numbered markers overlaid on it: ' +
    items.join(', ') +
    '. Refer to elements by their [number] when describing actions. ' +
    'Coordinates are in image pixels.'
  );
}

/**
 * Build a complete AnnotatedFrame from a raw capture and annotations.
 */
export async function buildAnnotatedFrame(
  rawBase64: string,
  annotations: Annotation[],
): Promise<AnnotatedFrame> {
  const compositeBase64 = annotations.length > 0
    ? await renderAnnotatedFrame(rawBase64, annotations)
    : rawBase64;

  return {
    originalBase64: rawBase64,
    compositeBase64,
    annotations,
    promptSuffix: generateAnnotationPrompt(annotations),
    timestamp: Date.now(),
  };
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------
function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });
}
