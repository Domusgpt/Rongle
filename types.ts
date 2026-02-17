// ---------------------------------------------------------------------------
// Agent States
// ---------------------------------------------------------------------------
export enum AgentStatus {
  IDLE = 'IDLE',
  PERCEIVING = 'PERCEIVING',
  PLANNING = 'PLANNING',
  ACTING = 'ACTING',
  VERIFYING = 'VERIFYING',
  STOPPED = 'STOPPED',
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

// ---------------------------------------------------------------------------
// Hardware & Connection State (Android-first)
// ---------------------------------------------------------------------------
export interface HardwareState {
  cameraActive: boolean;
  hidConnected: boolean;
  hidMode: HIDMode;
  portalConnected: boolean;
  latencyMs: number;
  fps: number;
}

export type HIDMode = 'web_serial' | 'bluetooth' | 'websocket' | 'clipboard' | 'none';

// ---------------------------------------------------------------------------
// Agent Config
// ---------------------------------------------------------------------------
export interface AgentConfig {
  autoMode: boolean;
  humanInTheLoop: boolean;
  confidenceThreshold: number;
  maxRetries: number;
  pollIntervalMs: number;
  annotationsEnabled: boolean;
  useLLMProxy: boolean;
}

// ---------------------------------------------------------------------------
// Vision Analysis
// ---------------------------------------------------------------------------
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

// ---------------------------------------------------------------------------
// Canvas Annotation (Set-of-Mark prompting)
// ---------------------------------------------------------------------------
export type AnnotationType = 'box' | 'mark' | 'arrow' | 'zone' | 'label';

export interface Annotation {
  id: string;
  type: AnnotationType;
  x: number;
  y: number;
  width?: number;
  height?: number;
  label: string;
  color: string;
  markIndex?: number;
}

export interface AnnotatedFrame {
  originalBase64: string;
  compositeBase64: string;
  annotations: Annotation[];
  promptSuffix: string;
  timestamp: number;
}

// ---------------------------------------------------------------------------
// Auth & Portal
// ---------------------------------------------------------------------------
export interface AuthState {
  isAuthenticated: boolean;
  accessToken: string | null;
  refreshToken: string | null;
  user: PortalUser | null;
}

export interface PortalUser {
  id: string;
  email: string;
  display_name: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
}

export interface PortalDevice {
  id: string;
  name: string;
  hardware_type: string;
  api_key?: string;
  is_online: boolean;
  last_seen: string | null;
  created_at: string;
  settings_json?: string;
  policy_json?: string;
}

// ---------------------------------------------------------------------------
// Subscription & Billing
// ---------------------------------------------------------------------------
export type SubscriptionTier = 'free' | 'starter' | 'pro' | 'enterprise';

export interface Subscription {
  tier: SubscriptionTier;
  llm_quota_monthly: number;
  llm_used_this_month: number;
  max_devices: number;
  billing_cycle_start: string;
  expires_at: string | null;
}

export interface UsageStats {
  tier: string;
  billing_cycle_start: string;
  llm_calls_used: number;
  llm_calls_quota: number;
  tokens_input_total: number;
  tokens_output_total: number;
}

export interface AuditLogEntry {
  sequence: number;
  timestamp: number;
  timestamp_iso: string;
  action: string;
  action_detail: string;
  screenshot_hash: string;
  entry_hash: string;
  policy_verdict: string;
}

export const TIER_INFO: Record<SubscriptionTier, {
  name: string;
  quota: number;
  devices: number;
  price: string;
}> = {
  free:       { name: 'Free',       quota: 100,    devices: 1,  price: '$0' },
  starter:    { name: 'Starter',    quota: 2000,   devices: 3,  price: '$19/mo' },
  pro:        { name: 'Pro',        quota: 20000,  devices: 10, price: '$79/mo' },
  enterprise: { name: 'Enterprise', quota: -1,     devices: -1, price: 'Contact us' },
};

// ---------------------------------------------------------------------------
// HID Bridge
// ---------------------------------------------------------------------------
export interface HIDConnectionState {
  connected: boolean;
  mode: HIDMode;
  deviceName: string;
  error: string | null;
}

// ---------------------------------------------------------------------------
// LLM Proxy Response
// ---------------------------------------------------------------------------
export interface LLMProxyResponse {
  result: string;
  tokens_input: number;
  tokens_output: number;
  latency_ms: number;
  remaining_quota: number;
}