// ---------------------------------------------------------------------------
// TaskPlanner — VLM-driven goal decomposition with checkpoints and replanning.
//
// The planner takes a high-level goal, captures the current screen context,
// and asks the VLM to decompose it into concrete steps. Each step includes
// verification criteria so the agent can confirm success before moving on.
//
// Key features:
//   - Checkpoint system: resumes from last successful step on failure
//   - Automatic replanning: when a step fails repeatedly, asks VLM to
//     re-plan from the current screen state
//   - CNN + OCR context: enriches the VLM prompt with detected elements
//     and visible text for more accurate planning
//   - Step dependencies: supports simple dependency chains
// ---------------------------------------------------------------------------

import type {
  TaskPlan,
  TaskStep,
  ScreenContext,
  PlannerConfig,
  PlannerEvent,
} from './types';
import { DEFAULT_PLANNER_CONFIG } from './types';

// ---------------------------------------------------------------------------
// Prompt Templates
// ---------------------------------------------------------------------------

const PLAN_PROMPT = `You are an autonomous computer operator planning a multi-step task.

GOAL: "{goal}"

CURRENT SCREEN: The attached screenshot shows the current state.
{cnnContext}
{ocrContext}

Break this goal into concrete, sequential steps. Each step should be a single
UI interaction (click, type, keyboard shortcut, etc.).

Return a JSON array of steps. Each step must have:
- "description": What this step does (human-readable)
- "action": Ducky Script command(s) to execute
- "verificationCriteria": What should be visible/true after this step succeeds
- "targetRegion": Approximate screen region {{x, y, width, height}} in 0-100 normalized coords (optional)
- "notes": Any caveats or conditions (optional)

Rules:
- Be specific. "Click the Start menu" not "Navigate to the application".
- Include DELAY commands where the UI needs time to respond.
- Each step should be independently verifiable by looking at the screen.
- Maximum {maxSteps} steps. If the goal needs more, focus on the most critical path.
- Account for common failure modes (dialog popups, loading screens).

Return ONLY the JSON array, no markdown fences or commentary.`;

const REPLAN_PROMPT = `You are an autonomous computer operator. Your original plan failed at step {failedStep}.

ORIGINAL GOAL: "{goal}"
COMPLETED STEPS: {completedSteps}
FAILED STEP: "{failedDescription}"
FAILURE REASON: {failureReason}

CURRENT SCREEN: The attached screenshot shows what the screen looks like now.
{cnnContext}
{ocrContext}

Create a NEW plan to complete the remaining goal from the current screen state.
Do NOT repeat already-completed steps. Start from where we are now.

Return a JSON array of steps (same format as before).
Return ONLY the JSON array, no markdown fences or commentary.`;

const VERIFY_PROMPT = `You are verifying whether a computer interaction step succeeded.

STEP DESCRIPTION: "{description}"
VERIFICATION CRITERIA: "{criteria}"
ACTION TAKEN: "{action}"

Look at the attached screenshot. Did the step succeed?

Return JSON: {{"success": true/false, "confidence": 0.0-1.0, "observation": "what you see"}}
Return ONLY the JSON, no markdown fences or commentary.`;

// ---------------------------------------------------------------------------
// Plan generation
// ---------------------------------------------------------------------------

/**
 * Generate a task plan by asking the VLM to decompose a goal.
 *
 * @param goal           The user's high-level goal
 * @param context        Current screen state
 * @param config         Planner configuration
 * @param vlmQuery       Function that sends a prompt + image to VLM and returns text
 * @returns A TaskPlan with steps, or throws on failure
 */
