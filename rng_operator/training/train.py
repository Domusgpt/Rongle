
import os
import torch
import torch.optim as optim
from torch.utils.data import DataLoader
from tqdm import tqdm
import argparse
import logging
import time

from .model import get_model
from .dataset import UIElementDataset, collate_fn
from . import transforms as T

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def train_one_epoch(model, optimizer, data_loader, device, epoch):
    model.train()
    total_loss = 0
    count = 0

    pbar = tqdm(data_loader, desc=f"Epoch {epoch}")
    for images, targets in pbar:
        # Move to device
        images = list(image.to(device) for image in images)
        targets = [{k: v.to(device) for k, v in t.items()} for t in targets]

        loss_dict = model(images, targets)
        losses = sum(loss for loss in loss_dict.values())

        if not torch.isfinite(losses):
            logger.error(f"Loss is infinite: {losses}, stopping training")
            break

        optimizer.zero_grad()
        losses.backward()
        optimizer.step()

        total_loss += losses.item()
        count += 1
        pbar.set_postfix(loss=losses.item())

    avg_loss = total_loss / max(count, 1)
    logger.info(f"Epoch {epoch} finished. Avg Loss: {avg_loss:.4f}")
    return avg_loss

def main():
    parser = argparse.ArgumentParser(description="Train MobileNetV3-SSD for UI Elements")
    parser.add_argument("--data-dir", type=str, required=True, help="Path to dataset root")
    parser.add_argument("--epochs", type=int, default=10, help="Number of epochs")
    parser.add_argument("--batch-size", type=int, default=4, help="Batch size")
    parser.add_argument("--num-classes", type=int, default=2, help="Number of classes (including background)")
    parser.add_argument("--output-dir", type=str, default="checkpoints", help="Directory to save checkpoints")
    parser.add_argument("--device", type=str, default="cuda" if torch.cuda.is_available() else "cpu", help="Device (cuda/cpu)")

    args = parser.parse_args()

    device = torch.device(args.device)
    logger.info(f"Using device: {device}")

    # Transforms
    # We use custom transforms that handle both image and target (bounding boxes)
    transform = T.Compose([
        T.Resize((320, 320)),
        T.ToTensor(),
    ])

    dataset = UIElementDataset(args.data_dir, transform=transform)

    if len(dataset) == 0:
        logger.error(f"No valid images found in {args.data_dir}")
        return

    data_loader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=2,
        collate_fn=collate_fn
    )

    # Model
    model = get_model(num_classes=args.num_classes)
    model.to(device)

    # Optimizer
    params = [p for p in model.parameters() if p.requires_grad]
    optimizer = optim.SGD(params, lr=0.005, momentum=0.9, weight_decay=0.0005)
    lr_scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=3, gamma=0.1)

    os.makedirs(args.output_dir, exist_ok=True)

    for epoch in range(args.epochs):
        train_one_epoch(model, optimizer, data_loader, device, epoch)
        lr_scheduler.step()

        # Save checkpoint
        checkpoint_path = os.path.join(args.output_dir, f"model_epoch_{epoch}.pth")
        torch.save({
            'epoch': epoch,
            'model_state_dict': model.state_dict(),
            'optimizer_state_dict': optimizer.state_dict(),
        }, checkpoint_path)
        logger.info(f"Saved checkpoint to {checkpoint_path}")

    logger.info("Training complete.")

if __name__ == "__main__":
    main()
