import React, { useEffect, useRef, useState } from 'react';
import { VisionAnalysisResult, AgentStatus } from '../types';
import { Scan, AlertCircle, Camera } from 'lucide-react';

interface LiveViewProps {
  status: AgentStatus;
  analysis: VisionAnalysisResult | null;
  onCaptureFrame: (dataUrl: string) => void;
  isProcessing: boolean;
}

export const LiveView: React.FC<LiveViewProps> = ({ status, analysis, onCaptureFrame, isProcessing }) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [streamError, setStreamError] = useState<string | null>(null);

  // Initialize Camera (Mobile Back Camera)
  useEffect(() => {
    const startVideo = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ 
          video: { 
            facingMode: 'environment', // Request back camera for phone use
            width: { ideal: 1920 },
            height: { ideal: 1080 }
          } 
        });
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
        setStreamError(null);
      } catch (err) {
        console.error("Camera access denied:", err);
        setStreamError("CAMERA ACCESS DENIED");
      }
    };
    startVideo();
  }, []);

  // Handle periodic capturing or manual capturing
  useEffect(() => {
    if (!isProcessing && status === AgentStatus.PERCEIVING) {
        // Wait a brief moment for video to stabilize if needed, then capture
        const timer = setTimeout(() => {
            if (videoRef.current && canvasRef.current) {
                const video = videoRef.current;
                const canvas = canvasRef.current;
                const context = canvas.getContext('2d');
                
                if (context && video.videoWidth > 0) {
                  canvas.width = video.videoWidth;
                  canvas.height = video.videoHeight;
                  context.drawImage(video, 0, 0, canvas.width, canvas.height);
                  
                  // Convert to base64 jpeg
                  const dataUrl = canvas.toDataURL('image/jpeg', 0.8);
                  // Strip header for API
                  const base64 = dataUrl.split(',')[1];
                  onCaptureFrame(base64);
                }
            }
        }, 500); // 500ms delay to simulate "looking"
        return () => clearTimeout(timer);
    }
  }, [status, isProcessing, onCaptureFrame]);

  // Calculate overlay style for target click
  const getClickTargetStyle = () => {
    if (!analysis?.coordinates) return {};
    return {
      left: `${analysis.coordinates.x}%`,
      top: `${analysis.coordinates.y}%`,
    };
  };

  return (
    <div className="relative w-full aspect-video bg-black rounded-lg border border-industrial-600 overflow-hidden group shadow-2xl">
      {/* Video Feed */}
      <video 
        ref={videoRef} 
        autoPlay 
        playsInline 
        muted 
        className="w-full h-full object-cover opacity-80"
      />

      {/* Hidden Canvas for Capture */}
      <canvas ref={canvasRef} className="hidden" />

      {/* Error State */}
      {streamError && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-industrial-900/90 text-terminal-red">
          <AlertCircle size={48} className="mb-4" />
          <p className="font-mono font-bold text-lg">{streamError}</p>
          <p className="text-sm text-gray-500 mt-2 text-center px-4">Ensure camera permissions are enabled and you are using a mobile device.</p>
        </div>
      )}

      {/* Overlays */}
      <div className="absolute inset-0 pointer-events-none">
        
        {/* Scanline Effect */}
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-terminal-green/5 to-transparent h-[10%] w-full animate-scanline opacity-20"></div>

        {/* AI Thinking/Processing Overlay */}
        {isProcessing && (
           <div className="absolute inset-0 border-2 border-terminal-amber/50 animate-pulse bg-terminal-amber/5 flex items-center justify-center">
             <div className="bg-black/70 px-4 py-2 rounded text-terminal-amber font-mono text-sm flex items-center gap-2">
               <Scan className="animate-spin" size={16} />
               ANALYZING SCENE...
             </div>
           </div>
        )}

        {/* Target Indicator */}
        {analysis?.coordinates && !isProcessing && (
           <div 
             className="absolute w-6 h-6 -ml-3 -mt-3 border-2 border-terminal-blue rounded-full animate-ping"
             style={getClickTargetStyle()}
           ></div>
        )}
        {analysis?.coordinates && !isProcessing && (
           <div 
             className="absolute w-2 h-2 -ml-1 -mt-1 bg-terminal-blue rounded-full"
             style={getClickTargetStyle()}
           >
             <div className="absolute left-4 top-0 bg-black/80 text-terminal-blue text-[10px] font-mono whitespace-nowrap px-1 rounded border border-terminal-blue/30">
                TARGET ({analysis.coordinates.x}, {analysis.coordinates.y})
             </div>
           </div>
        )}

        {/* HUD Corners */}
        <div className="absolute top-4 left-4 border-l-2 border-t-2 border-white/20 w-8 h-8"></div>
        <div className="absolute top-4 right-4 border-r-2 border-t-2 border-white/20 w-8 h-8"></div>
        <div className="absolute bottom-4 left-4 border-l-2 border-b-2 border-white/20 w-8 h-8"></div>
        <div className="absolute bottom-4 right-4 border-r-2 border-b-2 border-white/20 w-8 h-8"></div>

        {/* Status Label */}
        <div className="absolute top-4 left-4 ml-4 mt-1 flex items-center gap-2">
             <div className="bg-red-600 text-white text-[10px] font-bold px-1.5 py-0.5 rounded flex items-center gap-1">
               <Camera size={10} />
               LIVE
             </div>
        </div>
      </div>
    </div>
  );
};