export async function generatePlan(
  goal: string,
  context: ScreenContext,
  config: PlannerConfig,
  vlmQuery: (prompt: string, imageBase64: string) => Promise<string>,
): Promise<TaskPlan> {
  const cnnContext = context.detectedElements?.length
    ? `\nDETECTED UI ELEMENTS:\n${context.detectedElements
        .map(e => `- ${e.class}: "${e.label}" at (${e.bbox.x},${e.bbox.y},${e.bbox.width},${e.bbox.height}) conf=${e.confidence.toFixed(2)}`)
        .join('\n')}`
    : '';

  const ocrContext = context.visibleText
    ? `\nVISIBLE TEXT ON SCREEN:\n${context.visibleText.slice(0, 2000)}`
    : '';

  const prompt = PLAN_PROMPT
    .replace('{goal}', goal)
    .replace('{cnnContext}', cnnContext)
    .replace('{ocrContext}', ocrContext)
    .replace('{maxSteps}', String(config.maxSteps));

  const rawResponse = await vlmQuery(prompt, context.imageBase64);
  const steps = parseStepsResponse(rawResponse, config);

  const planId = `plan_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`;

  return {
    id: planId,
    goal,
    steps,
    currentStepIndex: 0,
    status: 'executing',
    checkpointIndex: -1,
    replanCount: 0,
    maxReplans: config.maxReplans,
    createdAt: Date.now(),
    updatedAt: Date.now(),
    initialScreenDescription: context.previousAction,
    initialScreenType: context.screenType,
  };
}

/**
 * Generate a new plan from a failed plan's checkpoint.
 */
export async function replan(
  originalPlan: TaskPlan,
  failedStep: TaskStep,
  failureReason: string,
  context: ScreenContext,
  config: PlannerConfig,
  vlmQuery: (prompt: string, imageBase64: string) => Promise<string>,
): Promise<TaskPlan> {
  const completedSteps = originalPlan.steps
    .filter(s => s.status === 'completed')
    .map((s, i) => `${i + 1}. ${s.description}`)
    .join('\n');

  const cnnContext = context.detectedElements?.length
    ? `\nDETECTED UI ELEMENTS:\n${context.detectedElements
        .map(e => `- ${e.class}: "${e.label}" at (${e.bbox.x},${e.bbox.y})`)
        .join('\n')}`
    : '';

  const ocrContext = context.visibleText
    ? `\nVISIBLE TEXT ON SCREEN:\n${context.visibleText.slice(0, 2000)}`
    : '';

  const prompt = REPLAN_PROMPT
    .replace('{goal}', originalPlan.goal)
    .replace('{failedStep}', String(failedStep.index + 1))
    .replace('{failedDescription}', failedStep.description)
    .replace('{failureReason}', failureReason)
    .replace('{completedSteps}', completedSteps || '(none)')
    .replace('{cnnContext}', cnnContext)
    .replace('{ocrContext}', ocrContext);

  const rawResponse = await vlmQuery(prompt, context.imageBase64);
  const steps = parseStepsResponse(rawResponse, config);

  return {
    ...originalPlan,
    steps,
    currentStepIndex: 0,
    status: 'executing',
    replanCount: originalPlan.replanCount + 1,
    updatedAt: Date.now(),
  };
}

/**
 * Verify whether a step succeeded by asking the VLM to check the screen.
 */
export async function verifyStep(
  step: TaskStep,
  context: ScreenContext,
  vlmQuery: (prompt: string, imageBase64: string) => Promise<string>,
): Promise<{ success: boolean; confidence: number; observation: string }> {
  const prompt = VERIFY_PROMPT
    .replace('{description}', step.description)
    .replace('{criteria}', step.verificationCriteria)
    .replace('{action}', step.action);

  const rawResponse = await vlmQuery(prompt, context.imageBase64);

  try {
    const parsed = JSON.parse(extractJSON(rawResponse));
    return {
      success: !!parsed.success,
      confidence: typeof parsed.confidence === 'number' ? parsed.confidence : 0,
      observation: parsed.observation || '',
    };
  } catch {
    // If parsing fails, assume failure
    return {
      success: false,
      confidence: 0,
      observation: `Failed to parse verification response: ${rawResponse.slice(0, 200)}`,
    };
  }
}

// ---------------------------------------------------------------------------
// Step Execution Engine
// ---------------------------------------------------------------------------

/**
 * Execute a single step and return updated step.
 *
 * @param plan           Current plan
 * @param stepIndex      Index of the step to execute
 * @param executeAction  Function that executes Ducky Script and returns success
 * @returns Updated step
 */
export function prepareStepForExecution(
  plan: TaskPlan,
  stepIndex: number,
): TaskStep {
  const step = { ...plan.steps[stepIndex] };
  step.status = 'in_progress';
  step.attempts += 1;
  step.updatedAt = Date.now();
  return step;
}

/**
 * Mark a step as completed and advance the plan.
 */
