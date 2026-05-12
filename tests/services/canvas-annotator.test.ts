import { describe, it, expect } from 'vitest';
import {
  createMark,
  createBox,
  createZone,
  annotationsFromDetections,
  generateAnnotationPrompt
} from '../../src/services/canvas-annotator';
import type { BoundingBox } from '../../src/types';

describe('CanvasAnnotator Builders', () => {
  describe('createMark', () => {
    it('should create a mark annotation with correct properties', () => {
      const x = 100;
      const y = 200;
      const label = 'Test Mark';
      const mark = createMark(x, y, label, 0);

      expect(mark.type).toBe('mark');
      expect(mark.x).toBe(x);
      expect(mark.y).toBe(y);
      expect(mark.label).toBe(label);
      expect(mark.markIndex).toBe(0);
      expect(mark.id).toMatch(/^ann_/);
      expect(mark.color).toBeDefined();
    });

    it('should use the default mark counter if index is not provided', () => {
      const mark1 = createMark(10, 10, 'Mark 1');
      const mark2 = createMark(20, 20, 'Mark 2');

      expect(mark1.markIndex).toBeDefined();
      expect(mark2.markIndex).toBeGreaterThan(mark1.markIndex!);
    });

    it('should generate unique IDs', () => {
      const mark1 = createMark(10, 10, 'Mark 1');
      const mark2 = createMark(10, 10, 'Mark 1');
      expect(mark1.id).not.toBe(mark2.id);
    });
  });

  describe('createBox', () => {
    it('should create a box annotation with correct properties', () => {
      const x = 50;
      const y = 60;
      const width = 100;
      const height = 80;
      const label = 'Test Box';
      const box = createBox(x, y, width, height, label);

      expect(box.type).toBe('box');
      expect(box.x).toBe(x);
      expect(box.y).toBe(y);
      expect(box.width).toBe(width);
      expect(box.height).toBe(height);
      expect(box.label).toBe(label);
      expect(box.id).toMatch(/^ann_/);
      expect(box.color).toBeDefined();
    });

    it('should use provided color if specified', () => {
      const color = '#FF0000';
      const box = createBox(0, 0, 10, 10, 'Red Box', color);
      expect(box.color).toBe(color);
    });
  });

  describe('createZone', () => {
    it('should create a zone annotation with correct properties', () => {
      const x = 0;
      const y = 0;
      const width = 500;
      const height = 400;
      const label = 'Safe Zone';
      const zone = createZone(x, y, width, height, label);

      expect(zone.type).toBe('zone');
      expect(zone.x).toBe(x);
      expect(zone.y).toBe(y);
      expect(zone.width).toBe(width);
      expect(zone.height).toBe(height);
      expect(zone.label).toBe(label);
      expect(zone.id).toMatch(/^ann_/);
    });

    it('should have a default semi-transparent color', () => {
      const zone = createZone(0, 0, 10, 10, 'Zone');
      expect(zone.color).toBe('#00FF4140');
    });

    it('should allow custom color', () => {
      const color = '#FF000080';
      const zone = createZone(0, 0, 10, 10, 'Custom Zone', color);
      expect(zone.color).toBe(color);
    });
  });

  describe('annotationsFromDetections', () => {
    it('should convert bounding boxes to annotations', () => {
      const detections: BoundingBox[] = [
        { x: 10, y: 10, width: 50, height: 50, label: 'Button', confidence: 0.9 },
        { x: 100, y: 100, width: 20, height: 20, label: 'Icon', confidence: 0.8 }
      ];

      const anns = annotationsFromDetections(detections);

      expect(anns).toHaveLength(2);
      expect(anns[0].type).toBe('box');
      expect(anns[0].label).toBe('[1] Button');
      expect(anns[0].markIndex).toBe(0);

      expect(anns[1].type).toBe('box');
      expect(anns[1].label).toBe('[2] Icon');
      expect(anns[1].markIndex).toBe(1);
    });

    it('should handle empty detections', () => {
      const anns = annotationsFromDetections([]);
      expect(anns).toEqual([]);
    });

    it('should reset mark counter and assign sequential indices', () => {
      // First call
      const firstBatch = annotationsFromDetections([
        { x: 0, y: 0, width: 1, height: 1, label: 'A', confidence: 1 }
      ]);
      expect(firstBatch[0].markIndex).toBe(0);

      // Second call should also start at 0 if _markCounter is reset
      const secondBatch = annotationsFromDetections([
        { x: 0, y: 0, width: 1, height: 1, label: 'B', confidence: 1 }
      ]);
      expect(secondBatch[0].markIndex).toBe(0);
    });
  });

  describe('generateAnnotationPrompt', () => {
    it('should return an empty string for empty input', () => {
      expect(generateAnnotationPrompt([])).toBe('');
    });

    it('should return an empty string if no annotations have a markIndex', () => {
      const zone = createZone(0, 0, 10, 10, 'Zone');
      expect(generateAnnotationPrompt([zone])).toBe('');
    });

    it('should format marks correctly in the prompt', () => {
      const mark = createMark(100, 200, 'Settings', 1);
      const prompt = generateAnnotationPrompt([mark]);

      expect(prompt).toContain('The image has numbered markers overlaid on it:');
      expect(prompt).toContain('[1] "Settings" at (100,200)');
      expect(prompt).toContain('Refer to elements by their [number]');
    });

    it('should format boxes correctly in the prompt', () => {
      const box = createBox(50, 60, 100, 80, 'Login Button');
      box.markIndex = 2; // Manually setting for deterministic test
      const prompt = generateAnnotationPrompt([box]);

      expect(prompt).toContain('[2] "Login Button" bbox (50,60,150,140)');
    });

    it('should combine multiple annotations in the prompt', () => {
      const mark = createMark(10, 10, 'A', 1);
      const box = createBox(100, 100, 20, 20, 'B');
      box.markIndex = 2;

      const prompt = generateAnnotationPrompt([mark, box]);
      expect(prompt).toContain('[1] "A" at (10,10)');
      expect(prompt).toContain('[2] "B" bbox (100,100,120,120)');
    });
  });
});
