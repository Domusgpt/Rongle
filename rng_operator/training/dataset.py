
import os
import glob
import torch
from torch.utils.data import Dataset
from PIL import Image
import logging

logger = logging.getLogger(__name__)

class UIElementDataset(Dataset):
    """
    Dataset for UI Element Detection.
    Expects a directory structure:
        root/
          images/
            img1.jpg
            ...
          labels/
            img1.txt  (YOLO format: class x_c y_c w h)
            ...
    """
    def __init__(self, root_dir, transform=None):
        self.root_dir = root_dir
        self.transform = transform
        self.image_paths = sorted(glob.glob(os.path.join(root_dir, "images", "*.*")))
        self.label_dir = os.path.join(root_dir, "labels")

        # Filter images without labels
        self.valid_images = []
        for img_path in self.image_paths:
            name = os.path.splitext(os.path.basename(img_path))[0]
            label_path = os.path.join(self.label_dir, name + ".txt")
            if os.path.exists(label_path):
                self.valid_images.append((img_path, label_path))
            else:
                logger.warning(f"No label found for {img_path}")

        logger.info(f"Found {len(self.valid_images)} valid samples in {root_dir}")

    def __len__(self):
        return len(self.valid_images)

    def __getitem__(self, idx):
        img_path, label_path = self.valid_images[idx]

        try:
            image = Image.open(img_path).convert("RGB")
        except Exception as e:
            logger.error(f"Failed to load image {img_path}: {e}")
            # Return a dummy sample or raise error.
            # For simplicity, let's just create a black image
            image = Image.new("RGB", (300, 300))

        boxes = []
        labels = []

        with open(label_path, "r") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 5:
                    cls_id = int(parts[0])
                    # YOLO format is normalized x_c, y_c, w, h
                    x_c, y_c, w, h = map(float, parts[1:5])

                    # Convert to x_min, y_min, x_max, y_max for torchvision
                    img_w, img_h = image.size
                    x_min = (x_c - w/2) * img_w
                    y_min = (y_c - h/2) * img_h
                    x_max = (x_c + w/2) * img_w
                    y_max = (y_c + h/2) * img_h

                    boxes.append([x_min, y_min, x_max, y_max])
                    labels.append(cls_id)

        target = {}
        if boxes:
            target["boxes"] = torch.tensor(boxes, dtype=torch.float32)
            target["labels"] = torch.tensor(labels, dtype=torch.int64)
        else:
            # No objects
            target["boxes"] = torch.zeros((0, 4), dtype=torch.float32)
            target["labels"] = torch.zeros((0,), dtype=torch.int64)

        if self.transform:
            image, target = self.transform(image, target)

        return image, target

def collate_fn(batch):
    return tuple(zip(*batch))
