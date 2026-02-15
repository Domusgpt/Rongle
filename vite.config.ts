/// <reference types="vitest" />
import path from 'path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// SECURITY: API keys are NOT baked into the frontend bundle.
// In direct mode, the user enters their key at runtime (stored in sessionStorage).
// In portal mode, the server holds the key and proxies all VLM requests.

export default defineConfig({
  server: {
    port: 3000,
    host: '0.0.0.0',
  },
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, '.'),
    },
  },
  build: {
    // Keep the importmap for TF.js (too large to bundle, loaded from CDN)
    rollupOptions: {
      external: ['@tensorflow/tfjs'],
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './setupTests.ts',
    css: true,
    exclude: ['**/tests/e2e/**', '**/node_modules/**'], // Exclude Playwright tests from Vitest
  },
});
