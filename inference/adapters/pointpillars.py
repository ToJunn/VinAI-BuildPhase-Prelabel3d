import math
import numpy as np
from model_adapter import ModelAdapter


class PointPillars(ModelAdapter):
    def __init__(self, config, checkpoint, device):
        import torch
        from mmdet3d.apis import init_model
        from mmengine.config import Config
        cfg = Config.fromfile(config)
        pipeline = cfg.test_dataloader.dataset.pipeline
        loads = [p for p in pipeline if p['type'] == 'LoadPointsFromMultiSweeps']
        if len(loads) != 1 or loads[0].get('sweeps_num') != 10:
            raise ValueError('Only the registered PointPillars nuScenes 10 previous sweeps config is supported')
        if loads[0].get('remove_close', False) or loads[0].get('pad_empty_sweeps', False):
            raise ValueError('Unexpected sweep preprocessing; use the registered upstream config')
        if 'pointpillars' not in str(config).lower():
            raise ValueError('Expected the registered PointPillars config')
        self.model = init_model(cfg, checkpoint, device=device)
        self.model.eval()
        self.classes = list(cfg.class_names)
        checkpoint_classes = list(self.model.dataset_meta.get('classes', self.classes))
        if checkpoint_classes != self.classes:
            raise ValueError('Checkpoint class order does not match the registered model config')
        self.torch = torch
        self.device = device

    def predict(self, points, threshold):
        from mmdet3d.structures import Det3DDataSample
        torch = self.torch
        # Match LoadPointsFromFile + LoadPointsFromMultiSweeps use_dim=[0,1,2,4].
        features = np.ascontiguousarray(points[:, [0, 1, 2, 4]])
        sample = Det3DDataSample()
        from mmdet3d.structures import LiDARInstance3DBoxes
        sample.set_metainfo({'box_type_3d': LiDARInstance3DBoxes})
        with torch.no_grad():
            result = self.model.test_step({'inputs': {'points': [torch.from_numpy(features)]},
                                           'data_samples': [sample]})[0].pred_instances_3d
        boxes = result.bboxes_3d
        centers = boxes.gravity_center.detach().cpu().numpy()
        sizes = boxes.dims.detach().cpu().numpy()
        yaws = boxes.yaw.detach().cpu().numpy()
        scores = result.scores_3d.detach().cpu().numpy()
        labels = result.labels_3d.detach().cpu().numpy()
        return [{'id': str(i), 'label': self.classes[int(labels[i])], 'score': float(score),
                 'center': centers[i].tolist(), 'size_lwh': sizes[i].tolist(),
                 'yaw_rad': float((yaws[i] + math.pi) % (2 * math.pi) - math.pi)}
                for i, score in enumerate(scores) if score >= threshold]
