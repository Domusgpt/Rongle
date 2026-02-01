import React from 'react';
import { HardwareState } from '../types';
import { Monitor, Cpu, Cable, Activity } from 'lucide-react';

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

export const HardwareStatus: React.FC<HardwareStatusProps> = ({ state }) => {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <StatusItem 
        label="HDMI Input" 
        value={state.hdmiSignal ? "LOCKED 1080P" : "NO SIGNAL"} 
        active={state.hdmiSignal}
        Icon={Monitor}
      />
      <StatusItem 
        label="USB HID" 
        value={state.hidConnected ? "CONNECTED" : "DISCONNECTED"} 
        active={state.hidConnected}
        Icon={Cable}
      />
      <StatusItem 
        label="Inference Latency" 
        value={`${state.latencyMs}ms`} 
        active={state.latencyMs < 500}
        Icon={Cpu}
      />
      <StatusItem 
        label="Capture FPS" 
        value={state.fps} 
        active={state.fps > 24}
        Icon={Activity}
      />
    </div>
  );
};