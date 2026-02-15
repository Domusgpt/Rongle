import { describe, it, expect, vi } from 'vitest';
import { analyzeScreenFrame } from './gemini';

// Mock the GoogleGenAI client
const { mockGenerateContent } = vi.hoisted(() => {
  return { mockGenerateContent: vi.fn() };
});

vi.mock('@google/genai', () => {
  return {
    GoogleGenAI: class {
      public apiKey: any;
      public models: any;
      constructor(params: any) {
        this.apiKey = params.apiKey;
        this.models = {
          generateContent: mockGenerateContent
        };
      }
    },
    Type: {
      OBJECT: 'OBJECT',
      STRING: 'STRING',
      NUMBER: 'NUMBER',
      ARRAY: 'ARRAY'
    }
  };
});

describe('analyzeScreenFrame', () => {
  const mockBase64Image = 'base64encodedimage';
  const mockGoal = 'Test Goal';

  it('should return analysis result when API call is successful', async () => {
    const mockResponse = {
      text: JSON.stringify({
        description: 'A test screen',
        suggestedAction: 'Click button',
        duckyScript: 'DELAY 100',
        confidence: 0.9,
        detectedElements: []
      })
    };

    mockGenerateContent.mockResolvedValue(mockResponse);

    const result = await analyzeScreenFrame(mockBase64Image, mockGoal);

    expect(result).toEqual({
      description: 'A test screen',
      suggestedAction: 'Click button',
      duckyScript: 'DELAY 100',
      confidence: 0.9,
      detectedElements: []
    });
  });

  it('should return fallback when API call fails', async () => {
    mockGenerateContent.mockRejectedValue(new Error('API Error'));

    const result = await analyzeScreenFrame(mockBase64Image, mockGoal);

    // Matches the actual implementation in services/gemini.ts error handling
    // which usually returns a safe fallback object
    expect(result.suggestedAction).toBe("WAIT");
    expect(result.duckyScript).toContain("REM");
  });
});
