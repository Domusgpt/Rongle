import React, { useState, useEffect } from 'react';
import type { PortalDevice, Subscription } from '../types';
import { TIER_INFO } from '../types';
import { portalAPI } from '../services/portal-api';
import {
  Smartphone, Plus, Trash2, RefreshCw, Key, ChevronDown, ChevronUp,
  Zap, CreditCard, BarChart3, Activity, Command,
} from 'lucide-react';

interface DeviceManagerProps {
  onSelectDevice: (device: PortalDevice | null) => void;
  selectedDeviceId: string | null;
}

export const DeviceManager: React.FC<DeviceManagerProps> = ({
  onSelectDevice,
  selectedDeviceId,
}) => {
  const [devices, setDevices] = useState<PortalDevice[]>([]);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [usage, setUsage] = useState<any>(null);
  const [newDeviceName, setNewDeviceName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [expandedSection, setExpandedSection] = useState<'devices' | 'subscription' | 'telemetry' | null>('devices');
  const [manualCmd, setManualCmd] = useState('');

  useEffect(() => {
    loadAll();
  }, []);

  // Poll for audit logs if a device is selected
  useEffect(() => {
      // This is a placeholder for the audit log polling loop
      // In a real implementation, we would call portalAPI.getAuditLogs(selectedDeviceId)
  }, [selectedDeviceId, expandedSection]);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [devs, sub, usg] = await Promise.all([
        portalAPI.listDevices(),
        portalAPI.getSubscription().catch(() => null),
        portalAPI.getUsage().catch(() => null),
      ]);
      setDevices(devs);
      setSubscription(sub);
      setUsage(usg);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateDevice = async () => {
    if (!newDeviceName.trim()) return;
    setError('');
    try {
      const device = await portalAPI.createDevice(newDeviceName.trim(), 'android');
      setDevices(prev => [device, ...prev]);
      setNewDeviceName('');
      onSelectDevice(device);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleDeleteDevice = async (id: string) => {
    try {
      await portalAPI.deleteDevice(id);
      setDevices(prev => prev.filter(d => d.id !== id));
      if (selectedDeviceId === id) onSelectDevice(null);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleRegenKey = async (id: string) => {
    try {
      const updated = await portalAPI.regenerateDeviceKey(id);
      setDevices(prev => prev.map(d => d.id === id ? updated : d));
    } catch (err: any) {
      setError(err.message);
    }
  };

  const tierInfo = subscription ? TIER_INFO[subscription.tier] : TIER_INFO.free;
  const quotaPercent = subscription && subscription.llm_quota_monthly > 0
    ? Math.min(100, (subscription.llm_used_this_month / subscription.llm_quota_monthly) * 100)
    : 0;

  return (
    <div className="space-y-4">
      {error && (
        <div className="bg-terminal-red/10 border border-terminal-red/30 rounded px-3 py-2 text-xs text-terminal-red font-mono">
          {error}
        </div>
      )}

      {/* Devices Section */}
      <div className="bg-industrial-800 rounded-xl border border-industrial-700 overflow-hidden">
        <button
          onClick={() => setExpandedSection(expandedSection === 'devices' ? null : 'devices')}
          className="w-full flex items-center justify-between p-4 hover:bg-industrial-700/50 transition-colors"
        >
          <h3 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
            <Smartphone size={16} className="text-terminal-blue" />
            Devices ({devices.length})
          </h3>
          {expandedSection === 'devices' ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>

        {expandedSection === 'devices' && (
          <div className="px-4 pb-4 space-y-3">
            {/* Create device */}
            <div className="flex gap-2">
              <input
                type="text"
                value={newDeviceName}
                onChange={(e) => setNewDeviceName(e.target.value)}
                className="flex-1 bg-industrial-900 border border-industrial-600 rounded px-3 py-2 text-sm focus:outline-none focus:border-terminal-blue text-white font-mono"
                placeholder="New device name..."
                onKeyDown={(e) => e.key === 'Enter' && handleCreateDevice()}
              />
              <button
                onClick={handleCreateDevice}
                className="bg-terminal-green hover:bg-green-400 text-black px-3 py-2 rounded flex items-center gap-1 text-sm font-bold transition-colors"
              >
                <Plus size={14} /> Add
              </button>
            </div>

            {/* Device list */}
            {devices.map(device => (
              <div
                key={device.id}
                className={`p-3 rounded-lg border cursor-pointer transition-all ${
                  selectedDeviceId === device.id
                    ? 'border-terminal-blue bg-terminal-blue/10'
                    : 'border-industrial-600 bg-industrial-900/50 hover:border-industrial-500'
                }`}
                onClick={() => onSelectDevice(device)}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${device.is_online ? 'bg-terminal-green' : 'bg-gray-600'}`} />
                    <span className="text-sm font-semibold text-white">{device.name}</span>
                    <span className="text-[10px] text-gray-500 bg-industrial-700 px-1.5 py-0.5 rounded font-mono">
                      {device.hardware_type}
                    </span>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={(e) => { e.stopPropagation(); handleRegenKey(device.id); }}
                      className="p-1 text-gray-500 hover:text-terminal-amber transition-colors"
                      title="Regenerate API key"
                    >
                      <Key size={12} />
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDeleteDevice(device.id); }}
                      className="p-1 text-gray-500 hover:text-terminal-red transition-colors"
                      title="Delete device"
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                </div>
                {selectedDeviceId === device.id && device.api_key && (
                  <div className="text-[10px] font-mono text-gray-500 bg-black/30 rounded px-2 py-1 truncate">
                    API Key: {device.api_key.slice(0, 20)}...
                  </div>
                )}
              </div>
            ))}

            {devices.length === 0 && (
              <p className="text-xs text-gray-500 text-center py-4 font-mono">
                No devices registered. Add one to get started.
              </p>
            )}
          </div>
        )}
      </div>

      {/* Subscription Section */}
      <div className="bg-industrial-800 rounded-xl border border-industrial-700 overflow-hidden">
        <button
          onClick={() => setExpandedSection(expandedSection === 'subscription' ? null : 'subscription')}
          className="w-full flex items-center justify-between p-4 hover:bg-industrial-700/50 transition-colors"
        >
          <h3 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
            <CreditCard size={16} className="text-terminal-amber" />
            Plan: {tierInfo.name}
          </h3>
          {expandedSection === 'subscription' ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>

        {expandedSection === 'subscription' && subscription && (
          <div className="px-4 pb-4 space-y-3">
            {/* Quota bar */}
            <div>
              <div className="flex justify-between text-xs text-gray-500 font-mono mb-1">
                <span>LLM Calls</span>
                <span>
                  {subscription.llm_used_this_month}
                  {subscription.llm_quota_monthly > 0 ? ` / ${subscription.llm_quota_monthly}` : ' / Unlimited'}
                </span>
              </div>
              <div className="h-2 bg-industrial-900 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${
                    quotaPercent > 90 ? 'bg-terminal-red' : quotaPercent > 70 ? 'bg-terminal-amber' : 'bg-terminal-green'
                  }`}
                  style={{ width: `${quotaPercent}%` }}
                />
              </div>
            </div>

            {/* Usage stats */}
            {usage && (
              <div className="grid grid-cols-2 gap-2">
                <div className="bg-industrial-900/50 rounded p-2">
                  <span className="text-[10px] text-gray-500 font-mono block">TOKENS IN</span>
                  <span className="text-sm text-white font-mono">{(usage.tokens_input_total || 0).toLocaleString()}</span>
                </div>
                <div className="bg-industrial-900/50 rounded p-2">
                  <span className="text-[10px] text-gray-500 font-mono block">TOKENS OUT</span>
                  <span className="text-sm text-white font-mono">{(usage.tokens_output_total || 0).toLocaleString()}</span>
                </div>
              </div>
            )}

            {/* Tier info */}
            <div className="bg-industrial-900/50 rounded p-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-400">Max Devices</span>
                <span className="text-xs text-white font-mono">
                  {tierInfo.devices > 0 ? tierInfo.devices : 'Unlimited'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-400">Monthly Quota</span>
                <span className="text-xs text-white font-mono">
                  {tierInfo.quota > 0 ? tierInfo.quota.toLocaleString() + ' calls' : 'Unlimited'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-400">Price</span>
                <span className="text-xs text-terminal-green font-mono">{tierInfo.price}</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Telemetry & Control Section */}
      {selectedDeviceId && (
      <div className="bg-industrial-800 rounded-xl border border-industrial-700 overflow-hidden">
        <button
          onClick={() => setExpandedSection(expandedSection === 'telemetry' ? null : 'telemetry')}
          className="w-full flex items-center justify-between p-4 hover:bg-industrial-700/50 transition-colors"
        >
          <h3 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
            <Activity size={16} className="text-terminal-green" />
            Telemetry & Control
          </h3>
          {expandedSection === 'telemetry' ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>

        {expandedSection === 'telemetry' && (
          <div className="px-4 pb-4 space-y-3">
             <div className="flex gap-2">
               <input
                 type="text"
                 value={manualCmd}
                 onChange={e => setManualCmd(e.target.value)}
                 className="flex-1 bg-black border border-industrial-600 rounded px-2 py-1 text-xs font-mono text-terminal-green"
                 placeholder="Ducky Script (e.g. STRING Hello)"
               />
               <button className="bg-industrial-700 text-white px-2 py-1 rounded text-xs">
                 <Command size={12} className="inline mr-1" /> Send
               </button>
             </div>

             <div className="h-32 bg-black rounded border border-industrial-600 p-2 overflow-auto font-mono text-[10px] text-gray-400">
               <div className="text-gray-500 italic">Waiting for audit logs...</div>
             </div>
          </div>
        )}
      </div>
      )}
    </div>
  );
};
