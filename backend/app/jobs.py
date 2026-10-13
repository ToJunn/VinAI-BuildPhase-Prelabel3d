import asyncio
import contextlib
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from .config import PROJECT, safe_path
from .schemas import Prediction
from .storage import atomic_json, new_record
from .wsl import to_wsl, to_windows


def redact(text):
    text = re.sub(r'(?i)(token|password|secret|api_key)\s*[=:]\s*\S+', r'\1=[REDACTED]', text)
    return re.sub(r'(?i)(https?://)[^\s/@]+:[^\s/@]+@', r'\1[REDACTED]@', text)[-6000:]


class Jobs:
    def __init__(self, settings, dataset, store):
        self.settings, self.dataset, self.store = settings, dataset, store
        self.process = None
        self.active = None
        self.task = None
        self._interpreter_probe = None

    def model(self):
        s = self.settings
        errors = []
        for name, value in [('INFERENCE_PYTHON', s.inference_python), ('MODEL_CONFIG', s.model_config_path),
                            ('MODEL_CHECKPOINT', s.model_checkpoint)]:
            candidate = Path(value)
            if value and name == 'INFERENCE_PYTHON' and s.inference_wsl_distro and value.startswith('/mnt/'):
                candidate = to_windows(value)
            exists = candidate.is_file()
            if s.inference_wsl_distro and name == 'INFERENCE_PYTHON' and value:
                # Native Linux interpreters and Linux symlinks need a WSL-side check.
                probe_key = (s.inference_wsl_distro, value)
                if not self._interpreter_probe or self._interpreter_probe[0] != probe_key or time.monotonic()-self._interpreter_probe[1]>30:
                    try:
                        result = subprocess.run(['wsl.exe', '-d', s.inference_wsl_distro, '--', 'test', '-x', value], timeout=10, capture_output=True)
                        exists = result.returncode == 0
                    except (OSError, subprocess.TimeoutExpired):
                        exists = False
                    self._interpreter_probe = (probe_key, time.monotonic(), exists)
                else:
                    exists = self._interpreter_probe[2]
            if not value or not exists:
                errors.append(f'{name}: configure an existing file in backend/.env')
        verified = False
        marker = s.runtime_root / 'model_verification.json'
        if not errors and marker.is_file():
            import json
            try:
                evidence = json.loads(marker.read_text(encoding='utf-8'))
                config = to_wsl(s.model_config_path) if s.inference_wsl_distro else str(Path(s.model_config_path).resolve())
                checkpoint = to_wsl(s.model_checkpoint) if s.inference_wsl_distro else str(Path(s.model_checkpoint).resolve())
                verified = evidence['config'] == config and evidence['checkpoint'] == checkpoint and evidence['device'] == s.device
                for key, path in [('config_stat', s.model_config_path), ('checkpoint_stat', s.model_checkpoint)]:
                    stat = Path(path).stat()
                    verified = verified and evidence[key]['size'] == stat.st_size and abs(evidence[key]['mtime'] - stat.st_mtime) < .001
            except (OSError, ValueError, KeyError):
                verified = False
        return {'id': 'pointpillars-nuscenes', 'name': 'PointPillars / nuScenes / 10 previous sweeps',
                'available': not errors, 'errors': errors, 'device': s.device,
                'runtime_verified': verified}

    def submit(self, request, parent=None):
        model = self.model()
        if not model['available']:
            raise ValueError('; '.join(model['errors']))
        request['sample_tokens'] = self.dataset.select(request['scene_token'], request['sample_tokens'])
        record = new_record(request, parent)
        s = self.settings
        manifest = {**request, 'job_id': record['id'], 'dataset_root': str(s.dataset_root),
                    'version': s.nuscenes_version, 'runtime_root': str(s.runtime_root),
                    'config': str(Path(s.model_config_path).resolve()),
                    'checkpoint': str(Path(s.model_checkpoint).resolve()), 'device': s.device,
                    'runtime_quota_bytes': int(s.runtime_quota_gb * 1024**3)}
        if s.inference_wsl_distro:
            for key in ('dataset_root', 'runtime_root', 'config', 'checkpoint'):
                manifest[key] = to_wsl(manifest[key])
            manifest['wsl_process_group'] = True
            probe = subprocess.run(['wsl.exe', '-d', s.inference_wsl_distro, '--',
                s.inference_python, '-c', 'from pathlib import Path; import sys; p=Path(sys.argv[1]); p.write_text("mount-ok"); print(p.read_text())',
                to_wsl(s.runtime_root / 'mount-probe.txt')], capture_output=True, text=True, timeout=30)
            if probe.returncode or 'mount-ok' not in probe.stdout:
                raise ValueError(f'WSL interpreter/mount probe failed: {redact(probe.stderr)}')
            if (s.runtime_root / 'mount-probe.txt').read_text() != 'mount-ok':
                raise ValueError('API and worker cannot share the runtime mount')
        atomic_json(s.runtime_root / 'jobs' / record['id'] / 'request.json', manifest)
        return self.store.put(record)

    async def start(self):
        for kind in ('job', 'export'):
            for record in self.store.list(kind):
                if record['status'] == 'running' or (kind == 'export' and record['status'] == 'queued'):
                    record.update(status='failed', error='API restarted; worker no longer available. Retry as a new job.')
                    self.store.put(record, kind)
        self.task = asyncio.create_task(self.loop())

    async def stop(self):
        if self.active:
            await self.cancel(self.active)
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    async def kill(self):
        process = self.process
        if process and process.returncode is None:
            if self.settings.inference_wsl_distro and self.active:
                pid_file = self.settings.runtime_root / 'jobs' / self.active / 'worker.pid'
                if pid_file.exists():
                    pid = int(pid_file.read_text().strip())
                    if pid > 1:
                        killer = await asyncio.create_subprocess_exec('wsl.exe', '-d', self.settings.inference_wsl_distro,
                            '--', '/bin/kill', '-KILL', '--', f'-{pid}',
                            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
                        await killer.wait()
            if os.name == 'nt':
                killer = await asyncio.create_subprocess_exec('taskkill', '/PID', str(process.pid), '/T', '/F',
                    stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
                await killer.wait()
            else:
                import signal
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    await asyncio.wait_for(process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    os.killpg(process.pid, signal.SIGKILL)
            if process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
            await process.wait()

    async def cancel(self, id):
        record = self.store.get(id)
        if record['status'] in ('queued', 'running'):
            progress = self.settings.runtime_root / 'jobs' / id / 'progress.json'
            if progress.exists():
                import json
                latest = json.loads(progress.read_text(encoding='utf-8'))
                record['processed'] = min(record['total'], int(latest.get('processed', record['processed'])))
            (self.settings.runtime_root / 'jobs' / id).mkdir(parents=True, exist_ok=True)
            (self.settings.runtime_root / 'jobs' / id / 'cancel.flag').touch()
            record.update(status='cancelled', message='Cancelled; completed frame outputs retained')
            self.store.put(record)
            if id == self.active:
                await self.kill()
        return self.store.get(id)

    def prediction(self, id, token):
        record = self.store.get(id)
        if token not in record['request']['sample_tokens']:
            raise ValueError('Frame is not part of the selected job')
        path = safe_path(self.settings.runtime_root, f'predictions/{id}/{token}.json')
        result = Prediction.model_validate_json(path.read_text(encoding='utf-8'))
        if result.job_id != id or result.sample_token != token or result.scene_token != record['request']['scene_token']:
            raise ValueError('Prediction provenance mismatch')
        return result.model_dump(mode='json')

    async def loop(self):
        while True:
            queued = [j for j in self.store.list() if j['status'] == 'queued']
            if not queued:
                await asyncio.sleep(.4)
                continue
            record = queued[-1]
            id = record['id']
            self.active = id
            root = self.settings.runtime_root / 'jobs' / id
            capture_task = None
            started = time.monotonic()
            record.update(status='running', message='Starting model worker')
            self.store.put(record)
            try:
                with (root / 'log.txt').open('wb') as log:
                    opts = {'start_new_session': True} if os.name != 'nt' else {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
                    command = [self.settings.inference_python, str(PROJECT / 'inference/worker.py'), str(root / 'request.json')]
                    if self.settings.inference_wsl_distro:
                        command = ['wsl.exe', '-d', self.settings.inference_wsl_distro, '--',
                            self.settings.inference_python, to_wsl(PROJECT / 'inference/worker.py'), to_wsl(root / 'request.json')]
                    self.process = await asyncio.create_subprocess_exec(*command,
                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, cwd=str(PROJECT), **opts)
                    stream = self.process.stdout
                    async def capture_output():
                        while chunk := await stream.read(4096):
                            log.write(chunk)
                            log.flush()
                    capture_task = asyncio.create_task(capture_output())
                    if self.store.get(id)['status'] == 'cancelled':
                        await self.kill()
                    while self.process.returncode is None:
                        await asyncio.sleep(.4)
                        record = self.store.get(id)
                        if record['status'] == 'cancelled':
                            break
                        progress = root / 'progress.json'
                        if progress.exists():
                            import json
                            data = json.loads(progress.read_text(encoding='utf-8'))
                            for key in ('processed', 'current_sample', 'message'):
                                record[key] = data.get(key, record[key])
                        record['elapsed'] = round(time.monotonic() - started, 2)
                        self.store.put(record)
                    await self.process.wait()
                    await capture_task
                record = self.store.get(id)
                if record['status'] != 'cancelled':
                    if self.process.returncode:
                        record.update(status='failed', error=redact((root / 'log.txt').read_text(encoding='utf-8', errors='replace')))
                    else:
                        for token in record['request']['sample_tokens']:
                            self.prediction(id, token)
                        record.update(status='completed', processed=record['total'], message='Inference completed')
                    self.store.put(record)
            except Exception as exc:
                await self.kill()
                record = self.store.get(id)
                if record['status'] != 'cancelled':
                    record.update(status='failed', error=redact(str(exc)))
                    self.store.put(record)
            finally:
                if capture_task:
                    if not capture_task.done():
                        capture_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError, ValueError, OSError):
                        await capture_task
                self.active, self.process = None, None
