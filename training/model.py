import torch
import torchvision
from torchvision.models.detection import ssdlite320_mobilenet_v3_large
from collections import OrderedDict

class ExportableSSDLite(torch.nn.Module):
    def __init__(self, num_classes):
        super().__init__()
        self.base_model = ssdlite320_mobilenet_v3_large(
            weights_backbone=None,
            num_classes=num_classes,
            weights=None
        )
        self.base_model.eval()

    def forward(self, images):
        if isinstance(images, torch.Tensor) and images.dim() == 4:
            images_list = list(images.unbind(0))
        else:
            images_list = images

        images_transformed, _ = self.base_model.transform(images_list, None)
        features = self.base_model.backbone(images_transformed.tensors)
        if isinstance(features, torch.Tensor):
            features = OrderedDict([('0', features)])

        feature_maps = list(features.values())
        head_outputs = self.base_model.head(feature_maps)

        anchors = self.base_model.anchor_generator(images_transformed, feature_maps)

        bbox_regression = head_outputs["bbox_regression"]
        pred_scores = head_outputs["cls_logits"]

        # Debug types
        # print(f"Head Type: {type(self.base_model.head)}")
        # print(f"Bbox Reg Type: {type(bbox_regression)}")

        if isinstance(bbox_regression, torch.Tensor):
             # Already flattened?
             # print(f"Bbox Reg Tensor Shape: {bbox_regression.shape}")
             flat_bbox_deltas = bbox_regression
             flat_scores = pred_scores
        elif isinstance(bbox_regression, list):
             # print(f"Bbox Reg List Len: {len(bbox_regression)}")
             # Check first element
             if len(bbox_regression) > 0:
                 b0 = bbox_regression[0]
                 # print(f"Bbox Reg[0] Shape: {b0.shape}")

                 if b0.dim() == 2:
                      # If it is (Total, 4), then maybe it's a list containing the flattened result?
                      # Or maybe feature_maps was a single tensor?
                      flat_bbox_deltas = b0
                      flat_scores = pred_scores[0]
                 else:
                      # Standard list of (N, A*4, H, W)
                      all_bbox_regression = []
                      all_pred_scores = []
                      for i in range(len(bbox_regression)):
                           b = bbox_regression[i]
                           s = pred_scores[i]
                           N, Ax4, H, W = b.shape
                           A = Ax4 // 4
                           C = s.shape[1] // A
                           b = b.permute(0, 2, 3, 1).contiguous().view(N, -1, 4)
                           s = s.permute(0, 2, 3, 1).contiguous().view(N, -1, C)
                           all_bbox_regression.append(b)
                           all_pred_scores.append(s)
                      flat_bbox_deltas = torch.cat(all_bbox_regression, dim=1)
                      flat_scores = torch.cat(all_pred_scores, dim=1)
        else:
             raise ValueError("Unknown bbox_regression type")

        # Anchors
        # anchors is List[Tensor].
        flat_anchors = torch.stack(anchors, dim=0)

        return flat_bbox_deltas, flat_scores, flat_anchors

def create_model(num_classes):
    return ExportableSSDLite(num_classes)
