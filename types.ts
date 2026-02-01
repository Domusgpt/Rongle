export enum AgentStatus {
  IDLE = 'IDLE',
  PERCEIVING = 'PERCEIVING', // Capturing and Analyzing
  PLANNING = 'PLANNING',     // Deciding next step
  ACTING = 'ACTING',         // Sending HID command
  VERIFYING = 'VERIFYING',   // Checking outcome
  STOPPED = 'STOPPED',       // Emergency stop or paused
  ERROR = 'ERROR'
}

export enum LogLevel {
  INFO = 'INFO',
  SUCCESS = 'SUCCESS',
  WARNING = 'WARNING',
  ERROR = 'ERROR',
  ACTION = 'ACTION'
}

export interface LogEntry {
  id: string;
  timestamp: Date;
  level: LogLevel;
  message: string;
  metadata?: Record<string, any>;
}

export interface HardwareState {
  hdmiSignal: boolean;
  hidConnected: boolean;
  latencyMs: number;
  fps: number;
}

export interface AgentConfig {
  autoMode: boolean;
  humanInTheLoop: boolean; // Requires confirmation for actions
  confidenceThreshold: number; // 0-1
  maxRetries: number;
  pollIntervalMs: number;
}

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
  label: string;
  confidence: number;
}

export interface VisionAnalysisResult {
  description: string;
  suggestedAction: string;
  duckyScript: string;
  confidence: number;
  coordinates?: { x: number; y: number };
  detectedElements: BoundingBox[];
}