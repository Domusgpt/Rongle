"""
Train MobileNet-SSD — Harness for fine-tuning local detection models.

This script:
1. Loads the dataset collected by `training/data_collector.py`.
2. Uses an LLM (Gemini/GPT-4V) to label the frames if no labels exist ("Auto-Labeling").
3. Fine-tunes a MobileNet-SSD v2 model using PyTorch.
4. Exports the model to ONNX for use in `FastDetector`.

Usage:
    python -m training.train --dataset training/data/raw --epochs 10
"""

import argparse
import glob
import json
import logging
import os
from pathlib import Path

# We assume requirements are installed if running this script
try:
    import torch
    from training.dataset import UIElementDataset
    from training.model import create_model
    from training.export import export_onnx
except ImportError as e:
    print(f"Error: Missing dependencies. Please run 'pip install -r training/requirements.txt'.\n{e}")
    exit(1)

logger = logging.getLogger("trainer")

def train_model(dataset, epochs: int):
    """
    Fine-tune MobileNet-SSD.
    """
    logger.info(f"Starting training for {epochs} epochs...")

    # 1. Setup DataLoaders
    data_loader = torch.utils.data.DataLoader(
        dataset, batch_size=4, shuffle=True, num_workers=0,
        collate_fn=lambda x: tuple(zip(*x)) # Standard collate for detection
    )

    # 2. Model
    # 2 classes: background, target
    model = create_model(num_classes=2)

    # Note: ExportableSSDLite wraps the base_model.
    # For training, we need to call base_model.train() and ensure it returns losses.
    # ExportableSSDLite.forward returns predictions.
    # We should train the base_model directly.

    model.base_model.train()

    # 3. Optimizer
    params = [p for p in model.base_model.parameters() if p.requires_grad]
    optimizer = torch.optim.SGD(params, lr=0.005, momentum=0.9, weight_decay=0.0005)

    # 4. Training Loop
    device = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')
    model.base_model.to(device)

    for epoch in range(epochs):
        model.base_model.train()
        total_loss = 0
        for images, targets in data_loader:
            images = list(image.to(device) for image in images)
            targets = [{k: v.to(device) for k, v in t.items()} for t in targets]

            # SSD returns dict of losses
            loss_dict = model.base_model(images, targets)
            losses = sum(loss for loss in loss_dict.values())

            optimizer.zero_grad()
            losses.backward()
            optimizer.step()

            total_loss += losses.item()

        logger.info(f"Epoch {epoch}: Loss {total_loss}")

    return model

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=str, required=True)
    parser.add_argument("--epochs", type=int, default=10)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    dataset = UIElementDataset(Path(args.dataset))

    if len(dataset) == 0:
        logger.error("No data found!")
        return

    trained_model_wrapper = train_model(dataset, args.epochs)

    # Save checkpoint
    torch.save(trained_model_wrapper.base_model.state_dict(), "model.pth")

    # Export
    export_onnx("model.pth", "rongle_operator/visual_cortex/mobilenet_ssd.onnx", num_classes=2)
    logger.info("Training complete. Model saved.")

if __name__ == "__main__":
    main()
