import React, { useEffect, useRef, useState, useCallback } from 'react';
import { VisionAnalysisResult, AgentStatus } from '../types';
import type { Annotation } from '../types';
import { AnnotationCanvas } from './AnnotationCanvas';
import { WebRTCStreamer } from '../services/webrtc-streamer';
import { Scan, AlertCircle, Camera, Layers, Cast } from 'lucide-react';

interface LiveViewProps {
  status: AgentStatus;
  analysis: VisionAnalysisResult | null;
  onCaptureFrame: (base64: string) => void;
  onAnnotatedFrame?: (annotations: Annotation[], compositeBase64: string) => void;
  isProcessing: boolean;
  annotationsEnabled: boolean;
  onCameraActive?: (active: boolean) => void;
  streamToBackend?: boolean;
  backendUrl?: string;
  apiKey?: string;
}

export const LiveView: React.FC<LiveViewProps> = ({
  status, analysis, onCaptureFrame, onAnnotatedFrame, isProcessing,
  annotationsEnabled, onCameraActive, streamToBackend = false,
  backendUrl = 'http://localhost:8080', apiKey
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamerRef = useRef<WebRTCStreamer | null>(null);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [lastFrameBase64, setLastFrameBase64] = useState<string | null>(null);
  const [showAnnotations, setShowAnnotations] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);

  // Initialize Camera (Mobile Back Camera)
  useEffect(() => {
    let mounted = true;
    const startVideo = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: 'environment',
            width: { ideal: 1920 },
            height: { ideal: 1080 }
          }
        });
        if (mounted && videoRef.current) {
          videoRef.current.srcObject = stream;
          setStreamError(null);
          onCameraActive?.(true);
        } else {
          stream.getTracks().forEach(t => t.stop());
        }
      } catch (err) {
        console.error("Camera access denied:", err);
        if (mounted) {
          setStreamError("CAMERA ACCESS DENIED");
          onCameraActive?.(false);
        }
      }
    };
    startVideo();

    return () => {
      mounted = false;
      // Cleanup camera on unmount
      if (videoRef.current?.srcObject) {
        const tracks = (videoRef.current.srcObject as MediaStream).getTracks();
        tracks.forEach(t => t.stop());
      }
    };
  }, []);

  // WebRTC Streaming
  useEffect(() => {
    const handleStreaming = async () => {
      if (streamToBackend && backendUrl && videoRef.current?.srcObject) {
        if (!streamerRef.current) {
          streamerRef.current = new WebRTCStreamer(backendUrl);
        }
        try {
          const stream = videoRef.current.srcObject as MediaStream;
          await streamerRef.current.start(stream, apiKey);
          setIsStreaming(true);
        } catch (err) {
          console.error("Streaming failed:", err);
          setIsStreaming(false);
        }
      } else {
        if (streamerRef.current) {
          streamerRef.current.stop();
          streamerRef.current = null;
        }
        setIsStreaming(false);
      }
    };

    handleStreaming();

    return () => {
      streamerRef.current?.stop();
    };
  }, [streamToBackend, backendUrl]); // Re-run if props change

  // Capture frame when entering PERCEIVING state
  useEffect(() => {
    if (!isProcessing && status === AgentStatus.PERCEIVING) {
      const timer = setTimeout(() => {
        if (videoRef.current && canvasRef.current) {
          const video = videoRef.current;
          const canvas = canvasRef.current;
          const context = canvas.getContext('2d');

          if (context && video.videoWidth > 0) {
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            context.drawImage(video, 0, 0, canvas.width, canvas.height);

            const dataUrl = canvas.toDataURL('image/jpeg', 0.8);
            const base64 = dataUrl.split(',')[1];
            setLastFrameBase64(base64);
            onCaptureFrame(base64);
          }
        }
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [status, isProcessing, onCaptureFrame]);

  // Handle annotation changes
  const handleAnnotationsChange = useCallback((annotations: Annotation[], compositeBase64: string) => {
    onAnnotatedFrame?.(annotations, compositeBase64);
  }, [onAnnotatedFrame]);

  const getClickTargetStyle = () => {
    if (!analysis?.coordinates) return {};
    return {
      left: `${analysis.coordinates.x}%`,
      top: `${analysis.coordinates.y}%`,
    };
  };

  return (
    <div className="relative w-full bg-black rounded-lg border border-industrial-600 overflow-hidden group shadow-2xl">
      {/* Live video feed */}
      <div className={`relative aspect-video ${showAnnotations ? 'hidden' : 'block'}`}>
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className="w-full h-full object-cover opacity-80"
        />

        <canvas ref={canvasRef} className="hidden" />

        {streamError && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-industrial-900/90 text-terminal-red">
            <AlertCircle size={48} className="mb-4" />
            <p className="font-mono font-bold text-lg">{streamError}</p>
            <p className="text-sm text-gray-500 mt-2 text-center px-4">
              Ensure camera permissions are enabled.
            </p>
          </div>
        )}

        {/* Overlays */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute inset-0 bg-gradient-to-b from-transparent via-terminal-green/5 to-transparent h-[10%] w-full animate-scanline opacity-20"></div>

          {isProcessing && (
            <div className="absolute inset-0 border-2 border-terminal-amber/50 animate-pulse bg-terminal-amber/5 flex items-center justify-center">
              <div className="bg-black/70 px-4 py-2 rounded text-terminal-amber font-mono text-sm flex items-center gap-2">
                <Scan className="animate-spin" size={16} />
                ANALYZING SCENE...
              </div>
            </div>
          )}

          {analysis?.coordinates && !isProcessing && (
            <>
              <div
                className="absolute w-6 h-6 -ml-3 -mt-3 border-2 border-terminal-blue rounded-full animate-ping"
                style={getClickTargetStyle()}
              ></div>
              <div
                className="absolute w-2 h-2 -ml-1 -mt-1 bg-terminal-blue rounded-full"
                style={getClickTargetStyle()}
              >
                <div className="absolute left-4 top-0 bg-black/80 text-terminal-blue text-[10px] font-mono whitespace-nowrap px-1 rounded border border-terminal-blue/30">
                  TARGET ({analysis.coordinates.x}, {analysis.coordinates.y})
                </div>
              </div>
            </>
          )}

          {/* HUD Corners */}
          <div className="absolute top-4 left-4 border-l-2 border-t-2 border-white/20 w-8 h-8"></div>
          <div className="absolute top-4 right-4 border-r-2 border-t-2 border-white/20 w-8 h-8"></div>
          <div className="absolute bottom-4 left-4 border-l-2 border-b-2 border-white/20 w-8 h-8"></div>
          <div className="absolute bottom-4 right-4 border-r-2 border-b-2 border-white/20 w-8 h-8"></div>

          {/* Status badges */}
          <div className="absolute top-4 left-4 ml-4 mt-1 flex items-center gap-2">
            <div className="bg-red-600 text-white text-[10px] font-bold px-1.5 py-0.5 rounded flex items-center gap-1">
              <Camera size={10} />
              LIVE
            </div>
            {isStreaming && (
              <div className="bg-blue-600 text-white text-[10px] font-bold px-1.5 py-0.5 rounded flex items-center gap-1 animate-pulse">
                <Cast size={10} />
                STREAMING
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Annotation canvas view (toggled) */}
      {showAnnotations && (
        <div className="aspect-video">
          <AnnotationCanvas
            frameBase64={lastFrameBase64}
            analysis={analysis}
            autoAnnotate={annotationsEnabled}
            onAnnotationsChange={handleAnnotationsChange}
          />
        </div>
      )}

      {/* Toggle annotation/live */}
      {annotationsEnabled && (
        <button
          onClick={() => setShowAnnotations(!showAnnotations)}
          className={`absolute top-4 right-4 z-10 flex items-center gap-1 px-2 py-1 rounded text-xs font-mono transition-colors ${
            showAnnotations
              ? 'bg-terminal-blue text-black'
              : 'bg-black/60 text-gray-300 hover:bg-black/80'
          }`}
        >
          <Layers size={12} />
          {showAnnotations ? 'LIVE' : 'ANNOTATE'}
        </button>
      )}
    </div>
  );
};
