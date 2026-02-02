import { GoogleGenAI, Type } from "@google/genai";
import { VisionAnalysisResult } from "../types";

// ---------------------------------------------------------------------------
// Runtime API key management (NEVER baked into the bundle)
// ---------------------------------------------------------------------------
const STORAGE_KEY = 'rongle_gemini_key';

let _cachedClient: InstanceType<typeof GoogleGenAI> | null = null;

/** Store the API key in sessionStorage (cleared on tab close). */
export function setGeminiApiKey(key: string): void {
  sessionStorage.setItem(STORAGE_KEY, key);
  _cachedClient = null; // Force re-creation
}

/** Get the current API key (from sessionStorage). */
export function getGeminiApiKey(): string | null {
  return sessionStorage.getItem(STORAGE_KEY);
}

/** Check if a Gemini API key is configured. */
export function hasGeminiApiKey(): boolean {
  return !!sessionStorage.getItem(STORAGE_KEY);
}

/** Clear the stored API key. */
export function clearGeminiApiKey(): void {
  sessionStorage.removeItem(STORAGE_KEY);
  _cachedClient = null;
}

function getClient(): GoogleGenAI {
  if (_cachedClient) return _cachedClient;
  const key = getGeminiApiKey();
  if (!key) throw new Error('No Gemini API key configured. Enter your key in Settings or use Portal mode.');
  _cachedClient = new GoogleGenAI({ apiKey: key });
  return _cachedClient;
}

export const analyzeScreenFrame = async (
  base64Image: string,
  goal: string,
  previousAction?: string
): Promise<VisionAnalysisResult> => {
  try {
    const prompt = `
      You are an autonomous KVM (Keyboard/Video/Mouse) Agent running on a mobile device.
      Your Goal: "${goal}".
      ${previousAction ? `Previous Action taken: "${previousAction}".` : ''}
      
      Analyze the provided screen screenshot (captured via phone camera aiming at a monitor).
      
      1. Describe the current state of the screen relevant to the goal.
      2. Identify the specific UI element that needs to be interacted with to advance the goal.
      3. Suggest the next specific action in natural language (e.g., "Open Terminal").
      4. TRANSLATE the action into valid DUCKY SCRIPT commands.
         - Use commands like: DELAY, STRING, ENTER, GUI, TAB.
         - Example: "GUI r", "DELAY 200", "STRING cmd", "ENTER".
      5. Provide normalized coordinates (0-100 scale) for where a mouse click should happen if applicable.
      6. Estimate your confidence in this action.

      Return the response in JSON format.
    `;

    const response = await getClient().models.generateContent({
      model: 'gemini-3-flash-preview',
      contents: {
        parts: [
          {
            inlineData: {
              mimeType: 'image/jpeg',
              data: base64Image
            }
          },
          {
            text: prompt
          }
        ]
      },
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            description: { type: Type.STRING, description: "Brief visual description of the screen state." },
            suggestedAction: { type: Type.STRING, description: "The immediate next action in plain English." },
            duckyScript: { type: Type.STRING, description: "The action translated to Ducky Script syntax (multi-line string)." },
            confidence: { type: Type.NUMBER, description: "Confidence score between 0.0 and 1.0." },
            coordinates: {
              type: Type.OBJECT,
              description: "Target coordinates for mouse action (0-100 range).",
              properties: {
                x: { type: Type.NUMBER },
                y: { type: Type.NUMBER }
              }
            },
            detectedElements: {
              type: Type.ARRAY,
              items: {
                type: Type.OBJECT,
                properties: {
                  label: { type: Type.STRING },
                  x: { type: Type.NUMBER },
                  y: { type: Type.NUMBER },
                  width: { type: Type.NUMBER },
                  height: { type: Type.NUMBER },
                  confidence: { type: Type.NUMBER }
                }
              }
            }
          }
        }
      }
    });

    if (response.text) {
      return JSON.parse(response.text) as VisionAnalysisResult;
    }
    
    throw new Error("Empty response from Gemini");

  } catch (error) {
    console.error("Gemini Analysis Failed:", error);
    // Return a safe fallback
    return {
      description: "Analysis failed due to error.",
      suggestedAction: "WAIT",
      duckyScript: "REM Analysis Failed",
      confidence: 0,
      detectedElements: []
    };
  }
};