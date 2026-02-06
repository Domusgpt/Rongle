// ---------------------------------------------------------------------------
// Architecture — MobileNet-style CNN definitions using TF.js Layers API.
//
// Defines two models:
//   1. RongleNet-Detect:  MobileNet-SSD for UI element detection (320x320)
//   2. RongleNet-Classify: Lightweight screen classifier (224x224)
//
// Both use depthwise separable convolutions (MobileNetV1 style) for
// maximum inference speed on mobile WebGL.
//
// Models start with random weights — load pre-trained weights via
// engine.loadModelFromURL() when available.
// ---------------------------------------------------------------------------

import { getTF, loadTF } from './engine';
import { UI_CLASSES, SCREEN_CLASSES } from './types';

// ---------------------------------------------------------------------------
// Building blocks
// ---------------------------------------------------------------------------

/**
 * Depthwise separable convolution block:
 *   DepthwiseConv2D → BatchNorm → ReLU6 → Conv2D 1x1 → BatchNorm → ReLU6
 *
 * This is the core building block of MobileNetV1, providing ~8-9x fewer
 * parameters and FLOPs than standard convolutions.
 */
function depthwiseSeparableBlock(
  input: any,
  filters: number,
  stride: number = 1,
  blockId: string,
): any {
  const tf = getTF();

  // Depthwise convolution
  let x = tf.layers.depthwiseConv2d({
    kernelSize: 3,
    strides: stride,
    padding: 'same',
    useBias: false,
    name: `dw_conv_${blockId}`,
  }).apply(input);

  x = tf.layers.batchNormalization({ name: `dw_bn_${blockId}` }).apply(x);
  x = tf.layers.activation({ activation: 'relu6', name: `dw_relu_${blockId}` }).apply(x);

  // Pointwise 1x1 convolution
  x = tf.layers.conv2d({
    filters,
    kernelSize: 1,
    strides: 1,
    padding: 'same',
    useBias: false,
    name: `pw_conv_${blockId}`,
  }).apply(x);

  x = tf.layers.batchNormalization({ name: `pw_bn_${blockId}` }).apply(x);
  x = tf.layers.activation({ activation: 'relu6', name: `pw_relu_${blockId}` }).apply(x);

  return x;
}

/**
 * Standard convolution block:
 *   Conv2D → BatchNorm → ReLU6
 */
function convBlock(
  input: any,
  filters: number,
  kernelSize: number,
  stride: number,
  blockId: string,
): any {
  const tf = getTF();

  let x = tf.layers.conv2d({
    filters,
    kernelSize,
    strides: stride,
    padding: 'same',
    useBias: false,
    name: `conv_${blockId}`,
  }).apply(input);

  x = tf.layers.batchNormalization({ name: `bn_${blockId}` }).apply(x);
  x = tf.layers.activation({ activation: 'relu6', name: `relu_${blockId}` }).apply(x);

  return x;
}

// ---------------------------------------------------------------------------
// RongleNet-Detect: MobileNet-SSD for UI Element Detection
// ---------------------------------------------------------------------------

/**
 * Feature map sizes at each detection level.
 * Input 320x320 → stride 4,8,16,32 → feature maps 80,40,20,10
 */
export const DETECTOR_FEATURE_MAPS = [80, 40, 20, 10];
export const DETECTOR_ANCHORS_PER_CELL = 3;

/**
 * Build the UI element detection model.
 *
 * Architecture:
 *   Input (320, 320, 3)
 *   → Conv 3x3/2 → 32 filters (160x160)
 *   → DW-Sep /1 → 64  (160x160)
 *   → DW-Sep /2 → 128 (80x80)   → SSD Head Level 0
 *   → DW-Sep /1 → 128 (80x80)
 *   → DW-Sep /2 → 256 (40x40)   → SSD Head Level 1
 *   → DW-Sep /1 → 256 (40x40)
 *   → DW-Sep /2 → 512 (20x20)   → SSD Head Level 2
 *   → DW-Sep /1 → 512 (20x20)
 *   → DW-Sep /2 → 1024 (10x10)  → SSD Head Level 3
 *
 * Each SSD head outputs:
 *   anchorsPerCell * (4 + numClasses + 1) per cell
 *   = 3 * (4 + 17 + 1) = 66 channels
 *
 * Returns: { model, featureMapSizes, anchorsPerCell }
 */
