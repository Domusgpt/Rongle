import React from 'react';
import { HardwareStatus } from './components/HardwareStatus';
import { LiveView } from './components/LiveView';
import { ActionLog } from './components/ActionLog';
import { AgentStatus, LogLevel } from './types';
import { useAgent } from './hooks/useAgent';
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
  Wifi,
  WifiOff
} from 'lucide-react';

export default function App() {
  const {
    status, setStatus,
    hardware,
    config, setConfig,
    logs, addLog,
    goal, setGoal,
    currentAnalysis,
    bridgeConnected,
    handleStart,
    handleEmergencyStop,
    handleFrameCapture,
    manualConfirmAction
  } = useAgent();

  const copyToClipboard = () => {
    if (currentAnalysis?.duckyScript) {
      navigator.clipboard.writeText(currentAnalysis.duckyScript);
      addLog(LogLevel.INFO, "Ducky Script copied to clipboard");
    }
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

  return (
    <div className="min-h-screen bg-industrial-900 text-gray-200 font-sans selection:bg-terminal-green selection:text-black">
      
      {/* Header */}
      <header className="border-b border-industrial-700 bg-industrial-800/50 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 bg-gradient-to-br from-terminal-green to-emerald-800 rounded flex items-center justify-center shadow-lg shadow-terminal-green/20">
              <Smartphone className="text-white" size={24} />
            </div>
            <div>
              <h1 className="font-bold text-lg tracking-tight text-white hidden md:block">Sentient KVM <span className="text-terminal-green text-xs align-top">MOBILE</span></h1>
              <h1 className="font-bold text-lg tracking-tight text-white md:hidden">Mobile KVM</h1>
              <p className="text-xs text-gray-500 font-mono">OPTICAL DUCKY INJECTOR</p>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            <div className={`flex items-center gap-1.5 px-2 py-1 rounded border ${bridgeConnected ? 'bg-terminal-green/10 border-terminal-green/30 text-terminal-green' : 'bg-red-900/20 border-red-900/50 text-red-500'}`}>
               {bridgeConnected ? <Wifi size={14} /> : <WifiOff size={14} />}
               <span className="text-[10px] font-bold tracking-wider hidden sm:inline">{bridgeConnected ? 'CONNECTED' : 'OFFLINE'}</span>
            </div>
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
        
        {/* Mobile Status Bar (Visible only on small screens) */}
        <div className="md:hidden mb-4 flex justify-between items-center bg-industrial-800 p-3 rounded-lg border border-industrial-700">
          <span className="text-xs text-gray-400 font-bold">SYSTEM STATUS</span>
          {getStatusBadge()}
        </div>

        {/* Top Hardware Status Row */}
        <div className="hidden md:block">
          <HardwareStatus state={hardware} />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          
          {/* Left Column: Visuals & Control */}
          <div className="lg:col-span-2 flex flex-col gap-6">
            
            {/* Live Feed Container */}
            <div className="bg-industrial-800 rounded-xl border border-industrial-700 p-3 sm:p-4 shadow-lg flex flex-col">
              <div className="flex justify-between items-center mb-4">
                <h2 className="font-semibold text-gray-300 flex items-center gap-2 text-sm sm:text-base">
                  <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></span>
                  Camera Input (Target Screen)
                </h2>
                <div className="flex items-center gap-2 text-xs font-mono text-gray-500">
                  <span className="hidden sm:inline">LATENCY: {hardware.latencyMs}ms</span>
                  <span className="text-industrial-600 hidden sm:inline">|</span>
                  <span>CONF: {currentAnalysis ? Math.round(currentAnalysis.confidence * 100) : 0}%</span>
                </div>
              </div>
              
              <div className="relative bg-black rounded overflow-hidden flex items-center justify-center">
                 <LiveView 
                    status={status} 
                    analysis={currentAnalysis} 
                    onCaptureFrame={handleFrameCapture} 
                    isProcessing={status === AgentStatus.PERCEIVING}
                 />
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

            {/* Manual Confirmation Panel (Conditional) */}
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
                      Inject Payload
                    </button>
                  </div>
               </div>
            )}
          </div>

          {/* Right Column: Ducky Script & Logs */}
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
                          <span className="text-industrial-600 select-none mr-3 w-4 text-right">{i+1}</span>
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

            {/* Analysis Summary */}
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

            {/* Logs (Collapsible on mobile via scroll) */}
            <div className="flex-1 min-h-[200px] max-h-[400px]">
              <ActionLog logs={logs} />
            </div>

            {/* Quick Config */}
            <div className="bg-industrial-800 rounded-xl border border-industrial-700 p-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
                  <Settings size={16} /> Config
                </h3>
              </div>
              <div className="space-y-3">
                 <label className="flex items-center justify-between p-2 rounded bg-industrial-900/50 cursor-pointer border border-transparent hover:border-industrial-600 transition-colors">
                    <span className="text-sm text-gray-400">Human-in-the-loop</span>
                    <div 
                      className={`w-10 h-5 rounded-full relative transition-colors ${config.humanInTheLoop ? 'bg-terminal-green' : 'bg-industrial-600'}`}
                      onClick={() => setConfig(p => ({...p, humanInTheLoop: !p.humanInTheLoop}))}
                    >
                       <div className={`absolute top-1 w-3 h-3 bg-white rounded-full transition-all ${config.humanInTheLoop ? 'left-6' : 'left-1'}`}></div>
                    </div>
                 </label>
                 <label className="flex items-center justify-between p-2 rounded bg-industrial-900/50 cursor-pointer border border-transparent hover:border-industrial-600 transition-colors">
                    <span className="text-sm text-gray-400">Auto-Retry</span>
                    <div 
                      className={`w-10 h-5 rounded-full relative transition-colors ${config.autoMode ? 'bg-terminal-blue' : 'bg-industrial-600'}`}
                      onClick={() => setConfig(p => ({...p, autoMode: !p.autoMode}))}
                    >
                       <div className={`absolute top-1 w-3 h-3 bg-white rounded-full transition-all ${config.autoMode ? 'left-6' : 'left-1'}`}></div>
                    </div>
                 </label>
              </div>
            </div>

          </div>
        </div>
      </main>
    </div>
  );
}