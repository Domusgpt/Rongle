
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
