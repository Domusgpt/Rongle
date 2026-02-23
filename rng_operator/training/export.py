
import torch
import argparse
import logging
import os
from .model import get_model

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Export MobileNetV3-SSD to ONNX")
    parser.add_argument("--checkpoint", type=str, required=True, help="Path to .pth checkpoint")
    parser.add_argument("--output", type=str, default="model.onnx", help="Output ONNX file")
    parser.add_argument("--num-classes", type=int, default=2, help="Number of classes used in training")
    parser.add_argument("--opset", type=int, default=12, help="ONNX opset version")

    args = parser.parse_args()

    # Load model
    logger.info(f"Loading model with {args.num_classes} classes")
    model = get_model(num_classes=args.num_classes)

    if not os.path.exists(args.checkpoint):
        raise FileNotFoundError(f"Checkpoint not found: {args.checkpoint}")

    checkpoint = torch.load(args.checkpoint, map_location="cpu")
    if "model_state_dict" in checkpoint:
        model.load_state_dict(checkpoint["model_state_dict"])
    else:
        model.load_state_dict(checkpoint)

    model.eval()

    # Dummy input
    dummy_input = torch.randn(1, 3, 320, 320)

    logger.info(f"Exporting to {args.output}...")
    torch.onnx.export(
        model,
        dummy_input,
        args.output,
        opset_version=args.opset,
        input_names=["input"],
        output_names=["boxes", "scores", "labels"],
        dynamic_axes={
            "input": {0: "batch_size"},
            "boxes": {0: "batch_size"},
            "scores": {0: "batch_size"},
            "labels": {0: "batch_size"},
        }
    )
    logger.info("Export complete.")

if __name__ == "__main__":
    main()
