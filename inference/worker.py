import hashlib
import json
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'backend'))
from app.dataset import NuScenes
from app.schemas import Prediction
from app.storage import atomic_json, runtime_size


def run(manifest):
    if manifest.get('wsl_process_group'):
        import os
        if os.getpgrp() != os.getpid():
            os.setsid()
        (Path(manifest['runtime_root']) / 'jobs' / manifest['job_id'] / 'worker.pid').write_text(str(os.getpid()))
    cancel_flag = Path(manifest['runtime_root']) / 'jobs' / manifest['job_id'] / 'cancel.flag'
    if cancel_flag.exists():
        return
    from adapters.pointpillars import PointPillars
    import torch
    root = Path(manifest['runtime_root'])
    job = manifest['job_id']
    progress_path = root / 'jobs' / job / 'progress.json'
    started = time.monotonic()
    def progress(n, token, message):
        atomic_json(progress_path, {'processed': n, 'current_sample': token,
            'message': message, 'elapsed': time.monotonic() - started})
    progress(0, None, 'Loading checkpoint')
    checkpoint = Path(manifest['checkpoint'])
    with checkpoint.open('rb') as file:
        hasher = hashlib.sha256()
        for chunk in iter(lambda: file.read(1024**2), b''):
            hasher.update(chunk)
        digest = hasher.hexdigest()
    model_metadata = {'model': manifest['model'], 'checkpoint_sha256': digest,
                      'torch': torch.__version__, 'cuda': torch.version.cuda}
    atomic_json(root / 'jobs' / job / 'model.json', model_metadata)
    print(json.dumps(model_metadata), flush=True)
    adapter = PointPillars(manifest['config'], str(checkpoint), manifest['device'])
    data = NuScenes(Path(manifest['dataset_root']), manifest['version'])
    tokens = data.select(manifest['scene_token'], manifest['sample_tokens'])
    for index, token in enumerate(tokens):
        if cancel_flag.exists():
            return
        if runtime_size(root) > manifest['runtime_quota_bytes']:
            raise RuntimeError('Runtime disk quota exceeded')
        progress(index, token, 'Running inference')
        frame = data.frame(token)
        boxes = adapter.predict(data.model_points(token), manifest['threshold'])
        if cancel_flag.exists():
            return
        prediction = Prediction(job_id=job, scene_token=manifest['scene_token'],
            sample_token=token, lidar_sample_data_token=frame['lidar_sample_data_token'],
            frame_index=frame['frame_index'], timestamp_us=frame['timestamp_us'],
            model={'name': manifest['model'], 'checkpoint_sha256': digest}, boxes=boxes)
        atomic_json(root / 'predictions' / job / f'{token}.json', prediction.model_dump(mode='json'))
        if index == 0:
            evidence = {key: manifest[key] for key in ('config', 'checkpoint', 'device')}
            for key, source in [('config_stat', manifest['config']), ('checkpoint_stat', manifest['checkpoint'])]:
                stat = Path(source).stat()
                evidence[key] = {'size': stat.st_size, 'mtime': stat.st_mtime}
            evidence.update(checkpoint_sha256=digest, job_id=job, sample_token=token)
            atomic_json(root / 'model_verification.json', evidence)
        progress(index + 1, token, 'Frame completed')
        metrics = {'sample': token, 'boxes': len(boxes), 'elapsed': time.monotonic()-started,
            'peak_vram_bytes': torch.cuda.max_memory_allocated() if torch.cuda.is_available() else 0}
        with (root / 'jobs' / job / 'metrics.jsonl').open('a', encoding='utf-8') as log:
            log.write(json.dumps(metrics) + '\n')
        print(json.dumps(metrics), flush=True)


if __name__ == '__main__':
    run(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')))
