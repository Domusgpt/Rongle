# Training the Vision Cortex 🧠

This guide details how to train the local CNN (MobileNet-SSD) used by the Operator for low-latency detection ("Foveated Rendering").

## Overview

The `training/` directory contains a complete pipeline to:
1.  **Collect Data**: Capture frames from the device.
2.  **Label Data**: Use a VLM (Gemini) to auto-label UI elements.
3.  **Train Model**: Fine-tune a MobileNetV3-SSD model.
4.  **Export ONNX**: Convert the model for optimized inference.

## Prerequisites

```bash
pip install -r training/requirements.txt
```

## Why Cloud Compute?

Training a Convolutional Neural Network (CNN) like MobileNet-SSD is computationally intensive.
*   **Inference (Edge)**: Running the model to detect objects takes ~10-30ms on a CPU (Pi/Android).
*   **Training (Cloud)**: Teaching the model requires processing thousands of images millions of times. On a Raspberry Pi CPU, this would take **weeks**. On a Cloud GPU (like NVIDIA T4/A10G), it takes **minutes to hours**.

Therefore, the workflow is:
1.  **Collect Data** on the Edge Device.
2.  **Upload Data** to a powerful machine (Cloud or Dev PC with GPU).
3.  **Train** the model.
4.  **Download** the `.onnx` file back to the Edge Device.

## Workflow

### 1. Data Collection
Use the `data_collector.py` tool (or just run the agent) to save frames to `training/data/raw`.

```bash
# Capture every 5th frame
python -m training.data_collector --interval 5 --output training/data/raw
```

### 2. Training
Run the training harness. This script handles dataset loading, training, and exporting.

```bash
# Train for 50 epochs on the collected dataset
python -m training.train --dataset training/data/raw --epochs 50
```

### 3. Verification
The training script automatically verifies the exported `model.onnx`. You can also verify manually:

```bash
python -m training.export --model model.pth --output model.onnx --verify
```

### 4. Deployment
Copy the exported model to the operator's visual cortex:

```bash
cp model.onnx rongle_operator/visual_cortex/mobilenet_ssd.onnx
```

## Technical Details

*   **Model Architecture**: SSDLite320 with MobileNetV3-Large Backbone.
*   **Input Size**: 320x320 RGB.
*   **Outputs**:
    *   `bbox_deltas`: Raw bounding box regression (N, Anchors, 4).
    *   `scores`: Class logits (N, Anchors, Classes).
    *   `anchors`: Default anchor boxes (N, Anchors, 4).
*   **Post-Processing**: NMS is performed in the `FastDetector` class (Python side) to avoid ONNX export compatibility issues.

---
[Back to Documentation Index](INDEX.md)
