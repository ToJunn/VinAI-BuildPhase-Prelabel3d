import io
import json
import zipfile
import numpy as np
from .schemas import LABELS


def pcd(points):
    xyz = np.ascontiguousarray(points[:, :3], dtype='<f4')
    count = len(xyz)
    header = (f'# .PCD v0.7\nVERSION 0.7\nFIELDS x y z\nSIZE 4 4 4\nTYPE F F F\n'
              f'COUNT 1 1 1\nWIDTH {count}\nHEIGHT 1\nVIEWPOINT 0 0 0 1 0 0 0\nPOINTS {count}\nDATA binary\n')
    return header.encode('ascii') + xyz.tobytes()


def datumaro_item(index, prediction, threshold, classes):
    annotations = []
    for box in prediction['boxes']:
        if box['score'] < threshold or box['label'] not in classes:
            continue
        annotations.append({'id': len(annotations) + 1, 'type': 'cuboid_3d',
            'label_id': LABELS.index(box['label']), 'group': 0,
            'attributes': {'score': box['score']}, 'position': box['center'],
            'rotation': [0, 0, box['yaw_rad']], 'scale': box['size_lwh']})
    return {'id': f'{index:06d}', 'point_cloud': {'path': f'{index:06d}.pcd'}, 'annotations': annotations}


def write_export(directory, dataset, predictions, request, progress):
    directory.mkdir(parents=True, exist_ok=True)
    items, mapping = [], []
    with zipfile.ZipFile(directory / 'data.zip', 'w', zipfile.ZIP_DEFLATED) as data:
        for index, prediction in enumerate(predictions):
            token = prediction['sample_token']
            data.writestr(f'{index:06d}.pcd', pcd(dataset.points(token)))
            items.append(datumaro_item(index, prediction, request['threshold'], request['classes']))
            mapping.append({'export_index': index, 'sample_token': token, 'scene_frame_index': prediction['frame_index']})
            progress(index + 1)
    payload = {'info': {}, 'categories': {'label': {'labels': [
        {'name': label, 'parent': '', 'attributes': ['score']} for label in LABELS], 'attributes': []}}, 'items': items}
    with zipfile.ZipFile(directory / 'annotations.zip', 'w', zipfile.ZIP_DEFLATED) as annotations:
        annotations.writestr('annotations/default.json', json.dumps(payload, allow_nan=False))
    manifest = {'schema_version': '1.0', 'dataset_version': dataset.version,
        'scene_token': predictions[0]['scene_token'], 'job_id': request['job_id'],
        'model': predictions[0]['model'], 'selected_tokens': [p['sample_token'] for p in predictions],
        'threshold': request['threshold'], 'classes': request['classes'], 'mapping': mapping,
        'coordinate_frame': 'LIDAR_TOP', 'axis_convention': predictions[0]['axis_convention'],
        'origin': 'geometric_center', 'rotation': 'XYZ Euler radians; yaw around +Z',
        'format': 'Datumaro 3D 1.0', 'live_cvat_import_verified': False}
    (directory / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    with zipfile.ZipFile(directory / 'bundle.zip', 'w', zipfile.ZIP_STORED) as bundle:
        for name in ('data.zip', 'annotations.zip', 'manifest.json'):
            bundle.write(directory / name, name)
