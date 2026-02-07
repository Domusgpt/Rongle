import os
import json
import torch
from torch.utils.data import Dataset
from PIL import Image
import logging

logger = logging.getLogger(__name__)

class UIElementDataset(Dataset):
    """
    Dataset for UI Element Detection.
    Expects data in format:
      - image.jpg
      - image.json (LabelMe format or simple bbox list)
    """
    def __init__(self, root_dir, transforms=None):
        self.root_dir = root_dir
        self.transforms = transforms
        self.samples = []

        if not os.path.exists(root_dir):
            logger.warning(f"Dataset root {root_dir} does not exist.")
            return

        for filename in os.listdir(root_dir):
            if filename.endswith(".jpg"):
                img_path = os.path.join(root_dir, filename)
                json_path = os.path.join(root_dir, filename.replace(".jpg", ".json"))
                if os.path.exists(json_path):
                    self.samples.append((img_path, json_path))

        logger.info(f"Found {len(self.samples)} valid samples in {root_dir}")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        img_path, json_path = self.samples[idx]

        # Load Image
        img = Image.open(img_path).convert("RGB")

        # Load Labels
        with open(json_path, "r") as f:
            data = json.load(f)

        boxes = []
        labels = []

        # Assume simple format: {"boxes": [[x1, y1, x2, y2], ...], "labels": [1, ...]}
        # Or LabelMe format (requires parsing)
        # For this implementation, we assume a simplified format produced by data_collector.py

        if "shapes" in data: # LabelMe style
             for shape in data["shapes"]:
                 points = shape["points"]
                 x_min = min(p[0] for p in points)
                 y_min = min(p[1] for p in points)
                 x_max = max(p[0] for p in points)
                 y_max = max(p[1] for p in points)
                 boxes.append([x_min, y_min, x_max, y_max])
                 # Map label string to int ID (needs a class map)
                 labels.append(1) # Default to class 1 for now
        elif "boxes" in data:
            boxes = data["boxes"]
            labels = data["labels"]

        boxes = torch.as_tensor(boxes, dtype=torch.float32)
        labels = torch.as_tensor(labels, dtype=torch.int64)

        target = {}
        target["boxes"] = boxes
        target["labels"] = labels
        target["image_id"] = torch.tensor([idx])

        if self.transforms:
            img, target = self.transforms(img, target)

        # ToTensor is usually handled in transforms, but here for simplicity:
        import torchvision.transforms.functional as F
        img = F.to_tensor(img)

        return img, target
