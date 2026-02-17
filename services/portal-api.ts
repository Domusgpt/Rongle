/**
 * PortalAPI — Browser-side client for the Rongle Portal backend.
 *
 * Handles auth (JWT), device management, LLM proxy, subscription,
 * and audit log retrieval.  All state is persisted in localStorage
 * so the session survives page reloads.
 */

import type {
  AuthState,
  LLMProxyResponse,
  PortalDevice,
  PortalUser,
  Subscription,
  UsageStats,
  AuditLogEntry,
} from '../types';

// ---------------------------------------------------------------------------
// Defaults
// ---------------------------------------------------------------------------
const STORAGE_KEY = 'rongle_auth';
const DEFAULT_PORTAL_URL = import.meta.env.VITE_PORTAL_URL || 'http://localhost:8000';

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------
function loadAuth(): AuthState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  return { isAuthenticated: false, accessToken: null, refreshToken: null, user: null };
}

function saveAuth(state: AuthState) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function clearAuth() {
  localStorage.removeItem(STORAGE_KEY);
}

// ---------------------------------------------------------------------------
// Portal API Client
// ---------------------------------------------------------------------------
export class PortalAPI {
  private baseUrl: string;
  private auth: AuthState;

  constructor(baseUrl?: string) {
    this.baseUrl = (baseUrl || DEFAULT_PORTAL_URL).replace(/\/$/, '');
    this.auth = loadAuth();
  }

  // -- State accessors --
  getAuth(): AuthState { return this.auth; }
  isAuthenticated(): boolean { return this.auth.isAuthenticated && !!this.auth.accessToken; }
  getUser(): PortalUser | null { return this.auth.user; }

