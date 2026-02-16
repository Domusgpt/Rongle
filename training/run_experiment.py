"""
Rongle Training Experiment Runner
----------------------------------
This script performs a complete "Dry Run" of the Machine Learning pipeline.
1. Generates a Synthetic Dataset (since we might not have real data yet).
2. Trains the MobileNet-SSD model for a few epochs.
3. Exports the model to ONNX.
4. Verifies the export.

Usage:
    python3 training/run_experiment.py
"""

import os
import sys
import shutil
import cv2
import numpy as np
import json
import logging
from pathlib import Path

# Add root to path
sys.path.append(os.getcwd())

# Ensure we can import training modules
try:
    from training.train import train_model
    from training.dataset import UIElementDataset
    from training.export import export_onnx
    import torch
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("experiment")

DATA_DIR = Path("training/data/synthetic_experiment")
MODEL_PATH = "experiment_model.pth"
ONNX_PATH = "experiment_model.onnx"

def generate_synthetic_data(num_samples=20):
    """Generates simple images with white rectangles (buttons) on black background."""
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    logger.info(f"Generating {num_samples} synthetic samples in {DATA_DIR}...")

    for i in range(num_samples):
        # Create black image 320x320
        img = np.zeros((320, 320, 3), dtype=np.uint8)

        # Random button position
        x = np.random.randint(0, 200)
        y = np.random.randint(0, 200)
        w = np.random.randint(50, 100)
        h = np.random.randint(20, 50)

        # Draw "Button"
        cv2.rectangle(img, (x, y), (x+w, y+h), (255, 255, 255), -1)

        # Save Image
        img_path = DATA_DIR / f"sample_{i}.jpg"
        cv2.imwrite(str(img_path), img)

        # Save Label
        label_data = {
            "boxes": [[float(x), float(y), float(x+w), float(y+h)]],
            "labels": [1] # Class 1 = "Button"
        }
        with open(str(img_path).replace(".jpg", ".json"), "w") as f:
            json.dump(label_data, f)

    logger.info("Data generation complete.")

def run_training():
    logger.info("Loading dataset...")
    dataset = UIElementDataset(DATA_DIR)

    logger.info("Starting training (Dry Run - 2 Epochs)...")
    # Train for just 2 epochs to verify pipeline mechanics
    trained_wrapper = train_model(dataset, epochs=2)

    logger.info(f"Saving checkpoint to {MODEL_PATH}...")
    torch.save(trained_wrapper.base_model.state_dict(), MODEL_PATH)

    return MODEL_PATH

def run_export_and_verify(pth_path):
    logger.info(f"Exporting {pth_path} to {ONNX_PATH}...")
    export_onnx(pth_path, ONNX_PATH, num_classes=2)

    if os.path.exists(ONNX_PATH):
        file_size = os.path.getsize(ONNX_PATH) / (1024 * 1024)
        logger.info(f"✅ Export Successful! Model size: {file_size:.2f} MB")
    else:
        logger.error("❌ Export Failed: File not created.")
        sys.exit(1)

def cleanup():
    # Optional: cleanup artifacts
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)
    if os.path.exists(MODEL_PATH):
        os.remove(MODEL_PATH)
    if os.path.exists(ONNX_PATH):
        os.remove(ONNX_PATH)
    pass

def main():
    try:
        generate_synthetic_data()
        pth = run_training()
        run_export_and_verify(pth)
        logger.info("Experiment Completed Successfully.")
    except Exception as e:
        logger.exception(f"Experiment Failed: {e}")
        sys.exit(1)
    finally:
        cleanup()

if __name__ == "__main__":
    main()
