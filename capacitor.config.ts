import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.rongle.operator',
  appName: 'Rongle',
  webDir: 'dist',

  // Android-specific configuration
  android: {
    // Allow mixed content (HTTP + HTTPS) for local development
    allowMixedContent: true,
    // Enable WebView debugging in dev builds
    webContentsDebuggingEnabled: true,
    // Override user agent for compatibility
    overrideUserAgent: 'Rongle/1.0 (Android; Agentic Operator)',
  },

  server: {
    // In production, load from bundled assets (no external URL)
    androidScheme: 'https',
  },

  plugins: {
    Camera: {
      // Default to rear camera for screen capture
      defaultDirection: 'rear',
    },
    CapacitorHttp: {
      // Enable native HTTP for portal API calls (avoids CORS)
      enabled: true,
    },
  },
};

export default config;
