import React from 'react';
import { HardwareState } from '../types';
import { Camera, Cpu, Cable, Activity, Cloud, CloudOff } from 'lucide-react';

interface HardwareStatusProps {
  state: HardwareState;
}

const StatusItem: React.FC<{ label: string; value: string | number; active: boolean; Icon: React.ElementType }> = ({ label, value, active, Icon }) => (
  <div className={`flex items-center space-x-3 p-3 rounded-lg border ${active ? 'border-terminal-green/30 bg-terminal-green/5' : 'border-industrial-700 bg-industrial-800'}`}>
    <div className={`p-2 rounded-md ${active ? 'bg-terminal-green/20 text-terminal-green' : 'bg-industrial-700 text-gray-400'}`}>
      <Icon size={18} />
    </div>
    <div>
      <div className="text-xs text-gray-500 uppercase tracking-wider font-semibold">{label}</div>
      <div className={`font-mono text-sm ${active ? 'text-gray-200' : 'text-gray-500'}`}>
        {value}
      </div>
    </div>
  </div>
);

const HID_MODE_LABELS: Record<string, string> = {
  web_serial: 'USB SERIAL',
  bluetooth: 'BLUETOOTH',
  websocket: 'WS BRIDGE',
  clipboard: 'CLIPBOARD',
  none: 'DISCONNECTED',
};

export const HardwareStatus: React.FC<HardwareStatusProps> = ({ state }) => {
  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
      <StatusItem
        label="Camera"
        value={state.cameraActive ? "ACTIVE" : "NO FEED"}
        active={state.cameraActive}
        Icon={Camera}
      />
      <StatusItem
        label="HID Output"
        value={HID_MODE_LABELS[state.hidMode] || 'NONE'}
        active={state.hidConnected}
        Icon={Cable}
      />
      <StatusItem
        label="Portal"
        value={state.portalConnected ? "CONNECTED" : "OFFLINE"}
        active={state.portalConnected}
        Icon={state.portalConnected ? Cloud : CloudOff}
      />
      <StatusItem
        label="Inference"
        value={`${state.latencyMs}ms`}
        active={state.latencyMs > 0 && state.latencyMs < 500}
        Icon={Cpu}
      />
      <StatusItem
        label="Capture FPS"
        value={state.fps}
        active={state.fps > 0}
        Icon={Activity}
      />
    </div>
  );
};