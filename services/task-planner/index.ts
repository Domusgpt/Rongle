// ---------------------------------------------------------------------------
// RongleTaskPlanner — Public API for multi-step goal decomposition.
//
// Usage:
//   import { ronglePlanner } from './services/task-planner';
//   const plan = await ronglePlanner.createPlan('Open calculator', screenContext);
//   while (ronglePlanner.hasNextStep()) {
//     const step = ronglePlanner.getNextStep();
//     // execute step...
//     await ronglePlanner.completeCurrentStep(screenContext);
//   }
// ---------------------------------------------------------------------------

import type {
  TaskPlan,
  TaskStep,
  ScreenContext,
  PlannerConfig,
  PlannerEvent,
} from './types';
import { DEFAULT_PLANNER_CONFIG } from './types';
import {
  generatePlan,
  replan,
  verifyStep,
  prepareStepForExecution,
  completeStep,
  failStep,
  getNextStep,
  getPlanProgress,
} from './planner';

// Re-export types
export type {
  TaskPlan,
  TaskStep,
  ScreenContext,
  PlannerConfig,
  PlannerEvent,
  StepStatus,
} from './types';
export { DEFAULT_PLANNER_CONFIG } from './types';
export { getPlanProgress } from './planner';

/** Callback for VLM queries. */
export type VLMQueryFn = (prompt: string, imageBase64: string) => Promise<string>;

/** Callback for executing Ducky Script. Returns true if executed OK. */
export type ExecuteActionFn = (duckyScript: string) => Promise<boolean>;

/**
 * RongleTaskPlanner — orchestrates multi-step goal execution.
 *
 * This class owns the plan lifecycle:
 *   1. Create plan (VLM decomposes goal)
 *   2. Execute steps one at a time
 *   3. Verify each step (VLM checks screenshot)
 *   4. Replan on failure (VLM generates new steps from checkpoint)
 *   5. Complete or fail the plan
 */
class RongleTaskPlanner {
  private config: PlannerConfig;
  private currentPlan: TaskPlan | null = null;
  private listeners: Array<(event: PlannerEvent) => void> = [];
  private vlmQuery: VLMQueryFn | null = null;

  constructor(config?: Partial<PlannerConfig>) {
    this.config = { ...DEFAULT_PLANNER_CONFIG, ...config };
  }

  /**
   * Register the VLM query function.
   * Must be called before creating plans.
   */
  setVLMQuery(fn: VLMQueryFn): void {
    this.vlmQuery = fn;
  }

  /**
   * Subscribe to planner events for UI updates.
   */
  onEvent(listener: (event: PlannerEvent) => void): () => void {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }

  private emit(event: PlannerEvent): void {
    for (const l of this.listeners) {
      try { l(event); } catch {}
    }
  }

  /**
   * Create a new task plan from a goal.
   *
   * Uses the VLM to analyze the current screen and decompose
   * the goal into concrete, sequential steps.
   */
  async createPlan(goal: string, context: ScreenContext): Promise<TaskPlan> {
    if (!this.vlmQuery) {
      throw new Error('VLM query function not set — call setVLMQuery() first');
    }

    const plan = await generatePlan(goal, context, this.config, this.vlmQuery);
    this.currentPlan = plan;
    this.emit({ type: 'plan_created', plan });
    return plan;
  }

  /**
   * Get the current plan (if any).
   */
  getPlan(): TaskPlan | null {
    return this.currentPlan;
  }

  /**
   * Check if there's a next step to execute.
   */
  hasNextStep(): boolean {
    if (!this.currentPlan) return false;
    if (this.currentPlan.status !== 'executing') return false;
    return getNextStep(this.currentPlan) !== null;
  }

  /**
   * Get the next step to execute (without advancing).
   */
  getNextStep(): TaskStep | null {
    if (!this.currentPlan) return null;
    return getNextStep(this.currentPlan);
  }

  /**
   * Begin executing the next step. Marks it as in_progress.
   * Returns the step's Ducky Script action to execute.
   */
  startNextStep(): TaskStep | null {
    if (!this.currentPlan) return null;
    const step = getNextStep(this.currentPlan);
    if (!step) return null;

    const prepared = prepareStepForExecution(this.currentPlan, step.index);
    this.currentPlan.steps[step.index] = prepared;
    this.currentPlan.updatedAt = Date.now();

    this.emit({ type: 'step_started', stepIndex: step.index, step: prepared });
    return prepared;
  }

