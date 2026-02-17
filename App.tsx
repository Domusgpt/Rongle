import React, { useState, useEffect, useCallback, useRef } from 'react';
import { HardwareStatus } from './components/HardwareStatus';
import { LiveView } from './components/LiveView';
import { ActionLog } from './components/ActionLog';
import { AuthGate } from './components/AuthGate';
import { DeviceManager } from './components/DeviceManager';
import {
  AgentStatus,
  HardwareState,
  LogEntry,
  LogLevel,
  AgentConfig,
  VisionAnalysisResult,
  AuthState,
  PortalDevice,
  Annotation,
  HIDMode,
} from './types';
import { analyzeScreenFrame, hasGeminiApiKey, setGeminiApiKey, clearGeminiApiKey } from './services/gemini';
import { portalAPI } from './services/portal-api';
import { generateAnnotationPrompt } from './services/canvas-annotator';
import { HIDBridge } from './services/hid-bridge';
import { rongleCNN } from './services/cnn';
import type { Detection, Classification, FrameDiff, EngineStatus } from './services/cnn';
import { CNNOverlay } from './components/CNNOverlay';
import {
  Power,
  Play,
  Pause,
  ShieldAlert,
  Settings,
  Keyboard,
  Smartphone,
  Copy,
  Terminal as TerminalIcon,
  BrainCircuit,
  Cable,
  Usb,
  LogOut,
  Send,
  Cloud,
  Layers,
  Cpu,
  Eye,
  KeyRound,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Defaults
// ---------------------------------------------------------------------------
const INITIAL_HARDWARE_STATE: HardwareState = {
  cameraActive: false,
  hidConnected: false,
  hidMode: 'none' as HIDMode,
  portalConnected: false,
  latencyMs: 0,
  fps: 0,
};

const INITIAL_CONFIG: AgentConfig = {
  autoMode: false,
  humanInTheLoop: true,
  confidenceThreshold: 0.7,
  maxRetries: 3,
  pollIntervalMs: 3000,
  annotationsEnabled: true,
  useLLMProxy: true, // Mandated by security policy
};

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------
export default function App() {
  // Auth & portal state
  const [authState, setAuthState] = useState<AuthState>(portalAPI.getAuth());
  const [showAuth, setShowAuth] = useState(!portalAPI.isAuthenticated());
  const [selectedDevice, setSelectedDevice] = useState<PortalDevice | null>(null);
  const [showDevicePanel, setShowDevicePanel] = useState(false);

  // Core agent state
  const [status, setStatus] = useState<AgentStatus>(AgentStatus.IDLE);
  const [hardware, setHardware] = useState<HardwareState>(INITIAL_HARDWARE_STATE);
  const [config, setConfig] = useState<AgentConfig>(INITIAL_CONFIG);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [goal, setGoal] = useState<string>("Open the calculator app");
  const [currentAnalysis, setCurrentAnalysis] = useState<VisionAnalysisResult | null>(null);

  // Annotation state
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [compositeBase64, setCompositeBase64] = useState<string | null>(null);

  // CNN state
  const [cnnDetections, setCnnDetections] = useState<Detection[]>([]);
  const [cnnClassification, setCnnClassification] = useState<Classification | null>(null);
  const [cnnFrameDiff, setCnnFrameDiff] = useState<FrameDiff | null>(null);
  const [cnnStatus, setCnnStatus] = useState<EngineStatus>(rongleCNN.getStatus());
  const [cnnEnabled, setCnnEnabled] = useState(true);
  const [showCnnOverlay, setShowCnnOverlay] = useState(true);

  // API Key state (direct mode only)
  const [apiKeyInput, setApiKeyInput] = useState('');
  const [hasApiKey, setHasApiKey] = useState(hasGeminiApiKey());

  // HID Bridge
  const hidBridgeRef = useRef(new HIDBridge((s) => {
    setHardware(prev => ({ ...prev, hidConnected: s.connected, hidMode: s.mode }));
  }));

  // Refs for loop control
  const loopTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastActionRef = useRef<string | undefined>(undefined);
  const vlmRetryCountRef = useRef(0);
  const MAX_VLM_RETRIES = 3;

  // Set portal connected status
  useEffect(() => {
    setHardware(prev => ({
      ...prev,
      portalConnected: authState.isAuthenticated,
    }));
    if (authState.isAuthenticated) {
      setConfig(prev => ({ ...prev, useLLMProxy: true }));
    }
  }, [authState.isAuthenticated]);

  // Initialize CNN engine on mount
  useEffect(() => {
    if (!cnnEnabled) return;
    rongleCNN.init().then(ok => {
      setCnnStatus(rongleCNN.getStatus());
      if (ok) {
        console.log('[App] CNN engine initialized');
      }
    });
    return () => { rongleCNN.dispose(); };
  }, []);

  // Helper to add logs
  const addLog = useCallback((level: LogLevel, message: string, metadata?: Record<string, unknown>) => {
    setLogs(prev => [...prev, {
      id: Math.random().toString(36).substr(2, 9),
      timestamp: new Date(),
      level,
      message,
      metadata
    }]);
  }, []);

  // Emergency Stop
  const handleEmergencyStop = useCallback(() => {
    setStatus(AgentStatus.STOPPED);
    if (loopTimerRef.current) clearTimeout(loopTimerRef.current);
    hidBridgeRef.current.releaseAll();
    addLog(LogLevel.ERROR, "EMERGENCY STOP TRIGGERED BY USER");
  }, [addLog]);

  // Start Agent
  const handleStart = () => {
    if (status === AgentStatus.IDLE || status === AgentStatus.STOPPED) {
      addLog(LogLevel.INFO, "Agent Initialized", { goal, mode: config.useLLMProxy ? 'portal' : 'direct' });
      setStatus(AgentStatus.PERCEIVING);
    }
  };

  // Core Loop: Perceive -> Plan -> Act -> Verify
  const handleFrameCapture = useCallback(async (base64Image: string) => {
    if (status !== AgentStatus.PERCEIVING) return;

    try {
      addLog(LogLevel.INFO, "Analyzing visual input...");
      const t0 = Date.now();

      // Run CNN inference in parallel with VLM (fast local processing)
      if (cnnEnabled && rongleCNN.getStatus().ready) {
        rongleCNN.processFrame(base64Image, 1920, 1080).then(cnnResult => {
          setCnnDetections(cnnResult.detections);
          setCnnClassification(cnnResult.classification);
          setCnnFrameDiff(cnnResult.frameDiff);
          setCnnStatus(rongleCNN.getStatus());

          if (cnnResult.detections.length > 0) {
            addLog(LogLevel.INFO, `CNN: ${cnnResult.detections.length} UI elements detected in ${cnnResult.inferenceMs.toFixed(0)}ms`);
          }
          if (cnnResult.classification) {
            addLog(LogLevel.INFO, `CNN: Screen type → ${cnnResult.classification.class} (${(cnnResult.classification.confidence * 100).toFixed(0)}%)`);
          }
          if (cnnResult.frameDiff && cnnResult.frameDiff.changePercent < 0.01) {
            addLog(LogLevel.INFO, 'CNN: No significant frame change detected');
          }
        }).catch(() => { /* CNN errors don't block VLM */ });
      }

      // Build prompt with annotation context if available
      let annotationSuffix = '';
      if (config.annotationsEnabled && annotations.length > 0) {
        annotationSuffix = generateAnnotationPrompt(annotations);
      }

      let analysis: VisionAnalysisResult;

      // Choose the image to send: annotated composite or raw
      const imageToSend = (config.annotationsEnabled && compositeBase64) ? compositeBase64 : base64Image;

      if (config.useLLMProxy && portalAPI.isAuthenticated()) {
        // Route through portal (metered, API key stays server-side)
        const resp = await portalAPI.llmQuery(
          buildVLMPrompt(goal, lastActionRef.current, annotationSuffix),
          imageToSend,
          selectedDevice?.id,
        );
        analysis = parsePortalLLMResponse(resp.result);
        setHardware(prev => ({ ...prev, latencyMs: Math.round(resp.latency_ms) }));
        addLog(LogLevel.INFO, `Quota remaining: ${resp.remaining_quota}`, {
          tokens_in: resp.tokens_input as unknown as number,
          tokens_out: resp.tokens_output as unknown as number,
        });
      } else {
        // Direct Gemini call (local API key)
        analysis = await analyzeScreenFrame(
          imageToSend,
          goal + annotationSuffix,
          lastActionRef.current,
        );
        setHardware(prev => ({ ...prev, latencyMs: Date.now() - t0 }));
      }

      setCurrentAnalysis(analysis);
      vlmRetryCountRef.current = 0; // Reset retry counter on success

      addLog(LogLevel.INFO, "Analysis Complete", {
        confidence: analysis.confidence,
        suggestion: analysis.suggestedAction
      });

      if (analysis.confidence < config.confidenceThreshold) {
        addLog(LogLevel.WARNING, `Confidence too low (${analysis.confidence}). Pausing for safety.`);
        setStatus(AgentStatus.IDLE);
        return;
      }

      setStatus(AgentStatus.PLANNING);

      setTimeout(() => {
        if (config.humanInTheLoop) {
          if (config.autoMode) {
            proceedToAct(analysis);
          } else {
            addLog(LogLevel.WARNING, "Waiting for human confirmation...");
          }
        } else {
          proceedToAct(analysis);
        }
      }, 1000);

    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      vlmRetryCountRef.current += 1;

      // Camera permission errors — prompt user to re-grant
      if (message.includes('Permission') || message.includes('NotAllowed') || message.includes('camera')) {
        addLog(LogLevel.ERROR, "Camera access lost — please re-grant camera permission", { message });
        setHardware(prev => ({ ...prev, cameraActive: false }));
        setStatus(AgentStatus.ERROR);
        vlmRetryCountRef.current = 0;
        return;
      }

      // HID disconnect during operation
      if (message.includes('serial') || message.includes('device has been lost') || message.includes('NetworkError')) {
        addLog(LogLevel.WARNING, "HID connection lost — attempting reconnection", { message });
        setHardware(prev => ({ ...prev, hidConnected: false, hidMode: 'none' as HIDMode }));
        // Don't enter error state — agent can continue without HID
      }

      // VLM failure with exponential backoff retry
      if (vlmRetryCountRef.current <= MAX_VLM_RETRIES) {
        const backoffMs = Math.min(1000 * Math.pow(2, vlmRetryCountRef.current - 1), 8000);
        addLog(LogLevel.WARNING, `VLM query failed (attempt ${vlmRetryCountRef.current}/${MAX_VLM_RETRIES}), retrying in ${backoffMs}ms`, { message });
        setStatus(AgentStatus.IDLE);
        loopTimerRef.current = setTimeout(() => {
          setStatus(AgentStatus.PERCEIVING);
        }, backoffMs);
      } else {
        addLog(LogLevel.ERROR, `VLM query failed after ${MAX_VLM_RETRIES} retries. Stopping.`, { message });
        vlmRetryCountRef.current = 0;
        setStatus(AgentStatus.ERROR);
      }
    }
  }, [status, goal, config, addLog, annotations, compositeBase64, selectedDevice]);

  const proceedToAct = async (analysis: VisionAnalysisResult) => {
    setStatus(AgentStatus.ACTING);
    addLog(LogLevel.ACTION, `Executing Ducky Script payload...`);

    // Execute via HID bridge if connected
    if (hidBridgeRef.current.getState().connected && analysis.duckyScript) {
      try {
        await hidBridgeRef.current.executeDuckyScript(analysis.duckyScript);
        addLog(LogLevel.SUCCESS, "Payload injected via HID bridge");
      } catch (err: unknown) {
        const errMsg = err instanceof Error ? err.message : String(err);
        if (errMsg.includes('device has been lost') || errMsg.includes('serial')) {
          addLog(LogLevel.WARNING, "HID disconnected during execution — switching to clipboard mode");
          setHardware(prev => ({ ...prev, hidConnected: false, hidMode: 'none' as HIDMode }));
          // Copy to clipboard as fallback
          if (analysis.duckyScript) {
            try {
              await navigator.clipboard.writeText(analysis.duckyScript);
              addLog(LogLevel.INFO, "Payload copied to clipboard as fallback");
            } catch {}
          }
        } else {
          addLog(LogLevel.ERROR, `HID execution failed: ${errMsg}`);
        }
      }
    } else {
      addLog(LogLevel.SUCCESS, "Payload generated (no HID connected — copy to use)");
    }

    lastActionRef.current = analysis.suggestedAction;
    setStatus(AgentStatus.VERIFYING);

    // Verification delay then back to perception
    setTimeout(() => {
      setStatus(AgentStatus.PERCEIVING);
    }, 3000);
  };

  const manualConfirmAction = () => {
    if (status === AgentStatus.PLANNING && currentAnalysis) {
      addLog(LogLevel.INFO, "Action confirmed by operator.");
      proceedToAct(currentAnalysis);
    }
  };

  const copyToClipboard = () => {
    if (currentAnalysis?.duckyScript) {
      navigator.clipboard.writeText(currentAnalysis.duckyScript);
      addLog(LogLevel.INFO, "Ducky Script copied to clipboard");
    }
  };

  // HID connection handlers
  const connectHIDSerial = async () => {
    const ok = await hidBridgeRef.current.connectWebSerial();
    addLog(ok ? LogLevel.SUCCESS : LogLevel.ERROR,
      ok ? "USB Serial HID connected" : "Serial connection failed");
  };

  const connectHIDClipboard = () => {
    hidBridgeRef.current.enableClipboardMode();
    addLog(LogLevel.INFO, "HID output set to clipboard mode");
  };

  const disconnectHID = async () => {
    await hidBridgeRef.current.disconnect();
    addLog(LogLevel.INFO, "HID disconnected");
  };

  // Handle annotation changes from LiveView
  const handleAnnotatedFrame = useCallback((anns: Annotation[], composite: string) => {
    setAnnotations(anns);
    setCompositeBase64(composite);
  }, []);

  // Auth handlers
  const handleAuth = (state: AuthState) => {
    setAuthState(state);
    setShowAuth(false);
    addLog(LogLevel.SUCCESS, `Signed in as ${state.user?.email || 'user'}`);
  };

  const handleLogout = () => {
    portalAPI.logout();
    setAuthState({ isAuthenticated: false, accessToken: null, refreshToken: null, user: null });
    setConfig(prev => ({ ...prev, useLLMProxy: false }));
    addLog(LogLevel.INFO, "Signed out");
  };

  // Status Badge Helper
  const getStatusBadge = () => {
    const baseClasses = "px-3 py-1 rounded-full text-xs font-bold tracking-wider";
    switch (status) {
      case AgentStatus.IDLE: return <span className={`${baseClasses} bg-gray-700 text-gray-300`}>IDLE</span>;
      case AgentStatus.PERCEIVING: return <span className={`${baseClasses} bg-purple-900 text-purple-200 animate-pulse`}>WATCHING</span>;
      case AgentStatus.PLANNING: return <span className={`${baseClasses} bg-terminal-amber/20 text-terminal-amber animate-pulse`}>PLANNING</span>;
      case AgentStatus.ACTING: return <span className={`${baseClasses} bg-terminal-blue/20 text-terminal-blue`}>GENERATING</span>;
      case AgentStatus.VERIFYING: return <span className={`${baseClasses} bg-terminal-green/20 text-terminal-green`}>VERIFYING</span>;
      case AgentStatus.STOPPED: return <span className={`${baseClasses} bg-terminal-red text-white`}>STOPPED</span>;
      case AgentStatus.ERROR: return <span className={`${baseClasses} bg-red-900 text-red-200`}>ERROR</span>;
    }
  };

  // Show auth gate if not authenticated (Mandatory Proxy Mode)
  if (showAuth && !authState.isAuthenticated) {
    return (
      <AuthGate
        onAuth={handleAuth}
        // onSkip removed to enforce Portal Authentication
      />
    );
  }

  return (
    <div className="min-h-screen bg-industrial-900 text-gray-200 font-sans selection:bg-terminal-green selection:text-black">

      {/* Header */}
      <header className="border-b border-industrial-700 bg-industrial-800/50 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 bg-gradient-to-br from-terminal-green to-emerald-800 rounded flex items-center justify-center shadow-lg shadow-terminal-green/20">
              <span className="text-white font-bold text-lg">R</span>
            </div>
            <div>
              <h1 className="font-bold text-lg tracking-tight text-white hidden md:block">
                Rongle <span className="text-terminal-green text-xs align-top">ANDROID</span>
              </h1>
              <h1 className="font-bold text-lg tracking-tight text-white md:hidden">Rongle</h1>
              <p className="text-xs text-gray-500 font-mono">AGENTIC OPERATOR</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Auth indicator */}
            {authState.isAuthenticated ? (
              <div className="hidden sm:flex items-center gap-2">
                <Cloud size={14} className="text-terminal-green" />
                <span className="text-xs text-gray-400 font-mono">{authState.user?.email}</span>
                <button onClick={handleLogout} className="text-gray-500 hover:text-gray-300">
                  <LogOut size={14} />
                </button>
              </div>
            ) : (
              <button
                onClick={() => setShowAuth(true)}
                className="text-xs text-gray-400 hover:text-white font-mono flex items-center gap-1"
              >
                <Cloud size={14} /> Sign In
              </button>
            )}

            <div className="hidden md:flex items-center gap-2">
              <span className="text-xs text-gray-500 uppercase font-semibold">Status</span>
              {getStatusBadge()}
            </div>
            <button
              onClick={handleEmergencyStop}
              className="bg-red-500/10 hover:bg-red-500/20 text-red-500 border border-red-500/50 px-3 py-2 rounded flex items-center gap-2 transition-all font-bold text-xs sm:text-sm"
            >
              <Power size={16} />
              <span className="hidden sm:inline">ESTOP</span>
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">

        {/* Mobile Status Bar */}
        <div className="md:hidden mb-4 flex justify-between items-center bg-industrial-800 p-3 rounded-lg border border-industrial-700">
          <span className="text-xs text-gray-400 font-bold">SYSTEM STATUS</span>
          {getStatusBadge()}
        </div>

        {/* Hardware Status Row */}
        <div className="hidden md:block">
          <HardwareStatus state={hardware} />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

          {/* Left Column: Camera + Control */}
          <div className="lg:col-span-2 flex flex-col gap-6">

            {/* Live Feed */}
            <div className="bg-industrial-800 rounded-xl border border-industrial-700 p-3 sm:p-4 shadow-lg flex flex-col">
              <div className="flex justify-between items-center mb-4">
                <h2 className="font-semibold text-gray-300 flex items-center gap-2 text-sm sm:text-base">
                  <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></span>
                  Camera Input
                </h2>
                <div className="flex items-center gap-2 text-xs font-mono text-gray-500">
                  <span className="hidden sm:inline">LATENCY: {hardware.latencyMs}ms</span>
                  <span className="text-industrial-600 hidden sm:inline">|</span>
                  <span>CONF: {currentAnalysis ? Math.round(currentAnalysis.confidence * 100) : 0}%</span>
                </div>
              </div>

              <div className="relative bg-black rounded overflow-hidden">
                <LiveView
                  status={status}
                  analysis={currentAnalysis}
                  onCaptureFrame={handleFrameCapture}
                  onAnnotatedFrame={handleAnnotatedFrame}
                  isProcessing={status === AgentStatus.PERCEIVING}
                  annotationsEnabled={config.annotationsEnabled}
                  onCameraActive={(active) => setHardware(prev => ({ ...prev, cameraActive: active }))}
                />
                {showCnnOverlay && cnnEnabled && (
                  <CNNOverlay
                    detections={cnnDetections}
                    classification={cnnClassification}
                    frameDiff={cnnFrameDiff}
                    engineStatus={cnnStatus}
                    containerWidth={640}
                    containerHeight={480}
                    imageWidth={1920}
                    imageHeight={1080}
                  />
                )}
              </div>

              {/* Goal Input */}
              <div className="mt-4 flex flex-col sm:flex-row gap-2">
                <div className="flex-1 relative">
                  <input
                    type="text"
                    value={goal}
                    onChange={(e) => setGoal(e.target.value)}
                    className="w-full bg-industrial-900 border border-industrial-600 rounded px-4 py-3 text-sm focus:outline-none focus:border-terminal-blue text-white font-mono"
                    placeholder="Enter objective (e.g. Open Terminal)"
                    disabled={status !== AgentStatus.IDLE && status !== AgentStatus.STOPPED}
                  />
                  <div className="absolute right-3 top-3 text-xs text-gray-500 font-mono">GOAL</div>
                </div>
                {status === AgentStatus.IDLE || status === AgentStatus.STOPPED ? (
                  <button
                    onClick={handleStart}
                    className="bg-terminal-green hover:bg-green-400 text-black font-bold px-6 py-3 rounded flex items-center justify-center gap-2 transition-colors"
                  >
                    <Play size={18} /> START
                  </button>
                ) : (
                  <button
                    onClick={() => setStatus(AgentStatus.IDLE)}
                    className="bg-industrial-700 hover:bg-industrial-600 text-white font-bold px-6 py-3 rounded flex items-center justify-center gap-2 transition-colors"
                  >
                    <Pause size={18} /> PAUSE
                  </button>
                )}
              </div>
            </div>

            {/* HID Connection Bar */}
            <div className="bg-industrial-800 rounded-xl border border-industrial-700 p-4 flex flex-col sm:flex-row items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <Cable size={16} className={hardware.hidConnected ? 'text-terminal-green' : 'text-gray-500'} />
                <span className="text-sm text-gray-300 font-mono">
                  HID: {hardware.hidConnected
                    ? `Connected (${hardware.hidMode})`
                    : 'Not connected'}
                </span>
              </div>
              <div className="flex gap-2">
                {!hardware.hidConnected ? (
                  <>
                    <button
                      onClick={connectHIDSerial}
                      className="flex items-center gap-1 px-3 py-1.5 rounded text-xs font-bold bg-terminal-blue/20 text-terminal-blue hover:bg-terminal-blue/30 transition-colors"
                    >
                      <Usb size={12} /> USB Serial
                    </button>
                    <button
                      onClick={connectHIDClipboard}
                      className="flex items-center gap-1 px-3 py-1.5 rounded text-xs font-bold bg-industrial-700 text-gray-300 hover:bg-industrial-600 transition-colors"
                    >
                      <Copy size={12} /> Clipboard
                    </button>
                  </>
                ) : (
                  <button
                    onClick={disconnectHID}
                    className="flex items-center gap-1 px-3 py-1.5 rounded text-xs font-bold bg-industrial-700 text-gray-300 hover:bg-industrial-600 transition-colors"
                  >
                    Disconnect
                  </button>
                )}
              </div>
            </div>

            {/* Manual Confirmation Panel */}
            {status === AgentStatus.PLANNING && !config.autoMode && config.humanInTheLoop && (
              <div className="bg-terminal-amber/10 border border-terminal-amber/30 rounded-lg p-4 flex flex-col sm:flex-row items-center justify-between animate-pulse-fast gap-4">
                <div className="flex items-center gap-4">
                  <ShieldAlert className="text-terminal-amber shrink-0" size={24} />
                  <div>
                    <h3 className="font-bold text-terminal-amber text-sm">AUTHORIZATION REQUIRED</h3>
                    <p className="text-gray-400 text-xs mt-1">Proposed: <span className="font-mono text-white bg-black/50 px-1 rounded">{currentAnalysis?.suggestedAction}</span></p>
                  </div>
                </div>
                <div className="flex gap-2 w-full sm:w-auto">
                  <button
                    onClick={() => setStatus(AgentStatus.IDLE)}
                    className="flex-1 sm:flex-none px-4 py-2 rounded bg-industrial-800 hover:bg-industrial-700 text-gray-300 text-sm font-medium transition-colors"
                  >
                    Reject
                  </button>
                  <button
                    onClick={manualConfirmAction}
                    className="flex-1 sm:flex-none px-4 py-2 rounded bg-terminal-amber text-black text-sm font-bold hover:bg-amber-400 transition-colors shadow-[0_0_15px_rgba(255,176,0,0.3)]"
                  >
                    <Send size={14} className="inline mr-1" /> Inject Payload
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Right Column: Script, Reasoning, Config, Devices */}
          <div className="flex flex-col gap-6">

            {/* Ducky Script Terminal */}
            <div className="bg-industrial-800 rounded-xl border border-industrial-700 p-4 shadow-lg flex flex-col min-h-[250px]">
              <div className="flex justify-between items-center mb-3">
                <h3 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
                  <Keyboard size={16} className="text-terminal-blue" />
                  Payload Injector
                </h3>
                <button
                  onClick={copyToClipboard}
                  className="text-xs bg-industrial-700 hover:bg-industrial-600 text-gray-300 px-2 py-1 rounded flex items-center gap-1 transition-colors"
                  title="Copy Script"
                >
                  <Copy size={12} /> COPY
                </button>
              </div>

              <div className="flex-1 bg-black rounded-lg border border-industrial-600 p-3 font-mono text-sm overflow-auto relative group">
                {currentAnalysis?.duckyScript ? (
                  <div className="text-terminal-green space-y-1">
                    {currentAnalysis.duckyScript.split('\n').map((line, i) => (
                      <div key={i} className="flex">
                        <span className="text-industrial-600 select-none mr-3 w-4 text-right">{i + 1}</span>
                        <span>{line}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="absolute inset-0 flex flex-col items-center justify-center text-industrial-700">
                    <TerminalIcon size={32} className="mb-2 opacity-50" />
                    <p className="text-xs">WAITING FOR GENERATION...</p>
                  </div>
                )}
              </div>
              <div className="mt-2 text-[10px] text-gray-500 font-mono flex justify-between">
                <span>FORMAT: Ducky Script 1.0</span>
                <span>{currentAnalysis?.duckyScript?.length || 0} CHARS</span>
              </div>
            </div>

            {/* Reasoning */}
            <div className="bg-industrial-800 rounded-xl border border-industrial-700 p-4 shadow-lg">
              <h3 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2">
                <BrainCircuit size={16} className="text-terminal-blue" />
                Reasoning
              </h3>
              {currentAnalysis ? (
                <div className="space-y-3">
                  <p className="text-xs text-gray-300 leading-relaxed bg-industrial-900/50 p-2 rounded border border-industrial-700/50">
                    {currentAnalysis.description}
                  </p>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="bg-industrial-900/50 p-2 rounded border border-industrial-700/50">
                      <span className="text-[10px] text-gray-500 uppercase font-mono block mb-1">Target</span>
                      <div className="text-terminal-blue text-xs font-mono truncate">
                        {currentAnalysis.detectedElements?.[0]?.label || "N/A"}
                      </div>
                    </div>
                    <div className="bg-industrial-900/50 p-2 rounded border border-industrial-700/50">
                      <span className="text-[10px] text-gray-500 uppercase font-mono block mb-1">Confidence</span>
                      <div className="text-terminal-green text-xs font-mono">
                        {(currentAnalysis.confidence * 100).toFixed(1)}%
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center py-4 text-xs text-gray-600 font-mono">
                  NO ACTIVE ANALYSIS
                </div>
              )}
            </div>

            {/* Logs */}
            <div className="flex-1 min-h-[200px] max-h-[400px]">
              <ActionLog logs={logs} />
            </div>

            {/* CNN Status */}
            {cnnEnabled && (
              <div className="bg-industrial-800 rounded-xl border border-industrial-700 p-4">
                <h3 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2">
                  <Cpu size={16} className="text-pink-400" />
                  CNN Engine
                </h3>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="bg-industrial-900/50 p-2 rounded border border-industrial-700/50">
                    <span className="text-[10px] text-gray-500 uppercase font-mono block">Backend</span>
                    <span className={`text-xs font-mono ${cnnStatus.ready ? 'text-terminal-green' : 'text-gray-500'}`}>
                      {cnnStatus.backend.toUpperCase()}
                    </span>
                  </div>
                  <div className="bg-industrial-900/50 p-2 rounded border border-industrial-700/50">
                    <span className="text-[10px] text-gray-500 uppercase font-mono block">Inference</span>
                    <span className="text-xs font-mono text-terminal-blue">{cnnStatus.avgInferenceMs}ms</span>
                  </div>
                  <div className="bg-industrial-900/50 p-2 rounded border border-industrial-700/50">
                    <span className="text-[10px] text-gray-500 uppercase font-mono block">Detections</span>
                    <span className="text-xs font-mono text-terminal-amber">{cnnDetections.length}</span>
                  </div>
                </div>
                {cnnClassification && (
                  <div className="mt-2 text-[10px] font-mono text-gray-400 bg-industrial-900/50 p-2 rounded border border-industrial-700/50">
                    Screen: <span className="text-terminal-amber">{cnnClassification.class}</span> ({(cnnClassification.confidence * 100).toFixed(0)}%)
                    {cnnFrameDiff && (
                      <span className="ml-2 text-terminal-blue">
                        Change: {(cnnFrameDiff.changePercent * 100).toFixed(1)}%
                      </span>
                    )}
                  </div>
                )}
                {!rongleCNN.hasTrainedWeights() && cnnStatus.ready && (
                  <div className="mt-2 text-[10px] font-mono text-gray-500 bg-terminal-amber/5 p-1.5 rounded border border-terminal-amber/20">
                    <Eye size={10} className="inline mr-1 text-terminal-amber" />
                    Random weights — load trained model for accurate detection
                  </div>
                )}
              </div>
            )}

            {/* Config */}
            <div className="bg-industrial-800 rounded-xl border border-industrial-700 p-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
                  <Settings size={16} /> Config
                </h3>
              </div>
              <div className="space-y-3">
                <ToggleRow label="Human-in-the-loop" active={config.humanInTheLoop}
                  onToggle={() => setConfig(p => ({ ...p, humanInTheLoop: !p.humanInTheLoop }))}
                  color="bg-terminal-green" />
                <ToggleRow label="Auto-Retry" active={config.autoMode}
                  onToggle={() => setConfig(p => ({ ...p, autoMode: !p.autoMode }))}
                  color="bg-terminal-blue" />
                <ToggleRow label="Annotations (Set-of-Mark)" active={config.annotationsEnabled}
                  onToggle={() => setConfig(p => ({ ...p, annotationsEnabled: !p.annotationsEnabled }))}
                  color="bg-terminal-amber" />
                <ToggleRow label="CNN Vision (local)" active={cnnEnabled}
                  onToggle={() => setCnnEnabled(p => !p)}
                  color="bg-pink-500" />
                <ToggleRow label="CNN Overlay" active={showCnnOverlay}
                  onToggle={() => setShowCnnOverlay(p => !p)}
                  color="bg-indigo-500" />
                {authState.isAuthenticated && (
                  <ToggleRow label="Route through Portal" active={config.useLLMProxy}
                    onToggle={() => setConfig(p => ({ ...p, useLLMProxy: !p.useLLMProxy }))}
                    color="bg-purple-500" />
                )}

                {/* API Key input removed - Portal Proxy Mandated */}
              </div>
            </div>

            {/* Device Manager (portal mode only) */}
            {authState.isAuthenticated && (
              <DeviceManager
                onSelectDevice={setSelectedDevice}
                selectedDeviceId={selectedDevice?.id || null}
              />
            )}

          </div>
        </div>
      </main>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Small components
// ---------------------------------------------------------------------------
function ToggleRow({ label, active, onToggle, color }: {
  label: string; active: boolean; onToggle: () => void; color: string;
}) {
  return (
    <label className="flex items-center justify-between p-2 rounded bg-industrial-900/50 cursor-pointer border border-transparent hover:border-industrial-600 transition-colors">
      <span className="text-sm text-gray-400">{label}</span>
      <div
        className={`w-10 h-5 rounded-full relative transition-colors ${active ? color : 'bg-industrial-600'}`}
        onClick={onToggle}
      >
        <div className={`absolute top-1 w-3 h-3 bg-white rounded-full transition-all ${active ? 'left-6' : 'left-1'}`}></div>
      </div>
    </label>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function buildVLMPrompt(goal: string, previousAction?: string, annotationSuffix = ''): string {
  return `You are an autonomous KVM Agent running on an Android device.
Your Goal: "${goal}".
${previousAction ? `Previous Action: "${previousAction}".` : ''}

Analyze the screenshot. Identify the next UI element to interact with.
Return JSON with: description, suggestedAction, duckyScript, confidence (0-1),
coordinates ({x,y} as 0-100 normalized), detectedElements (array of {label,x,y,width,height,confidence}).${annotationSuffix}`;
}

function parsePortalLLMResponse(raw: string): VisionAnalysisResult {
  try {
    // Try parsing as JSON first
    const parsed = JSON.parse(raw);
    return {
      description: parsed.description || '',
      suggestedAction: parsed.suggestedAction || '',
      duckyScript: parsed.duckyScript || '',
      confidence: parsed.confidence || 0,
      coordinates: parsed.coordinates,
      detectedElements: parsed.detectedElements || [],
    };
  } catch {
    // Fallback: extract JSON from fenced code block
    const match = raw.match(/```(?:json)?\s*([\s\S]*?)```/);
    if (match) {
      try { return parsePortalLLMResponse(match[1]); } catch {}
    }
    return {
      description: raw.slice(0, 200),
      suggestedAction: 'WAIT',
      duckyScript: 'REM Parse error',
      confidence: 0,
      detectedElements: [],
    };
  }
}