import torch
import onnx
import onnxruntime as ort
import argparse
from training.model import create_model
import logging
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("export")

def export_onnx(model_path, output_path, num_classes=2):
    """
    Exports the trained model to ONNX.
    """
    logger.info(f"Loading model from {model_path} with {num_classes} classes...")
    model = create_model(num_classes)

    # Load weights if available
    if model_path and model_path != "dummy":
        checkpoint = torch.load(model_path, map_location="cpu")
        if "model_state_dict" in checkpoint:
            model.base_model.load_state_dict(checkpoint["model_state_dict"])
        else:
            model.base_model.load_state_dict(checkpoint)

    model.eval()

    # Create dummy input
    dummy_input = torch.randn(1, 3, 320, 320)

    logger.info("Exporting to ONNX...")

    # Export with fixed outputs
    torch.onnx.export(
        model,
        dummy_input,
        output_path,
        export_params=True,
        opset_version=12,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["bbox_deltas", "scores", "anchors"],
        dynamic_axes={
            "input": {0: "batch_size"},
            "bbox_deltas": {0: "batch_size"},
            "scores": {0: "batch_size"},
            "anchors": {0: "batch_size"}
        }
    )

    logger.info(f"Model exported to {output_path}")

    # Verify
    check_onnx(output_path)

def check_onnx(onnx_path):
    """
    Verifies the exported model with ONNX Runtime.
    """
    logger.info("Verifying ONNX model...")
    onnx_model = onnx.load(onnx_path)
    onnx.checker.check_model(onnx_model)

    ort_session = ort.InferenceSession(onnx_path)

    dummy_input = np.random.randn(1, 3, 320, 320).astype(np.float32)
    outputs = ort_session.run(None, {"input": dummy_input})

    bbox_deltas, scores, anchors = outputs

    logger.info(f"Verification Successful.")
    logger.info(f"  bbox_deltas: {bbox_deltas.shape} (N, Anchors, 4)")
    logger.info(f"  scores:      {scores.shape}      (N, Anchors, Classes)")
    logger.info(f"  anchors:     {anchors.shape}     (N, Anchors, 4)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default="dummy", help="Path to .pth checkpoint or 'dummy'")
    parser.add_argument("--output", type=str, required=True, help="Path to save .onnx model")
    parser.add_argument("--num-classes", type=int, default=2)
    args = parser.parse_args()

    export_onnx(args.model, args.output, args.num_classes)
