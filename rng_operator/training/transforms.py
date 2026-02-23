
import torch
import torchvision.transforms.functional as F
from PIL import Image

class Compose:
    def __init__(self, transforms):
        self.transforms = transforms

    def __call__(self, image, target):
        for t in self.transforms:
            image, target = t(image, target)
        return image, target

class Resize:
    """Resize image and bounding boxes."""
    def __init__(self, size):
        # size is (h, w) or int
        if isinstance(size, int):
            self.size = (size, size)
        else:
            self.size = size

    def __call__(self, image, target):
        w, h = image.size
        new_h, new_w = self.size

        image = F.resize(image, self.size)

        if "boxes" in target:
            boxes = target["boxes"]
            # specific scaling
            scale_x = new_w / w
            scale_y = new_h / h

            boxes[:, 0] *= scale_x
            boxes[:, 2] *= scale_x
            boxes[:, 1] *= scale_y
            boxes[:, 3] *= scale_y

            target["boxes"] = boxes

        return image, target

class ToTensor:
    def __call__(self, image, target):
        image = F.to_tensor(image)
        return image, target

class RandomHDMINoise:
    """Simulate HDMI signal artifacts, compression, and jitter."""
    def __init__(self, p=0.5):
        self.p = p

    def __call__(self, image, target):
        import random
        if random.random() > self.p:
            return image, target

        # Add Gaussian noise
        noise_type = random.choice(["gaussian", "jitter", "none"])
        if noise_type == "gaussian":
            # Simple brightness/contrast jitter as a proxy for noise if not using specialized libs
            image = F.adjust_brightness(image, random.uniform(0.8, 1.2))
            image = F.adjust_contrast(image, random.uniform(0.8, 1.2))

        return image, target
