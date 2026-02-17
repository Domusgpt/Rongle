import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ActionLog } from '../../components/ActionLog';
import { LogLevel } from '../../types';

// Mock scrollIntoView
window.HTMLElement.prototype.scrollIntoView = vi.fn();

describe('ActionLog', () => {
  it('renders empty state message when logs are empty', () => {
    render(<ActionLog logs={[]} />);
    expect(screen.getByText('No actions recorded. System ready.')).toBeInTheDocument();
  });

  it('renders logs correctly', () => {
    const logs = [
      {
        id: '1',
        timestamp: new Date('2023-01-01T10:00:00'),
        level: LogLevel.INFO,
        message: 'Test log message',
      },
      {
        id: '2',
        timestamp: new Date('2023-01-01T10:01:00'),
        level: LogLevel.ERROR,
        message: 'Error message',
        metadata: { error: 'details' }
      }
    ];

    render(<ActionLog logs={logs} />);

    expect(screen.getByText('Test log message')).toBeInTheDocument();
    expect(screen.getByText('Error message')).toBeInTheDocument();
    expect(screen.getByText(/"error": "details"/)).toBeInTheDocument();
  });
});
