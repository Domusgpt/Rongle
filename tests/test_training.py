
import unittest
import os
import shutil

try:
    import torch
    from rng_operator.training.model import get_model
    from rng_operator.training.dataset import UIElementDataset
    from rng_operator.training import transforms as T
except ImportError:
    torch = None

@unittest.skipIf(torch is None, "Torch not installed")
class TestTraining(unittest.TestCase):
    def test_model_creation(self):
        """Test if the model is created with correct number of classes."""
        num_classes = 5
        model = get_model(num_classes)

        # Check if head has correct output channels
        dummy_input = torch.randn(2, 3, 320, 320)

        # In train mode, it returns loss dict
        model.train()
        # It needs targets to return loss
        targets = [
            {
                "boxes": torch.tensor([[10, 10, 50, 50]], dtype=torch.float32),
                "labels": torch.tensor([1], dtype=torch.int64)
            },
            {
                "boxes": torch.tensor([[20, 20, 60, 60]], dtype=torch.float32),
                "labels": torch.tensor([2], dtype=torch.int64)
            }
        ]

        losses = model(dummy_input, targets)
        self.assertTrue(isinstance(losses, dict))
        self.assertTrue("bbox_regression" in losses)
        self.assertTrue("classification" in losses)

        # In eval mode, it returns detections
        model.eval()
        detections = model(dummy_input)
        self.assertTrue(isinstance(detections, list))
        self.assertEqual(len(detections), 2)
        self.assertTrue("boxes" in detections[0])

    def test_dataset_transforms(self):
        """Test if transforms resize image and boxes."""
        # Create a dummy image and label
        os.makedirs("temp_data/images", exist_ok=True)
        os.makedirs("temp_data/labels", exist_ok=True)

        from PIL import Image
        img = Image.new("RGB", (100, 100), color="red")
        img.save("temp_data/images/test.jpg")

        # Label: class 1, center (50, 50), size (20, 20) -> [40, 40, 60, 60]
        # YOLO format: 1 0.5 0.5 0.2 0.2
        with open("temp_data/labels/test.txt", "w") as f:
            f.write("1 0.5 0.5 0.2 0.2\n")

        transform = T.Compose([
            T.Resize((50, 50)),
            T.ToTensor(),
        ])

        dataset = UIElementDataset("temp_data", transform=transform)
        image, target = dataset[0]

        # Check image size (tensor is C, H, W)
        self.assertEqual(image.shape, (3, 50, 50))

        # Check box scaling
        # Original: [40, 40, 60, 60]
        # Scaled by 0.5: [20, 20, 30, 30]
        boxes = target["boxes"]
        self.assertTrue(torch.allclose(boxes, torch.tensor([[20.0, 20.0, 30.0, 30.0]])))

        # Clean up
        shutil.rmtree("temp_data")

    # def test_export_onnx(self):
    #     ... (Commented out)

if __name__ == "__main__":
    unittest.main()
