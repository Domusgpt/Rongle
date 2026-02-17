import React, { useEffect, useRef } from 'react';
import { LogEntry, LogLevel } from '../types';
import { Terminal, CheckCircle, AlertTriangle, Info, PlayCircle } from 'lucide-react';

interface ActionLogProps {
  logs: LogEntry[];
}

export const ActionLog: React.FC<ActionLogProps> = ({ logs }) => {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const getIcon = (level: LogLevel) => {
    switch (level) {
      case LogLevel.SUCCESS: return <CheckCircle size={14} className="text-terminal-green" />;
      case LogLevel.WARNING: return <AlertTriangle size={14} className="text-terminal-amber" />;
      case LogLevel.ERROR: return <AlertTriangle size={14} className="text-terminal-red" />;
      case LogLevel.ACTION: return <PlayCircle size={14} className="text-terminal-blue" />;
      default: return <Info size={14} className="text-gray-500" />;
    }
  };

  const getColor = (level: LogLevel) => {
    switch (level) {
      case LogLevel.SUCCESS: return 'text-terminal-green';
      case LogLevel.WARNING: return 'text-terminal-amber';
      case LogLevel.ERROR: return 'text-terminal-red';
      case LogLevel.ACTION: return 'text-terminal-blue';
      default: return 'text-gray-400';
    }
  };

  return (
    <div className="flex flex-col h-full bg-industrial-800 rounded-lg border border-industrial-700 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-industrial-700 bg-industrial-900/50">
        <div className="flex items-center gap-2">
          <Terminal size={16} className="text-gray-400" />
          <h3 className="text-sm font-semibold text-gray-200">System Log & Audit Trail</h3>
        </div>
        <span className="text-xs text-gray-500 font-mono">/var/log/agent.log</span>
      </div>
      
      <div className="flex-1 overflow-y-auto p-4 space-y-3 font-mono text-sm">
        {logs.length === 0 && (
          <div className="text-gray-600 italic text-center py-8">No actions recorded. System ready.</div>
        )}
        {logs.map((log) => (
          <div key={log.id} className="flex gap-3 group">
            <span className="text-gray-600 text-xs mt-0.5 min-w-[60px]">
              {log.timestamp.toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </span>
            <div className="mt-0.5">{getIcon(log.level)}</div>
            <div className={`break-words flex-1 ${getColor(log.level)}`}>
              {log.message}
              {log.metadata && (
                <pre className="mt-1 text-xs text-gray-500 bg-black/20 p-2 rounded overflow-x-auto">
                  {JSON.stringify(log.metadata, null, 2)}
                </pre>
              )}
            </div>
          </div>
        ))}
        <div ref={endRef} />
      </div>
    </div>
  );
};