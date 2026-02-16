# Training the Reflex Cortex

Rongle uses a hybrid vision system:
1.  **VLM (Gemini):** High latency, high intelligence. Understands "Click the red button".
2.  **CNN (Reflex):** Low latency (50ms), low intelligence. Tracks "Button is at (x,y)".

This guide explains how to train the **CNN** to enable fast visual servoing.

## 1. Collect Data

We need images of the target interfaces you want to control.

```bash
# Auto-capture every 2 seconds from Pixel phone
python3 scripts/collect_dataset.py --device "http://192.168.1.50:8080/video" --interval 2.0

# Manual capture from USB Webcam (Press Enter to snap)
python3 scripts/collect_dataset.py --device "/dev/video0"
```

Images are saved to `rng_operator/training/datasets/raw/images`.

## 2. Annotate

Use a tool like [LabelImg](https://github.com/heartexlabs/labelImg) or [CVAT](https://cvat.ai/) to draw bounding boxes.

1.  **Classes:** Define classes like `button`, `input`, `icon`, `text`.
2.  **Format:** Export annotations in **YOLO** format (`.txt` files next to images).
    *   `class_id x_center y_center width height` (normalized 0-1).

## 3. Train

The training harness uses PyTorch and MobileNetV3-SSD.

```bash
# Train on your dataset
python3 -m rng_operator.training.train \
    --data-dir rng_operator/training/datasets/raw \
    --epochs 50 \
    --batch-size 8 \
    --num-classes 5
```

This will produce `.pth` checkpoints in `checkpoints/`.

## 4. Export & Deploy

Convert the best checkpoint to ONNX for fast inference on the Operator.

```bash
python3 -m rng_operator.training.export \
    --checkpoint checkpoints/model_epoch_49.pth \
    --output rng_operator/visual_cortex/models/reflex.onnx \
    --num-classes 5
```

## 5. Configure

Update `rng_operator/config/settings.json`:

```json
{
  "yolo_model_path": "rng_operator/visual_cortex/models/reflex.onnx"
}
```

Now `ReflexTracker` will use your custom brain!