  /**
   * Mark the current step as completed and advance.
   *
   * Optionally verifies the step by asking the VLM to check the
   * current screen against the verification criteria.
   */
  async completeCurrentStep(
    context?: ScreenContext,
    skipVerification = false,
  ): Promise<{
    success: boolean;
    plan: TaskPlan;
    observation?: string;
  }> {
    if (!this.currentPlan) {
      throw new Error('No active plan');
    }

    const step = this.currentPlan.steps.find(s => s.status === 'in_progress');
    if (!step) {
      throw new Error('No step in progress');
    }

    // Optional VLM verification
    if (!skipVerification && context && this.vlmQuery && step.verificationCriteria) {
      const verification = await verifyStep(step, context, this.vlmQuery);

      if (!verification.success && verification.confidence > this.config.minStepConfidence) {
        // Step verification failed — handle as failure
        return this.handleStepFailure(
          step.index,
          `Verification failed: ${verification.observation}`,
          context,
        );
      }
    }

    // Mark completed
    this.currentPlan = completeStep(this.currentPlan, step.index);
    this.emit({
      type: 'step_completed',
      stepIndex: step.index,
      step: this.currentPlan.steps[step.index],
    });
    this.emit({ type: 'checkpoint_saved', stepIndex: step.index });

    // Check if plan is fully complete
    if (this.currentPlan.status === 'completed') {
      this.emit({ type: 'plan_completed', plan: this.currentPlan });
    }

    return {
      success: true,
      plan: this.currentPlan,
    };
  }

  /**
   * Mark the current step as failed.
   *
   * If retries are available, the step goes back to pending.
   * If retries are exhausted and replans are available, triggers replanning.
   * Otherwise, the plan fails.
   */
  async failCurrentStep(
    error: string,
    context?: ScreenContext,
  ): Promise<{
    success: boolean;
    plan: TaskPlan;
    observation?: string;
  }> {
    if (!this.currentPlan) {
      throw new Error('No active plan');
    }

    const step = this.currentPlan.steps.find(s => s.status === 'in_progress');
    if (!step) {
      throw new Error('No step in progress');
    }

    return this.handleStepFailure(step.index, error, context);
  }

  /**
   * Pause the current plan.
   */
  pause(): void {
    if (this.currentPlan && this.currentPlan.status === 'executing') {
      this.currentPlan.status = 'paused';
      this.currentPlan.updatedAt = Date.now();
    }
  }

  /**
   * Resume a paused plan.
   */
  resume(): void {
    if (this.currentPlan && this.currentPlan.status === 'paused') {
      this.currentPlan.status = 'executing';
      this.currentPlan.updatedAt = Date.now();
    }
  }

  /**
   * Cancel the current plan.
   */
  cancel(): void {
    if (this.currentPlan) {
      this.currentPlan.status = 'failed';
      this.currentPlan.updatedAt = Date.now();
      this.emit({
        type: 'plan_failed',
        plan: this.currentPlan,
        reason: 'Cancelled by user',
      });
    }
  }

  /**
   * Reset (clear the current plan).
   */
  reset(): void {
    this.currentPlan = null;
  }

  /**
   * Get progress summary for UI display.
   */
  getProgress(): {
    total: number;
    completed: number;
    failed: number;
    pending: number;
    percent: number;
  } | null {
    if (!this.currentPlan) return null;
    return getPlanProgress(this.currentPlan);
  }

  /**
   * Update configuration.
   */
  updateConfig(config: Partial<PlannerConfig>): void {
    this.config = { ...this.config, ...config };
  }

  // -----------------------------------------------------------------------
  // Private
  // -----------------------------------------------------------------------

  private async handleStepFailure(
    stepIndex: number,
    error: string,
    context?: ScreenContext,
  ): Promise<{
    success: boolean;
    plan: TaskPlan;
    observation?: string;
  }> {
    this.currentPlan = failStep(this.currentPlan!, stepIndex, error);
    const failedStep = this.currentPlan.steps[stepIndex];

    this.emit({
      type: 'step_failed',
      stepIndex,
      step: failedStep,
      error,
    });

    // Check if we need to replan
    if (this.currentPlan.status === 'replanning' && context && this.vlmQuery) {
      this.emit({
        type: 'replanning',
        plan: this.currentPlan,
        reason: error,
      });

      try {
        this.currentPlan = await replan(
          this.currentPlan,
          failedStep,
          error,
          context,
          this.config,
          this.vlmQuery,
        );
        this.emit({ type: 'plan_created', plan: this.currentPlan });
      } catch (e: any) {
        this.currentPlan.status = 'failed';
        this.currentPlan.updatedAt = Date.now();
        this.emit({
          type: 'plan_failed',
          plan: this.currentPlan,
          reason: `Replan failed: ${e.message}`,
        });
      }
    } else if (this.currentPlan.status === 'failed') {
      this.emit({
        type: 'plan_failed',
        plan: this.currentPlan,
        reason: `Step "${failedStep.description}" failed after ${failedStep.attempts} attempts: ${error}`,
      });
    }

    return {
      success: false,
      plan: this.currentPlan,
      observation: error,
    };
  }
}

// ---------------------------------------------------------------------------
// Singleton
// ---------------------------------------------------------------------------

/** Global planner instance. */
export const ronglePlanner = new RongleTaskPlanner();

/** Also export the class for advanced usage. */
export { RongleTaskPlanner };
