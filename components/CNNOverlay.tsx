import React, { useEffect, useRef, useMemo } from 'react';
import type { Detection, Classification, FrameDiff, EngineStatus } from '../services/cnn';

interface CNNOverlayProps {
  /** Detected UI elements from the CNN detector. */
  detections: Detection[];
  /** Screen classification result. */
  classification: Classification | null;
  /** Frame diff result (null = no previous frame). */
  frameDiff: FrameDiff | null;
  /** Engine status for the status bar. */
  engineStatus: EngineStatus;
  /** Container width/height for coordinate mapping. */
  containerWidth: number;
  containerHeight: number;
  /** Original image dimensions (for scaling boxes). */
  imageWidth: number;
  imageHeight: number;
  /** Whether to show detection boxes. */
  showDetections?: boolean;
  /** Whether to show change regions. */
  showChanges?: boolean;
  /** Whether to show the status bar. */
  showStatus?: boolean;
}

// Color palette for different UI element classes
const CLASS_COLORS: Record<string, string> = {
  button: '#00ff41',
  text_input: '#00ccff',
  link: '#ff6b35',
  icon: '#a855f7',
  dropdown: '#f59e0b',
  checkbox: '#10b981',
  radio: '#10b981',
  toggle: '#3b82f6',
  slider: '#8b5cf6',
  tab: '#ec4899',
  menu_item: '#f97316',
  image: '#6366f1',
  heading: '#ffffff',
  paragraph: '#94a3b8',
  dialog: '#ef4444',
  toolbar: '#64748b',
  cursor: '#ff0033',
};

/**
 * CNNOverlay renders detection bounding boxes, change regions, and
 * an engine status bar on top of the camera feed.
 *
 * Uses a canvas overlay for precise rendering at 60fps.
 */
export function CNNOverlay({
  detections,
  classification,
  frameDiff,
  engineStatus,
  containerWidth,
  containerHeight,
  imageWidth,
  imageHeight,
  showDetections = true,
  showChanges = true,
  showStatus = true,
}: CNNOverlayProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Scale factors: image coords → container coords
  const scaleX = containerWidth / (imageWidth || 1);
  const scaleY = containerHeight / (imageHeight || 1);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    canvas.width = containerWidth;
    canvas.height = containerHeight;
    ctx.clearRect(0, 0, containerWidth, containerHeight);

    // Draw change regions (subtle blue overlay)
    if (showChanges && frameDiff && frameDiff.changedRegions.length > 0) {
      ctx.fillStyle = 'rgba(0, 120, 255, 0.08)';
      ctx.strokeStyle = 'rgba(0, 120, 255, 0.3)';
      ctx.lineWidth = 1;
      for (const region of frameDiff.changedRegions) {
        const x = region.x * scaleX;
        const y = region.y * scaleY;
        const w = region.width * scaleX;
        const h = region.height * scaleY;
        ctx.fillRect(x, y, w, h);
        ctx.strokeRect(x, y, w, h);
      }
    }

    // Draw detection boxes
    if (showDetections && detections.length > 0) {
      for (const det of detections) {
        const color = CLASS_COLORS[det.class] || '#00ff41';
        const x = det.bbox.x * scaleX;
        const y = det.bbox.y * scaleY;
        const w = det.bbox.width * scaleX;
        const h = det.bbox.height * scaleY;

        // Box outline
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.strokeRect(x, y, w, h);

        // Corner accents (4px square at each corner)
        ctx.fillStyle = color;
        const cs = 6; // corner size
        ctx.fillRect(x - 1, y - 1, cs, 2);
        ctx.fillRect(x - 1, y - 1, 2, cs);
        ctx.fillRect(x + w - cs + 1, y - 1, cs, 2);
        ctx.fillRect(x + w - 1, y - 1, 2, cs);
        ctx.fillRect(x - 1, y + h - 1, cs, 2);
        ctx.fillRect(x - 1, y + h - cs + 1, 2, cs);
        ctx.fillRect(x + w - cs + 1, y + h - 1, cs, 2);
        ctx.fillRect(x + w - 1, y + h - cs + 1, 2, cs);

        // Label background
        const label = `${det.label} ${(det.confidence * 100).toFixed(0)}%`;
        ctx.font = '10px JetBrains Mono, monospace';
        const metrics = ctx.measureText(label);
        const labelH = 14;
        const labelW = metrics.width + 6;
        const labelY = y - labelH - 2;

        ctx.fillStyle = color;
        ctx.globalAlpha = 0.85;
        ctx.fillRect(x, Math.max(0, labelY), labelW, labelH);
        ctx.globalAlpha = 1.0;

        // Label text
        ctx.fillStyle = '#000000';
        ctx.fillText(label, x + 3, Math.max(10, labelY + 10));
      }
    }
  }, [detections, frameDiff, containerWidth, containerHeight, scaleX, scaleY, showDetections, showChanges]);

  // Format change percentage for display
  const changeText = frameDiff
    ? `${(frameDiff.changePercent * 100).toFixed(1)}% changed | SSIM: ${frameDiff.similarity.toFixed(3)}`
    : 'No diff data';

  return (
    <div className="absolute inset-0 pointer-events-none">
      {/* Detection canvas */}
      <canvas
        ref={canvasRef}
        className="absolute inset-0 w-full h-full"
        style={{ imageRendering: 'pixelated' }}
      />

      {/* Status bar */}
      {showStatus && (
        <div className="absolute bottom-0 left-0 right-0 bg-black/70 px-2 py-1 flex items-center justify-between text-[9px] font-mono">
          {/* Engine status */}
          <div className="flex items-center gap-2">
            <span className={engineStatus.ready ? 'text-terminal-green' : 'text-gray-500'}>
              {engineStatus.backend.toUpperCase()}
            </span>
            {engineStatus.detectorLoaded && (
              <span className="text-terminal-blue">DET</span>
            )}
            {engineStatus.classifierLoaded && (
              <span className="text-purple-400">CLS</span>
            )}
            <span className="text-gray-500">|</span>
            <span className="text-gray-400">{engineStatus.avgInferenceMs}ms</span>
            <span className="text-gray-400">{engineStatus.fps} FPS</span>
          </div>

          {/* Classification */}
          {classification && (
            <div className="flex items-center gap-1">
              <span className="text-terminal-amber">
                {classification.class.toUpperCase()}
              </span>
              <span className="text-gray-500">
                {(classification.confidence * 100).toFixed(0)}%
              </span>
            </div>
          )}

          {/* Detection count + change info */}
          <div className="flex items-center gap-2">
            {detections.length > 0 && (
              <span className="text-terminal-green">{detections.length} elem</span>
            )}
            {frameDiff && frameDiff.changePercent > 0.01 && (
              <span className="text-terminal-blue">
                {(frameDiff.changePercent * 100).toFixed(0)}%
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