export function completeStep(plan: TaskPlan, stepIndex: number): TaskPlan {
  const updatedSteps = [...plan.steps];
  updatedSteps[stepIndex] = {
    ...updatedSteps[stepIndex],
    status: 'completed',
    updatedAt: Date.now(),
  };

  const nextIndex = stepIndex + 1;
  const allDone = nextIndex >= updatedSteps.length;

  return {
    ...plan,
    steps: updatedSteps,
    currentStepIndex: allDone ? stepIndex : nextIndex,
    checkpointIndex: stepIndex,
    status: allDone ? 'completed' : 'executing',
    updatedAt: Date.now(),
  };
}

/**
 * Mark a step as failed.
 */
export function failStep(plan: TaskPlan, stepIndex: number, error: string): TaskPlan {
  const updatedSteps = [...plan.steps];
  const step = updatedSteps[stepIndex];

  updatedSteps[stepIndex] = {
    ...step,
    status: step.attempts >= step.maxRetries ? 'failed' : 'pending',
    error,
    updatedAt: Date.now(),
  };

  const exhausted = step.attempts >= step.maxRetries;

  return {
    ...plan,
    steps: updatedSteps,
    status: exhausted
      ? (plan.replanCount < plan.maxReplans ? 'replanning' : 'failed')
      : 'executing',
    updatedAt: Date.now(),
  };
}

/**
 * Get the next executable step (respects dependencies).
 */
export function getNextStep(plan: TaskPlan): TaskStep | null {
  for (let i = plan.currentStepIndex; i < plan.steps.length; i++) {
    const step = plan.steps[i];
    if (step.status === 'completed' || step.status === 'skipped') continue;
    if (step.status === 'failed') return null; // blocked

    // Check dependencies
    const depsReady = step.dependsOn.every(depId =>
      plan.steps.find(s => s.id === depId)?.status === 'completed'
    );

    if (depsReady) return step;
  }
  return null;
}

/**
 * Get a summary of plan progress.
 */
export function getPlanProgress(plan: TaskPlan): {
  total: number;
  completed: number;
  failed: number;
  pending: number;
  percent: number;
} {
  const total = plan.steps.length;
  const completed = plan.steps.filter(s => s.status === 'completed').length;
  const failed = plan.steps.filter(s => s.status === 'failed').length;
  const pending = total - completed - failed;
  const percent = total > 0 ? Math.round((completed / total) * 100) : 0;
  return { total, completed, failed, pending, percent };
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function parseStepsResponse(raw: string, config: PlannerConfig): TaskStep[] {
  const json = extractJSON(raw);
  let parsed: any[];

  try {
    parsed = JSON.parse(json);
  } catch {
    throw new Error(`Failed to parse plan steps: ${raw.slice(0, 300)}`);
  }

  if (!Array.isArray(parsed)) {
    throw new Error('Plan response is not an array');
  }

  return parsed.slice(0, config.maxSteps).map((item: any, i: number) => ({
    id: `step_${i}`,
    index: i,
    description: item.description || `Step ${i + 1}`,
    action: item.action || '',
    verificationCriteria: item.verificationCriteria || item.verification || '',
    status: 'pending' as const,
    attempts: 0,
    maxRetries: config.maxRetriesPerStep,
    dependsOn: item.dependsOn || [],
    targetRegion: item.targetRegion || undefined,
    notes: item.notes || undefined,
    updatedAt: Date.now(),
  }));
}

function extractJSON(text: string): string {
  // Try the raw text first
  const trimmed = text.trim();
  if (trimmed.startsWith('[') || trimmed.startsWith('{')) {
    return trimmed;
  }

  // Try extracting from markdown code fences
  const fenceMatch = trimmed.match(/```(?:json)?\s*([\s\S]*?)```/);
  if (fenceMatch) return fenceMatch[1].trim();

  // Try finding the first [ or { and matching to the last ] or }
  const arrayStart = trimmed.indexOf('[');
  const objStart = trimmed.indexOf('{');

  if (arrayStart >= 0) {
    const lastBracket = trimmed.lastIndexOf(']');
    if (lastBracket > arrayStart) {
      return trimmed.slice(arrayStart, lastBracket + 1);
    }
  }

  if (objStart >= 0) {
    const lastBrace = trimmed.lastIndexOf('}');
    if (lastBrace > objStart) {
      return trimmed.slice(objStart, lastBrace + 1);
    }
  }

  return trimmed;
}
