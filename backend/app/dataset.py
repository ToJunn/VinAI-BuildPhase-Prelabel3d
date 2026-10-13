import json
from pathlib import Path
import numpy as np
from .config import safe_path

CAMERAS = ('CAM_FRONT', 'CAM_FRONT_LEFT', 'CAM_FRONT_RIGHT', 'CAM_BACK',
           'CAM_BACK_LEFT', 'CAM_BACK_RIGHT')


def rotation(q):
    q = np.asarray(q, dtype=float)
    q /= np.linalg.norm(q)
    w, x, y, z = q
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                     [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])


def transform(record):
    result = np.eye(4)
    result[:3, :3] = rotation(record['rotation'])
    result[:3, 3] = record['translation']
    return result


def read_lidar(path):
    if path.stat().st_size % 20:
        raise ValueError('nuScenes LiDAR file must have 5 float32 values per point')
    points = np.fromfile(path, dtype='<f4').reshape(-1, 5)
    if not len(points) or not np.isfinite(points).all():
        raise ValueError('Empty or nonfinite LiDAR data')
    return points


class NuScenes:
    def __init__(self, root: Path, version: str):
        self.root, self.version = root.resolve(), version
        self.tables = {}
        for name in ('scene', 'sample', 'sample_data', 'calibrated_sensor', 'ego_pose', 'sensor'):
            file = safe_path(self.root, f'{version}/{name}.json')
            rows = json.loads(file.read_text(encoding='utf-8'))
            self.tables[name] = {r['token']: r for r in rows}
        self.data = {}
        for row in self.tables['sample_data'].values():
            if row['is_key_frame']:
                channel = self.channel(row)
                self.data.setdefault(row['sample_token'], {})[channel] = row
        self.frames = {}
        self.indices = {}
        for scene in self.tables['scene'].values():
            ordered, visited, token, last = [], set(), scene['first_sample_token'], -1
            while token:
                if token in visited:
                    raise ValueError('Cycle in sample.next')
                sample = self.tables['sample'][token]
                if sample['scene_token'] != scene['token'] or sample['timestamp'] <= last:
                    raise ValueError('Invalid scene membership or timestamp ordering')
                visited.add(token)
                self.indices[token] = len(ordered)
                ordered.append({'sample_token': token, 'frame_index': len(ordered), 'timestamp_us': sample['timestamp']})
                last, token = sample['timestamp'], sample['next']
            if len(ordered) != scene['nbr_samples'] or ordered[-1]['sample_token'] != scene['last_sample_token']:
                raise ValueError('Scene traversal does not match metadata')
            self.frames[scene['token']] = ordered

    def channel(self, row):
        cs = self.tables['calibrated_sensor'][row['calibrated_sensor_token']]
        return self.tables['sensor'][cs['sensor_token']]['channel']

    def file(self, row):
        path = safe_path(self.root, row['filename'])
        if not path.is_file():
            raise FileNotFoundError(f'Dataset file missing: {row["filename"]}')
        return path

    def sensor_to_global(self, row):
        return transform(self.tables['ego_pose'][row['ego_pose_token']]) @ transform(
            self.tables['calibrated_sensor'][row['calibrated_sensor_token']])

    def frame(self, token):
        sample = self.tables['sample'][token]
        sensors = self.data[token]
        lidar = sensors['LIDAR_TOP']
        cameras = {}
        for channel in CAMERAS:
            if channel in sensors:
                row = sensors[channel]
                cs = self.tables['calibrated_sensor'][row['calibrated_sensor_token']]
                cameras[channel] = {'sample_data_token': row['token'], 'timestamp_us': row['timestamp'],
                    'width': row['width'], 'height': row['height'], 'intrinsic': cs['camera_intrinsic'],
                    'lidar_to_camera': (np.linalg.inv(self.sensor_to_global(row)) @ self.sensor_to_global(lidar)).tolist()}
        return {'sample_token': token, 'scene_token': sample['scene_token'],
                'frame_index': self.indices[token], 'timestamp_us': sample['timestamp'],
                'lidar_sample_data_token': lidar['token'], 'cameras': cameras}

    def points(self, token):
        return read_lidar(self.file(self.data[token]['LIDAR_TOP']))

    def select(self, scene, tokens):
        frames = self.frames[scene]
        if len(tokens) != len(set(tokens)) or not tokens:
            raise ValueError('Frame selection must be nonempty and unique')
        wanted = set(tokens)
        if not wanted.issubset({f['sample_token'] for f in frames}):
            raise ValueError('Sample token does not belong to this scene')
        return [f['sample_token'] for f in frames if f['sample_token'] in wanted]

    def model_points(self, token, sweeps=10):
        current = self.data[token]['LIDAR_TOP']
        base = self.points(token)[:, :4].copy()
        # Registered config: remove_close=False, pad_empty_sweeps=False, seconds lag.
        base = np.column_stack((base, np.zeros(len(base), dtype=np.float32)))
        chunks = [base]
        row = current
        for _ in range(sweeps):
            if not row['prev']:
                break
            row = self.tables['sample_data'][row['prev']]
            raw = read_lidar(self.file(row))[:, :4].copy()
            matrix = np.linalg.inv(self.sensor_to_global(current)) @ self.sensor_to_global(row)
            raw[:, :3] = raw[:, :3] @ matrix[:3, :3].T + matrix[:3, 3]
            lag = (current['timestamp'] - row['timestamp']) / 1e6
            chunks.append(np.column_stack((raw, np.full(len(raw), lag, dtype=np.float32))))
        return np.concatenate(chunks).astype('<f4')
