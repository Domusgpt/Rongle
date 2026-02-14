import React, { useRef, useEffect, useState, useCallback } from 'react';
import type { Annotation, BoundingBox, VisionAnalysisResult } from '../types';
import { annotationsFromDetections, renderAnnotatedFrame, createMark } from '../services/canvas-annotator';
import { Crosshair, Tag, Trash2, Layers } from 'lucide-react';

interface AnnotationCanvasProps {
  /** Raw camera frame as base64 JPEG (no data: prefix) */
  frameBase64: string | null;
  /** Detected elements from the last VLM analysis */
  analysis: VisionAnalysisResult | null;
  /** Whether auto-annotation of detected elements is enabled */
  autoAnnotate: boolean;
  /** Called when annotations change (new composite ready) */
  onAnnotationsChange: (annotations: Annotation[], compositeBase64: string) => void;
}

export const AnnotationCanvas: React.FC<AnnotationCanvasProps> = ({
  frameBase64,
  analysis,
  autoAnnotate,
  onAnnotationsChange,
}) => {
  const displayCanvasRef = useRef<HTMLCanvasElement>(null);
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [isDrawing, setIsDrawing] = useState(false);
  const [markMode, setMarkMode] = useState(false);
  const imgRef = useRef<HTMLImageElement | null>(null);

  // Load the frame image whenever it changes
  useEffect(() => {
    if (!frameBase64) return;
    const img = new Image();
    img.onload = () => {
      imgRef.current = img;
      redraw(img, annotations);
    };
    img.src = `data:image/jpeg;base64,${frameBase64}`;
  }, [frameBase64]);

  // Auto-annotate detected elements
  useEffect(() => {
    if (!autoAnnotate || !analysis?.detectedElements?.length) return;
    const newAnns = annotationsFromDetections(analysis.detectedElements);
    setAnnotations(newAnns);
  }, [analysis, autoAnnotate]);

  // Re-render and emit whenever annotations change
  useEffect(() => {
    if (!frameBase64) return;
    if (imgRef.current) {
      redraw(imgRef.current, annotations);
    }
    // Generate composite
    renderAnnotatedFrame(frameBase64, annotations).then(composite => {
      onAnnotationsChange(annotations, composite);
    });
  }, [annotations, frameBase64]);

  const redraw = useCallback((img: HTMLImageElement, anns: Annotation[]) => {
    const canvas = displayCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    canvas.width = img.width;
    canvas.height = img.height;
    ctx.drawImage(img, 0, 0);

    // Draw annotations on the display canvas
    for (const ann of anns) {
      if (ann.type === 'mark') {
        drawMarkOnCtx(ctx, ann);
      } else if (ann.type === 'box') {
        drawBoxOnCtx(ctx, ann);
      }
    }
  }, []);

  // Handle tap/click to place a mark
  const handleCanvasClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!markMode || !displayCanvasRef.current) return;

    const canvas = displayCanvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const x = Math.round((e.clientX - rect.left) * scaleX);
    const y = Math.round((e.clientY - rect.top) * scaleY);

    const mark = createMark(x, y, `Target ${annotations.length + 1}`, annotations.length + 1);
    setAnnotations(prev => [...prev, mark]);
    setMarkMode(false);
  }, [markMode, annotations]);

  // Touch support for mobile
  const handleCanvasTouch = useCallback((e: React.TouchEvent<HTMLCanvasElement>) => {
    if (!markMode || !displayCanvasRef.current) return;
    e.preventDefault();

    const canvas = displayCanvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const touch = e.touches[0];
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const x = Math.round((touch.clientX - rect.left) * scaleX);
    const y = Math.round((touch.clientY - rect.top) * scaleY);

    const mark = createMark(x, y, `Target ${annotations.length + 1}`, annotations.length + 1);
    setAnnotations(prev => [...prev, mark]);
    setMarkMode(false);
  }, [markMode, annotations]);

  const clearAnnotations = () => setAnnotations([]);

  return (
    <div className="relative">
      {/* Canvas */}
      <canvas
        ref={displayCanvasRef}
        className={`w-full rounded border ${markMode ? 'border-terminal-amber cursor-crosshair' : 'border-industrial-600'}`}
        onClick={handleCanvasClick}
        onTouchStart={handleCanvasTouch}
      />

      {/* Annotation toolbar */}
      <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between bg-black/70 rounded px-2 py-1">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setMarkMode(!markMode)}
            className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-mono transition-colors ${
              markMode ? 'bg-terminal-amber text-black' : 'bg-industrial-700 text-gray-300 hover:bg-industrial-600'
            }`}
          >
            <Crosshair size={12} />
            {markMode ? 'TAP TO MARK' : 'MARK'}
          </button>
          <button
            onClick={clearAnnotations}
            className="flex items-center gap-1 px-2 py-1 rounded text-xs font-mono bg-industrial-700 text-gray-300 hover:bg-industrial-600 transition-colors"
          >
            <Trash2 size={12} />
            CLEAR
          </button>
        </div>
        <div className="flex items-center gap-1 text-xs font-mono text-gray-400">
          <Layers size={12} />
          {annotations.length} marks
        </div>
      </div>

      {/* Mark mode indicator */}
      {markMode && (
        <div className="absolute top-2 left-2 bg-terminal-amber/90 text-black px-2 py-1 rounded text-xs font-bold animate-pulse">
          TAP ON SCREEN TO PLACE MARK
        </div>
      )}

      {/* No frame placeholder */}
      {!frameBase64 && (
        <div className="absolute inset-0 flex items-center justify-center bg-industrial-900/80 text-gray-500 text-sm font-mono">
          <Tag size={24} className="mr-2 opacity-50" />
          NO FRAME CAPTURED
        </div>
      )}
    </div>
  );
};

// Simple canvas draw helpers (display only — export rendering uses canvas-annotator.ts)
function drawMarkOnCtx(ctx: CanvasRenderingContext2D, ann: Annotation) {
  const r = 14;
  ctx.beginPath();
  ctx.arc(ann.x, ann.y, r + 2, 0, Math.PI * 2);
  ctx.fillStyle = 'rgba(0,0,0,0.7)';
  ctx.fill();
  ctx.beginPath();
  ctx.arc(ann.x, ann.y, r, 0, Math.PI * 2);
  ctx.fillStyle = ann.color;
  ctx.fill();
  ctx.fillStyle = '#FFF';
  ctx.font = 'bold 14px sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(String(ann.markIndex ?? ''), ann.x, ann.y);
}

function drawBoxOnCtx(ctx: CanvasRenderingContext2D, ann: Annotation) {
  ctx.strokeStyle = ann.color;
  ctx.lineWidth = 2;
  ctx.strokeRect(ann.x, ann.y, ann.width || 50, ann.height || 50);
  if (ann.label) {
    ctx.font = 'bold 11px sans-serif';
    const tw = ctx.measureText(ann.label).width;
    ctx.fillStyle = ann.color;
    ctx.fillRect(ann.x, ann.y - 18, tw + 8, 18);
    ctx.fillStyle = '#000';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    ctx.fillText(ann.label, ann.x + 4, ann.y - 9);
  }
}
