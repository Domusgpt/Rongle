import React, { useState } from 'react';
import type { AuthState } from '../types';
import { portalAPI } from '../services/portal-api';
import { LogIn, UserPlus, Wifi, WifiOff, Eye, EyeOff } from 'lucide-react';

interface AuthGateProps {
  onAuth: (state: AuthState) => void;
  onSkip?: () => void;
}

export const AuthGate: React.FC<AuthGateProps> = ({ onAuth, onSkip }) => {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [portalUrl, setPortalUrl] = useState(
    import.meta.env.VITE_PORTAL_URL || 'http://localhost:8000'
  );
  const [showPortalConfig, setShowPortalConfig] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      let state: AuthState;
      if (mode === 'register') {
        state = await portalAPI.register(email, password, displayName);
      } else {
        state = await portalAPI.login(email, password);
      }
      onAuth(state);
    } catch (err: any) {
      setError(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-industrial-900 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 mx-auto bg-gradient-to-br from-terminal-green to-emerald-800 rounded-xl flex items-center justify-center shadow-lg shadow-terminal-green/20 mb-4">
            <span className="text-2xl font-bold text-white">R</span>
          </div>
          <h1 className="text-2xl font-bold text-white">Rongle</h1>
          <p className="text-sm text-gray-500 font-mono mt-1">HARDWARE AGENTIC OPERATOR</p>
        </div>

        {/* Auth Form */}
        <div className="bg-industrial-800 rounded-xl border border-industrial-700 p-6 shadow-lg">
          {/* Tab toggle */}
          <div className="flex mb-6 bg-industrial-900 rounded-lg p-1">
            <button
              onClick={() => setMode('login')}
              className={`flex-1 py-2 text-sm font-semibold rounded-md transition-colors ${
                mode === 'login' ? 'bg-industrial-700 text-white' : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              <LogIn size={14} className="inline mr-1" /> Sign In
            </button>
            <button
              onClick={() => setMode('register')}
              className={`flex-1 py-2 text-sm font-semibold rounded-md transition-colors ${
                mode === 'register' ? 'bg-industrial-700 text-white' : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              <UserPlus size={14} className="inline mr-1" /> Register
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'register' && (
              <div>
                <label className="block text-xs text-gray-500 font-mono mb-1 uppercase">Display Name</label>
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  className="w-full bg-industrial-900 border border-industrial-600 rounded px-3 py-2.5 text-sm focus:outline-none focus:border-terminal-blue text-white font-mono"
                  placeholder="Your name"
                />
              </div>
            )}

            <div>
              <label className="block text-xs text-gray-500 font-mono mb-1 uppercase">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-industrial-900 border border-industrial-600 rounded px-3 py-2.5 text-sm focus:outline-none focus:border-terminal-blue text-white font-mono"
                placeholder="you@example.com"
                required
              />
            </div>

            <div>
              <label className="block text-xs text-gray-500 font-mono mb-1 uppercase">Password</label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-industrial-900 border border-industrial-600 rounded px-3 py-2.5 text-sm focus:outline-none focus:border-terminal-blue text-white font-mono pr-10"
                  placeholder="Min 8 characters"
                  minLength={8}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-2.5 text-gray-500 hover:text-gray-300"
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {error && (
              <div className="bg-terminal-red/10 border border-terminal-red/30 rounded px-3 py-2 text-xs text-terminal-red font-mono">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-terminal-green hover:bg-green-400 text-black font-bold py-3 rounded flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
            >
              {loading ? (
                <span className="animate-spin">...</span>
              ) : mode === 'login' ? (
                <>
                  <LogIn size={16} /> Sign In
                </>
              ) : (
                <>
                  <UserPlus size={16} /> Create Account
                </>
              )}
            </button>
          </form>

          {/* Portal URL config */}
          <div className="mt-4 pt-4 border-t border-industrial-700">
            <button
              onClick={() => setShowPortalConfig(!showPortalConfig)}
              className="text-xs text-gray-500 hover:text-gray-300 font-mono flex items-center gap-1"
            >
              <Wifi size={12} /> Portal: {portalUrl}
            </button>
            {showPortalConfig && (
              <input
                type="url"
                value={portalUrl}
                onChange={(e) => setPortalUrl(e.target.value)}
                className="mt-2 w-full bg-industrial-900 border border-industrial-600 rounded px-3 py-2 text-xs text-gray-300 font-mono focus:outline-none focus:border-terminal-blue"
                placeholder="https://portal.rongle.io"
              />
            )}
          </div>
        </div>

        {/* Skip / offline mode */}
        {onSkip && (
          <>
            <button
              onClick={onSkip}
              className="w-full mt-4 py-3 text-sm text-gray-500 hover:text-gray-300 font-mono flex items-center justify-center gap-2 transition-colors"
            >
              <WifiOff size={14} /> Continue in Direct Mode (no portal)
            </button>
            <p className="text-center text-xs text-gray-600 mt-2">
              Direct mode uses your Gemini API key locally. No account, billing, or device sync.
            </p>
          </>
        )}
      </div>
    </div>
  );
};
