import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useAgent } from './useAgent';
import { AgentStatus, LogLevel } from '../types';

// Mock dependencies
vi.mock('../services/gemini', () => ({
  analyzeScreenFrame: vi.fn().mockResolvedValue({
    confidence: 0.9,
    suggestedAction: "TEST_ACTION",
    duckyScript: "DELAY 100",
    description: "test",
    detectedElements: []
  })
}));

// Mock Bridge
const mockSendScript = vi.fn();
const mockConnect = vi.fn();
const mockDisconnect = vi.fn();

vi.mock('../services/bridge', () => ({
  AgentBridge: class {
    ws: any = { readyState: 1 }; // WebSocket.OPEN = 1
    connect = mockConnect;
    disconnect = mockDisconnect;
    sendScript = mockSendScript;
    constructor(url: string, logCb: any, connCb: any) {
       // Simulate connection immediately for tests
       setTimeout(() => connCb(true), 0);
    }
  }
}));

describe('useAgent Hook', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it('should initialize with default state', () => {
    const { result } = renderHook(() => useAgent());
    expect(result.current.status).toBe(AgentStatus.IDLE);
    expect(result.current.goal).toBe("Open the calculator app");
  });

  it('should handle start', () => {
    const { result } = renderHook(() => useAgent());

    act(() => {
      result.current.handleStart();
    });

    expect(result.current.status).toBe(AgentStatus.PERCEIVING);
  });

  it('should handle emergency stop', () => {
    const { result } = renderHook(() => useAgent());

    act(() => {
      result.current.handleStart();
      result.current.handleEmergencyStop();
    });

    expect(result.current.status).toBe(AgentStatus.STOPPED);
    expect(result.current.logs).toEqual(expect.arrayContaining([
      expect.objectContaining({
        level: LogLevel.ERROR,
        message: "EMERGENCY STOP TRIGGERED BY USER"
      })
    ]));
  });

  it('should handle frame capture and transition to PLANNING', async () => {
    const { result } = renderHook(() => useAgent());

    // Start agent
    act(() => {
      result.current.handleStart();
    });

    // Capture frame
    await act(async () => {
      await result.current.handleFrameCapture("base64data");
    });

    expect(result.current.status).toBe(AgentStatus.PLANNING);
  });
});
