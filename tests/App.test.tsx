import { render, screen } from '@testing-library/react';
import App from '../App';
import { describe, it, expect, vi } from 'vitest';

// Mock dependencies
vi.mock('@capacitor/camera', () => ({
  Camera: {
    getPhoto: vi.fn(),
  },
}));

vi.mock('@capacitor/filesystem', () => ({
  Filesystem: {
    writeFile: vi.fn(),
  },
}));

// Mock services/cnn which might use TF.js
vi.mock('../services/cnn', () => ({
  rongleCNN: {
    init: vi.fn().mockResolvedValue(true),
    processFrame: vi.fn().mockResolvedValue({ detections: [] }),
    getStatus: vi.fn().mockReturnValue({ isReady: true }),
    dispose: vi.fn(),
  },
}));

describe('App', () => {
  it('renders without crashing', () => {
    // Basic smoke test
    render(<App />);
    expect(document.body).toBeTruthy();
  });
});
