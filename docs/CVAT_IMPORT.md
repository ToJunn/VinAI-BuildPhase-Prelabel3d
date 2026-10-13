# CVAT export/import

The local endpoint `http://localhost:8080/api/server/about` timed out during inspection. Installed CVAT version and a live import therefore remain unverified. No task was created in CVAT. The exporter targets the upstream `Datumaro 3D 1.0` handler, not the application's canonical prediction JSON.

Sources inspected:

- [CVAT Datumaro handler](https://github.com/cvat-ai/cvat/blob/develop/cvat/apps/dataset_manager/formats/datumaro.py): dimension-specific Datumaro 3D 1.0 import/export.
- [Datumaro exporter](https://github.com/cvat-ai/datumaro/blob/develop/src/datumaro/plugins/data_formats/datumaro/exporter.py): cuboid fields `position`, `rotation`, `scale`, category label indices, item point-cloud paths.
- [CVAT 3D annotation documentation](https://docs.cvat.ai/docs/manual/basics/3d-object-annotation/).

## Package

Download `bundle.zip` then extract it locally:

- `data.zip`: only zero-padded PCD files, with a PCD 0.7 binary header and little-endian float32 XYZ. Full LiDAR resolution.
- `annotations.zip`: only `annotations/default.json`, containing Datumaro `cuboid_3d` annotations, label categories and matching item IDs. Position is geometric center, rotation `[0,0,yaw]` in radians and scale `[length,width,height]`.
- `manifest.json`: dataset version, source scene, selected tokens, original/export indices, thresholds, selected labels, model hash and coordinate conventions. This is separate from annotation parser input.

## Manual workflow pending live validation

1. Inspect your CVAT version and confirm `Datumaro 3D 1.0` appears in the import formats for a point-cloud task.
2. Create a 3D task with nuScenes detection class names. Upload `data.zip` as task media.
3. Import `annotations.zip` using **Datumaro 3D 1.0**. Do not upload the outer bundle as annotation input.
4. Compare frame 0 point cloud, center, length/width/height, and yaw visually. Check subset frame mapping against manifest.
5. Export a sample annotation back from that CVAT version and compare the fields. Record version, task ID and results in VALIDATION.md before claiming live compatibility.

The web UI explicitly marks live import as unverified. Tests use synthetic box fixtures only to validate serialization/filtering/mapping; those fixtures never become production model output.