export async function buildDetector(inputSize: number = 320): Promise<{
  model: any;
  featureMapSizes: number[];
  anchorsPerCell: number;
}> {
  const tf = await loadTF();
  if (!tf) throw new Error('TF.js not available');

  const numClasses = UI_CLASSES.length; // 17
  const outputChannels = DETECTOR_ANCHORS_PER_CELL * (4 + numClasses + 1); // 66

  const input = tf.input({ shape: [inputSize, inputSize, 3], name: 'detector_input' });

  // Backbone
  let x = convBlock(input, 32, 3, 2, 'stem');           // 160x160

  x = depthwiseSeparableBlock(x, 64, 1, 'b1');           // 160x160
  x = depthwiseSeparableBlock(x, 128, 2, 'b2');          // 80x80
  const feat0 = x;                                       // Level 0: 80x80

  x = depthwiseSeparableBlock(x, 128, 1, 'b3');          // 80x80
  x = depthwiseSeparableBlock(x, 256, 2, 'b4');          // 40x40
  const feat1 = x;                                       // Level 1: 40x40

  x = depthwiseSeparableBlock(x, 256, 1, 'b5');          // 40x40
  x = depthwiseSeparableBlock(x, 512, 2, 'b6');          // 20x20
  const feat2 = x;                                       // Level 2: 20x20

  x = depthwiseSeparableBlock(x, 512, 1, 'b7');          // 20x20
  x = depthwiseSeparableBlock(x, 1024, 2, 'b8');         // 10x10
  const feat3 = x;                                       // Level 3: 10x10

  // SSD detection heads — one 1x1 conv per feature level
  const heads = [feat0, feat1, feat2, feat3].map((feat, i) => {
    const head = tf.layers.conv2d({
      filters: outputChannels,
      kernelSize: 1,
      padding: 'same',
      name: `ssd_head_${i}`,
    }).apply(feat);

    // Reshape to [batch, numAnchors, 4 + numClasses + 1]
    const fmSize = DETECTOR_FEATURE_MAPS[i];
    const numAnchors = fmSize * fmSize * DETECTOR_ANCHORS_PER_CELL;
    return tf.layers.reshape({
      targetShape: [numAnchors, 4 + numClasses + 1],
      name: `ssd_reshape_${i}`,
    }).apply(head);
  });

  // Concatenate all detection heads along the anchor dimension
  const allDetections = tf.layers.concatenate({ axis: 1, name: 'ssd_concat' }).apply(heads);

  const model = tf.model({ inputs: input, outputs: allDetections, name: 'RongleNet-Detect' });

  console.log(`[Architecture] RongleNet-Detect built: ${model.countParams()} params`);

  return {
    model,
    featureMapSizes: DETECTOR_FEATURE_MAPS,
    anchorsPerCell: DETECTOR_ANCHORS_PER_CELL,
  };
}

// ---------------------------------------------------------------------------
// RongleNet-Classify: Screen Type Classifier
// ---------------------------------------------------------------------------

/**
 * Build the screen classification model.
 *
 * Architecture:
 *   Input (224, 224, 3)
 *   → Conv 3x3/2 → 32  (112x112)
 *   → DW-Sep /1 → 64   (112x112)
 *   → DW-Sep /2 → 128  (56x56)
 *   → DW-Sep /2 → 256  (28x28)
 *   → DW-Sep /2 → 512  (14x14)
 *   → DW-Sep /2 → 512  (7x7)
 *   → GlobalAvgPool     (512)
 *   → Dense → 128 → ReLU
 *   → Dropout 0.3
 *   → Dense → numClasses → Softmax
 */
export async function buildClassifier(inputSize: number = 224): Promise<any> {
  const tf = await loadTF();
  if (!tf) throw new Error('TF.js not available');

  const numClasses = SCREEN_CLASSES.length; // 11

  const input = tf.input({ shape: [inputSize, inputSize, 3], name: 'classifier_input' });

  let x = convBlock(input, 32, 3, 2, 'cls_stem');         // 112x112
  x = depthwiseSeparableBlock(x, 64, 1, 'cls_b1');        // 112x112
  x = depthwiseSeparableBlock(x, 128, 2, 'cls_b2');       // 56x56
  x = depthwiseSeparableBlock(x, 256, 2, 'cls_b3');       // 28x28
  x = depthwiseSeparableBlock(x, 512, 2, 'cls_b4');       // 14x14
  x = depthwiseSeparableBlock(x, 512, 2, 'cls_b5');       // 7x7

  x = tf.layers.globalAveragePooling2d({ name: 'cls_gap' }).apply(x);
  x = tf.layers.dense({ units: 128, activation: 'relu', name: 'cls_fc1' }).apply(x);
  x = tf.layers.dropout({ rate: 0.3, name: 'cls_dropout' }).apply(x);
  x = tf.layers.dense({ units: numClasses, activation: 'softmax', name: 'cls_output' }).apply(x);

  const model = tf.model({ inputs: input, outputs: x, name: 'RongleNet-Classify' });

  console.log(`[Architecture] RongleNet-Classify built: ${model.countParams()} params`);

  return model;
}

/**
 * Print a human-readable model summary to console.
 */
export function printModelSummary(model: any): void {
  if (model?.summary) {
    model.summary();
  }
}
