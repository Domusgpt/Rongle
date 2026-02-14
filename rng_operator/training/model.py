
import torch
import torchvision
from torchvision.models.detection.ssdlite import SSDLiteHead
from torchvision.models.detection import _utils as det_utils
import functools

def get_model(num_classes):
    """
    Returns an SSDLite MobileNetV3 Large model fine-tuned for `num_classes`.
    """
    # Load the pretrained model
    model = torchvision.models.detection.ssdlite320_mobilenet_v3_large(
        weights="DEFAULT"
    )

    # Calculate input channels for the head from the backbone
    in_channels = det_utils.retrieve_out_channels(model.backbone, (320, 320))

    num_anchors = model.anchor_generator.num_anchors_per_location()

    # We need to provide a normalization layer. MobileNetV3 uses BatchNorm2d usually.
    norm_layer = functools.partial(torch.nn.BatchNorm2d, eps=0.001, momentum=0.03)

    model.head = SSDLiteHead(in_channels, num_anchors, num_classes, norm_layer)

    return model
