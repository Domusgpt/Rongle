import { useState, useEffect, useCallback, useRef } from 'react';
import {
  AgentStatus,
  HardwareState,
  LogEntry,
  LogLevel,
  AgentConfig,
  VisionAnalysisResult
} from '../types';
import { analyzeScreenFrame } from '../services/gemini';
import { AgentBridge } from '../services/bridge';

const INITIAL_HARDWARE_STATE: HardwareState = {
  hdmiSignal: true,
  hidConnected: true,
  latencyMs: 120,
  fps: 30
};

const INITIAL_CONFIG: AgentConfig = {
  autoMode: false,
  humanInTheLoop: true,
  confidenceThreshold: 0.7,
  maxRetries: 3,
  pollIntervalMs: 3000
};

export const useAgent = () => {
  const [status, setStatus] = useState<AgentStatus>(AgentStatus.IDLE);
  const [hardware, setHardware] = useState<HardwareState>(INITIAL_HARDWARE_STATE);
  const [config, setConfig] = useState<AgentConfig>(INITIAL_CONFIG);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [goal, setGoal] = useState<string>("Open the calculator app");
  const [bridgeUrl, setBridgeUrl] = useState<string>("ws://localhost:8000");
  const [authToken, setAuthToken] = useState<string>("default-insecure-token");
  const [currentAnalysis, setCurrentAnalysis] = useState<VisionAnalysisResult | null>(null);
  const [bridgeConnected, setBridgeConnected] = useState<boolean>(false);

  const loopTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastActionRef = useRef<string | undefined>(undefined);
  const bridgeRef = useRef<AgentBridge | null>(null);

  const addLog = useCallback((level: LogLevel, message: string, metadata?: any) => {
    setLogs(prev => [...prev, {
      id: Math.random().toString(36).substr(2, 9),
      timestamp: new Date(),
      level,
      message,
      metadata
    }]);
  }, []);

  useEffect(() => {
    bridgeRef.current = new AgentBridge(
      bridgeUrl,
      authToken,
      addLog,
      setBridgeConnected
    );
    bridgeRef.current.connect();

    return () => {
      bridgeRef.current?.disconnect();
    };
  }, [addLog, bridgeUrl, authToken]);

  const handleEmergencyStop = useCallback(() => {
    setStatus(AgentStatus.STOPPED);
    if (loopTimerRef.current) clearTimeout(loopTimerRef.current);
    addLog(LogLevel.ERROR, "EMERGENCY STOP TRIGGERED BY USER");
  }, [addLog]);

  const handleStart = () => {
    if (status === AgentStatus.IDLE || status === AgentStatus.STOPPED) {
      addLog(LogLevel.INFO, "Agent Initialized", { goal });
      setStatus(AgentStatus.PERCEIVING);
    }
  };

  const proceedToAct = useCallback((analysis: VisionAnalysisResult) => {
    setStatus(AgentStatus.ACTING);
    addLog(LogLevel.ACTION, `Transmitting Payload...`);

    if (bridgeRef.current && (bridgeConnected || bridgeRef.current['ws']?.readyState === WebSocket.OPEN)) {
        bridgeRef.current.sendScript(analysis.duckyScript);
        lastActionRef.current = analysis.suggestedAction;

        setTimeout(() => {
          setStatus(AgentStatus.VERIFYING);
          setTimeout(() => {
            setStatus(AgentStatus.PERCEIVING);
          }, 3000);
        }, 1000);
    } else {
        addLog(LogLevel.ERROR, "Cannot Execute: Bridge Disconnected");
        setStatus(AgentStatus.ERROR);
    }
  }, [addLog, bridgeConnected]);

  const handleFrameCapture = useCallback(async (base64Image: string) => {
    if (status !== AgentStatus.PERCEIVING) return;

    try {
      addLog(LogLevel.INFO, "Analyzing visual input...");

      const analysis = await analyzeScreenFrame(base64Image, goal, lastActionRef.current);
      setCurrentAnalysis(analysis);

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

    } catch (error) {
      addLog(LogLevel.ERROR, "Perception Failure", error);
      setStatus(AgentStatus.ERROR);
    }
  }, [status, goal, config, addLog, proceedToAct]);

  const manualConfirmAction = () => {
    if (status === AgentStatus.PLANNING && currentAnalysis) {
      addLog(LogLevel.INFO, "Action confirmed by operator.");
      proceedToAct(currentAnalysis);
    }
  };

  return {
    status, setStatus,
    hardware, setHardware,
    config, setConfig,
    logs, addLog,
    goal, setGoal,
    bridgeUrl, setBridgeUrl,
    authToken, setAuthToken,
    currentAnalysis,
    bridgeConnected,
    handleStart,
    handleEmergencyStop,
    handleFrameCapture,
    manualConfirmAction
  };
};
