import { describe, it, expect, vi, beforeEach } from 'vitest';
import { generatePlan, replan, verifyStep } from '../../src/services/task-planner/planner';
import type { TaskPlan, TaskStep, ScreenContext, PlannerConfig } from '../../src/services/task-planner/types';

describe('Task Planner', () => {
  const mockConfig: PlannerConfig = {
    maxSteps: 5,
    maxRetriesPerStep: 3,
    maxReplans: 3,
    useCNNContext: true,
    useOCRContext: true,
    minStepConfidence: 0.5,
    verificationDelayMs: 1000,
  };

  const mockContext: ScreenContext = {
    imageBase64: 'mock_image_base64',
    screenType: 'desktop',
    detectedElements: [],
    visibleText: 'Mock Screen Text',
    previousAction: 'none',
  };

  const mockVlmQuery = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('generatePlan', () => {
    it('should return a TaskPlan with correct initial state', async () => {
      const goal = 'Test Goal';
      const mockStepsResponse = JSON.stringify([
        { description: 'Step 1', action: 'DELAY 100', verificationCriteria: 'Check 1' },
      ]);
      mockVlmQuery.mockResolvedValue(mockStepsResponse);

      const plan = await generatePlan(goal, mockContext, mockConfig, mockVlmQuery);

      expect(plan.goal).toBe(goal);
      expect(plan.steps).toHaveLength(1);
      expect(plan.steps[0].description).toBe('Step 1');
      expect(plan.checkpointIndex).toBe(-1);
      expect(plan.replanCount).toBe(0);
      expect(plan.status).toBe('executing');
      expect(plan.id).toMatch(/^plan_/);
    });

    it('should correctly incorporate the goal into the VLM prompt', async () => {
      const goal = 'Unique Task Goal';
      mockVlmQuery.mockResolvedValue('[]');

      await generatePlan(goal, mockContext, mockConfig, mockVlmQuery);

      expect(mockVlmQuery).toHaveBeenCalledWith(
        expect.stringContaining(`GOAL: "${goal}"`),
        mockContext.imageBase64
      );
    });
  });

  describe('replan', () => {
    const originalPlan: TaskPlan = {
      id: 'plan_123',
      goal: 'Original Goal',
      steps: [
        {
          id: 'step_0',
          index: 0,
          description: 'Completed Step',
          action: 'ACTION 1',
          verificationCriteria: 'Crit 1',
          status: 'completed',
          attempts: 1,
          maxRetries: 3,
          dependsOn: [],
          updatedAt: Date.now(),
        },
        {
          id: 'step_1',
          index: 1,
          description: 'Failed Step',
          action: 'ACTION 2',
          verificationCriteria: 'Crit 2',
          status: 'failed',
          attempts: 3,
          maxRetries: 3,
          dependsOn: [],
          updatedAt: Date.now(),
        }
      ],
      currentStepIndex: 1,
      status: 'failed',
      checkpointIndex: 0,
      replanCount: 0,
      maxReplans: 3,
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };

    it('should increment replanCount and reset status to executing', async () => {
      const failedStep = originalPlan.steps[1];
      const failureReason = 'Element not found';
      const mockNewSteps = JSON.stringify([
        { description: 'New Step 1', action: 'ACTION 3', verificationCriteria: 'Crit 3' },
      ]);
      mockVlmQuery.mockResolvedValue(mockNewSteps);

      const newPlan = await replan(originalPlan, failedStep, failureReason, mockContext, mockConfig, mockVlmQuery);

      expect(newPlan.replanCount).toBe(1);
      expect(newPlan.status).toBe('executing');
      expect(newPlan.steps[0].description).toBe('New Step 1');
      expect(newPlan.currentStepIndex).toBe(0);
    });

    it('should correctly incorporate completed steps and failure reason into the REPLAN prompt', async () => {
      const failedStep = originalPlan.steps[1];
      const failureReason = 'Timeout';
      mockVlmQuery.mockResolvedValue('[]');

      await replan(originalPlan, failedStep, failureReason, mockContext, mockConfig, mockVlmQuery);

      const prompt = mockVlmQuery.mock.calls[0][0];
      expect(prompt).toContain('ORIGINAL GOAL: "Original Goal"');
      expect(prompt).toContain('COMPLETED STEPS: 1. Completed Step');
      expect(prompt).toContain('FAILED STEP: "Failed Step"');
      expect(prompt).toContain('FAILURE REASON: Timeout');
    });

    it('should handle markdown-fenced JSON responses from the VLM', async () => {
      const failedStep = originalPlan.steps[1];
      const mockMarkdownResponse = '```json\n[{"description": "Step from markdown", "action": "ACTION", "verificationCriteria": "CRIT"}]\n```';
      mockVlmQuery.mockResolvedValue(mockMarkdownResponse);

      const newPlan = await replan(originalPlan, failedStep, 'reason', mockContext, mockConfig, mockVlmQuery);

      expect(newPlan.steps[0].description).toBe('Step from markdown');
    });

    it('should throw an error when the VLM returns invalid JSON', async () => {
      const failedStep = originalPlan.steps[1];
      mockVlmQuery.mockResolvedValue('Invalid JSON string');

      await expect(replan(originalPlan, failedStep, 'reason', mockContext, mockConfig, mockVlmQuery))
        .rejects.toThrow('Failed to parse plan steps');
    });
  });

  describe('verifyStep', () => {
    const mockStep: TaskStep = {
      id: 'step_1',
      index: 1,
      description: 'Test Step',
      action: 'ACTION',
      verificationCriteria: 'Should see X',
      status: 'in_progress',
      attempts: 1,
      maxRetries: 3,
      dependsOn: [],
      updatedAt: Date.now(),
    };

    it('should correctly parse successful verification', async () => {
      const mockResponse = JSON.stringify({
        success: true,
        confidence: 0.95,
        observation: 'I see X'
      });
      mockVlmQuery.mockResolvedValue(mockResponse);

      const result = await verifyStep(mockStep, mockContext, mockVlmQuery);

      expect(result.success).toBe(true);
      expect(result.confidence).toBe(0.95);
      expect(result.observation).toBe('I see X');
    });

    it('should return success: false if the VLM response is malformed', async () => {
      mockVlmQuery.mockResolvedValue('Not a JSON');

      const result = await verifyStep(mockStep, mockContext, mockVlmQuery);

      expect(result.success).toBe(false);
      expect(result.observation).toContain('Failed to parse verification response');
    });
  });
});
