# Coordinates and data contract

## Correction to the task's sample schema

Raw nuScenes `LIDAR_TOP` sensor coordinates are X right, Y forward, Z up. The task's `x_forward_y_left_z_up` describes the ego/body convention and must not be attached to unrotated raw sensor points. This implementation preserves raw LiDAR coordinates throughout and explicitly declares `axis_convention=x_right_y_forward_z_up`. No arbitrary 90-degree visual rotation is applied.

Verify using sensor calibration in the local metadata and the [MMDetection3D coordinate guide](https://mmdetection3d.readthedocs.io/en/latest/user_guides/coord_sys_tutorial.html). The [nuScenes point-cloud loader](https://github.com/nutonomy/nuscenes-devkit/blob/master/python-sdk/nuscenes/utils/data_classes.py) reads five float32 values per LiDAR point and uses four internal channels; the fifth on-disk field is not XYZ/intensity. Here on-disk layout is `(x,y,z,intensity,ring)`; preview/export uses full-resolution XYZ except the explicitly downsampled browser preview.

Actual backend tests confirm every mini-dataset LIDAR_TOP calibration maps raw +X toward ego -Y (right), raw +Y toward ego +X (forward), and raw +Z toward ego +Z (up). `scripts/validate_model_geometry.py` independently verifies the installed MMDet3D box center/dimensions/corner rotation conventions at five yaw angles.

## Cuboids

- Units: meters. Center is geometric center. Sizes are `[length,width,height]` along the box's local X,Y,Z axes.
- Yaw is counterclockwise about +Z, radians in `[-pi,pi)`, measured from local +X. Direction arrows come from model yaw, not the symmetry of an unmarked cuboid.
- MMDet3D output uses `LiDARInstance3DBoxes`; read `gravity_center`, `dims`, and `yaw` properties to convert bottom-origin output safely. Dimensions represent local X/Y/Z extent in the registered 1.4.0 API. See [LiDAR box implementation](https://github.com/open-mmlab/mmdetection3d/blob/v1.4.0/mmdet3d/structures/bbox_3d/lidar_box3d.py).
- Three.js camera has `up=(0,0,1)`; all points, boxes and arrows stay in raw XYZ. Box rotation is around Z. Grid is rotated onto XY.
- Per-frame IDs do not imply tracking. Ground truth is not shown or exported as prediction.

## Calibration and sweeps

For a sample_data sensor: `T_global_sensor = T_global_ego(timestamp) @ T_ego_sensor`. To align an earlier sweep: `T_current_sweep = inverse(T_global_current) @ T_global_sweep`. Ego poses belong to each sensor timestamp, not the sample timestamp. Camera projection metadata uses `inverse(T_global_camera) @ T_global_lidar` plus that camera's intrinsic matrix; overlay is not implemented.

The registered PointPillars config requests up to 10 previous sweeps plus current LiDAR. Source defaults use `pad_empty_sweeps=False`, `remove_close=False`; early frames contain only available sweeps. Ring is replaced by lag in seconds, and features are selected `[x,y,z,lag]`, matching `[0,1,2,4]`. Current lag is zero. No preview downsampling is used.

Schema validates finite coordinates, strictly positive dimensions, supported detection labels, score [0,1], and checkpoint SHA256. Export items are ordered in scene time and remapped to `000000`, `000001`, … independently of source scene frame index.