  // -- Core HTTP --
  private async request<T>(
    method: string,
    path: string,
    body?: any,
    skipAuth = false,
  ): Promise<T> {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (!skipAuth && this.auth.accessToken) {
      headers['Authorization'] = `Bearer ${this.auth.accessToken}`;
    }

    const resp = await fetch(`${this.baseUrl}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });

    // Auto-refresh on 401
    if (resp.status === 401 && !skipAuth && this.auth.refreshToken) {
      const refreshed = await this.refreshToken();
      if (refreshed) {
        headers['Authorization'] = `Bearer ${this.auth.accessToken}`;
        const retry = await fetch(`${this.baseUrl}${path}`, {
          method, headers,
          body: body ? JSON.stringify(body) : undefined,
        });
        if (!retry.ok) throw new Error(await retry.text());
        return retry.json();
      }
    }

    if (!resp.ok) {
      const text = await resp.text();
      let detail = text;
      try { detail = JSON.parse(text).detail || text; } catch {}
      throw new Error(detail);
    }

    if (resp.status === 204) return undefined as T;
    return resp.json();
  }

  // -----------------------------------------------------------------------
  // Auth
  // -----------------------------------------------------------------------
  async register(email: string, password: string, displayName?: string): Promise<AuthState> {
    const data = await this.request<{
      access_token: string;
      refresh_token: string;
      expires_in: number;
    }>('POST', '/api/auth/register', { email, password, display_name: displayName || '' }, true);

    this.auth = {
      isAuthenticated: true,
      accessToken: data.access_token,
      refreshToken: data.refresh_token,
      user: null,
    };
    saveAuth(this.auth);

    // Fetch user profile
    await this.fetchMe();
    return this.auth;
  }

  async login(email: string, password: string): Promise<AuthState> {
    const data = await this.request<{
      access_token: string;
      refresh_token: string;
      expires_in: number;
    }>('POST', '/api/auth/login', { email, password }, true);

    this.auth = {
      isAuthenticated: true,
      accessToken: data.access_token,
      refreshToken: data.refresh_token,
      user: null,
    };
    saveAuth(this.auth);

    await this.fetchMe();
    return this.auth;
  }

  async refreshToken(): Promise<boolean> {
    try {
      const data = await this.request<{
        access_token: string;
        refresh_token: string;
      }>('POST', '/api/auth/refresh', { refresh_token: this.auth.refreshToken }, true);

      this.auth.accessToken = data.access_token;
      this.auth.refreshToken = data.refresh_token;
      saveAuth(this.auth);
      return true;
    } catch {
      this.logout();
      return false;
    }
  }

  logout(): void {
    this.auth = { isAuthenticated: false, accessToken: null, refreshToken: null, user: null };
    clearAuth();
  }

  // -----------------------------------------------------------------------
  // User
  // -----------------------------------------------------------------------
  async fetchMe(): Promise<PortalUser> {
    const user = await this.request<PortalUser>('GET', '/api/users/me');
    this.auth.user = user;
    saveAuth(this.auth);
    return user;
  }

  async updateProfile(updates: { display_name?: string; password?: string }): Promise<PortalUser> {
    const user = await this.request<PortalUser>('PATCH', '/api/users/me', updates);
    this.auth.user = user;
    saveAuth(this.auth);
    return user;
  }

  // -----------------------------------------------------------------------
  // Devices
  // -----------------------------------------------------------------------
  async listDevices(): Promise<PortalDevice[]> {
    return this.request<PortalDevice[]>('GET', '/api/devices/');
  }

  async createDevice(name: string, hardwareType = 'android'): Promise<PortalDevice> {
    return this.request<PortalDevice>('POST', '/api/devices/', { name, hardware_type: hardwareType });
  }

  async getDevice(deviceId: string): Promise<PortalDevice> {
    return this.request<PortalDevice>('GET', `/api/devices/${deviceId}`);
  }

  async deleteDevice(deviceId: string): Promise<void> {
    await this.request<void>('DELETE', `/api/devices/${deviceId}`);
  }

  async updateDeviceSettings(deviceId: string, settings: Record<string, any>): Promise<PortalDevice> {
    return this.request<PortalDevice>('PATCH', `/api/devices/${deviceId}/settings`, settings);
  }

  async regenerateDeviceKey(deviceId: string): Promise<PortalDevice> {
    return this.request<PortalDevice>('POST', `/api/devices/${deviceId}/regenerate-key`);
  }

  // -----------------------------------------------------------------------
  // Policy
  // -----------------------------------------------------------------------
  async getDevicePolicy(deviceId: string): Promise<{ device_id: string; policy: Record<string, any> }> {
    return this.request('GET', `/api/devices/${deviceId}/policy`);
  }

  async setDevicePolicy(deviceId: string, policy: Record<string, any>): Promise<any> {
    return this.request('PUT', `/api/devices/${deviceId}/policy`, policy);
  }

  // -----------------------------------------------------------------------
  // LLM Proxy (metered)
  // -----------------------------------------------------------------------
  async llmQuery(
    prompt: string,
    imageBase64?: string,
    deviceId?: string,
    model?: string,
  ): Promise<LLMProxyResponse> {
    return this.request<LLMProxyResponse>('POST', '/api/llm/query', {
      prompt,
      image_base64: imageBase64 || null,
      device_id: deviceId || null,
      model: model || null,
    });
  }

  // -----------------------------------------------------------------------
  // Subscription
  // -----------------------------------------------------------------------
  async getSubscription(): Promise<Subscription> {
    return this.request<Subscription>('GET', '/api/subscription/');
  }

  async updateSubscription(tier: string): Promise<Subscription> {
    return this.request<Subscription>('PUT', '/api/subscription/', { tier });
  }

  async getUsage(): Promise<UsageStats> {
    return this.request<UsageStats>('GET', '/api/subscription/usage');
  }

  // -----------------------------------------------------------------------
  // Audit
  // -----------------------------------------------------------------------
  async getAuditLog(deviceId: string, offset = 0, limit = 100): Promise<AuditLogEntry[]> {
    return this.request<AuditLogEntry[]>('GET', `/api/devices/${deviceId}/audit?offset=${offset}&limit=${limit}`);
  }

  async verifyAuditChain(deviceId: string): Promise<{ status: string; entries_verified?: number }> {
    return this.request('GET', `/api/devices/${deviceId}/audit/verify`);
  }

  // -----------------------------------------------------------------------
  // Health
  // -----------------------------------------------------------------------
  async health(): Promise<{ status: string }> {
    return this.request('GET', '/health', undefined, true);
  }
}

// Singleton instance
export const portalAPI = new PortalAPI();
