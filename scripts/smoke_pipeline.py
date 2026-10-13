"""Run one real frame using configured inference interpreter; no mock fallback."""
import json
import subprocess
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.config import Settings, PROJECT
from app.dataset import NuScenes
from app.jobs import Jobs, redact
from app.schemas import JobRequest
from app.storage import Store
from app.wsl import to_wsl

s = Settings()
d = NuScenes(s.dataset_root, s.nuscenes_version)
store = Store(s.runtime_root)
jobs = Jobs(s, d, store)
scene = next(iter(d.frames))
record = jobs.submit(JobRequest(scene_token=scene, sample_tokens=[d.frames[scene][0]['sample_token']],
                                threshold=s.default_score_threshold).model_dump())
record.update(status='running')
store.put(record)
started = time.monotonic()
log_path = s.runtime_root / 'jobs' / record['id'] / 'log.txt'
try:
    command = [s.inference_python, str(PROJECT / 'inference/worker.py'),
               str(s.runtime_root / 'jobs' / record['id'] / 'request.json')]
    if s.inference_wsl_distro:
        command = ['wsl.exe', '-d', s.inference_wsl_distro, '--', s.inference_python,
                   to_wsl(PROJECT / 'inference/worker.py'), to_wsl(s.runtime_root / 'jobs' / record['id'] / 'request.json')]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            encoding='utf-8', errors='replace')
    log_path.write_text(result.stdout, encoding='utf-8')
    result.check_returncode()
    print(log_path.read_text(encoding='utf-8'))
    prediction = jobs.prediction(record['id'], record['request']['sample_tokens'][0])
    record.update(status='completed', processed=1, elapsed=time.monotonic()-started,
                  current_sample=prediction['sample_token'], message='Real model smoke completed')
    print(json.dumps({'job_id': record['id'], 'boxes': len(prediction['boxes'])}))
except Exception as exc:
    error = log_path.read_text(encoding='utf-8') if log_path.exists() else str(exc)
    print(error)
    record.update(status='failed', error=redact(error), elapsed=time.monotonic()-started)
    raise
finally:
    store.put(record)
