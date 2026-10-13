import asyncio
import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import numpy as np
from .config import Settings, safe_path
from .dataset import NuScenes, CAMERAS
from .jobs import Jobs, redact
from .storage import Store, new_record, runtime_size
from .schemas import JobRequest, ExportRequest
from .exporter import write_export

logging.basicConfig(level=logging.INFO)


def create_app(settings=None):
    s = settings or Settings()
    tasks = set()
    export_lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(app):
        app.state.dataset = None
        app.state.dataset_error = None
        try:
            app.state.dataset = NuScenes(s.dataset_root, s.nuscenes_version)
        except (OSError, ValueError, KeyError) as exc:
            app.state.dataset_error = str(exc)
            logging.error('Dataset unavailable: %s', exc)
        app.state.store = Store(s.runtime_root)
        app.state.jobs = Jobs(s, app.state.dataset, app.state.store)
        await app.state.jobs.start()
        yield
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await app.state.jobs.stop()

    app = FastAPI(title='nuScenes Prelabel 3D', lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=[s.frontend_origin, s.frontend_origin.replace('localhost', '127.0.0.1')],
        allow_methods=['GET', 'POST'], allow_headers=['Content-Type'],
        expose_headers=['X-Point-Count', 'X-Full-Point-Count', 'X-Point-Format'])

    @app.exception_handler(KeyError)
    async def not_found(_, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={'detail': f'Unknown token or record: {exc}'})

    @app.exception_handler(FileNotFoundError)
    async def file_missing(_, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={'detail': str(exc)})

    @app.exception_handler(ValueError)
    async def invalid(_, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=400, content={'detail': str(exc)})

    def dataset():
        if not app.state.dataset:
            raise HTTPException(503, app.state.dataset_error)
        return app.state.dataset

    def quota(extra=0):
        used = runtime_size(s.runtime_root)
        if used + extra > s.runtime_quota_gb * 1024**3:
            raise ValueError('Runtime quota exceeded. Remove selected old outputs manually before retrying.')

    @app.get('/api/health')
    def health():
        return {'status': 'ok', 'dataset_available': app.state.dataset is not None,
                'dataset_error': app.state.dataset_error, 'model': app.state.jobs.model(), 'cvat_url': s.cvat_url,
                'default_score_threshold': s.default_score_threshold}

    @app.get('/api/dataset')
    def info():
        return {'root': str(s.dataset_root), 'version': s.nuscenes_version,
                'available': app.state.dataset is not None, 'error': app.state.dataset_error,
                'scene_count': len(app.state.dataset.frames) if app.state.dataset else 0}

    @app.get('/api/scenes')
    def scenes(offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100)):
        rows = list(dataset().tables['scene'].values())
        return {'items': rows[offset:offset+limit], 'total': len(rows)}

    @app.get('/api/scenes/{scene}/frames')
    def frames(scene: str):
        return dataset().frames[scene]

    @app.get('/api/frames/{token}')
    def frame(token: str):
        return dataset().frame(token)

    @app.get('/api/frames/{token}/points')
    def points(token: str):
        data = dataset().points(token)
        xyz = data[:, :3]
        if len(xyz) > s.preview_max_points:
            xyz = xyz[np.linspace(0, len(xyz)-1, s.preview_max_points, dtype=int)]
        return Response(np.ascontiguousarray(xyz, dtype='<f4').tobytes(), media_type='application/octet-stream',
            headers={'X-Point-Count': str(len(xyz)), 'X-Full-Point-Count': str(len(data)),
                     'X-Point-Format': 'float32-le xyz; LIDAR_TOP; meters; Z-up'})

    @app.get('/api/frames/{token}/camera/{channel}')
    def camera(token: str, channel: str):
        if channel not in CAMERAS:
            raise HTTPException(400, 'Unsupported camera channel')
        d = dataset()
        return FileResponse(d.file(d.data[token][channel]), media_type='image/jpeg')

    @app.get('/api/models')
    def models():
        return [app.state.jobs.model()]

    @app.post('/api/jobs', status_code=201)
    def submit(request: JobRequest):
        dataset()
        quota()
        payload = request.model_dump()
        if 'threshold' not in request.model_fields_set:
            payload['threshold'] = s.default_score_threshold
        return app.state.jobs.submit(payload)

    @app.get('/api/jobs')
    def jobs():
        return app.state.store.list()

    @app.get('/api/jobs/{id}')
    def job(id: str):
        return app.state.store.get(id)

    @app.post('/api/jobs/{id}/cancel')
    async def cancel(id: str):
        return await app.state.jobs.cancel(id)

    @app.post('/api/jobs/{id}/retry', status_code=201)
    def retry(id: str):
        dataset()
        quota()
        previous = app.state.store.get(id)
        if previous['status'] in ('queued', 'running'):
            raise HTTPException(409, 'Cancel or finish the existing job before retrying')
        return app.state.jobs.submit(previous['request'], id)

    @app.get('/api/jobs/{id}/predictions/{token}')
    def prediction(id: str, token: str):
        return app.state.jobs.prediction(id, token)

    def export_work(record, predictions):
        # Serialize exports to bound disk and memory usage.
        with export_lock:
            try:
                d = dataset()
                estimate = sum(d.file(d.data[p['sample_token']]['LIDAR_TOP']).stat().st_size for p in predictions) * 4
                quota(estimate)
                record.update(status='running')
                app.state.store.put(record, 'export')
                def progress(n):
                    record.update(processed=n)
                    app.state.store.put(record, 'export')
                write_export(s.runtime_root / 'exports' / record['id'], d, predictions, record['request'], progress)
                record.update(status='completed', download_url=f'/api/exports/{record["id"]}/download')
            except Exception as exc:
                record.update(status='failed', error=redact(str(exc)))
            app.state.store.put(record, 'export')

    @app.post('/api/exports', status_code=202)
    async def export(request: ExportRequest):
        dataset()
        job = app.state.store.get(request.job_id)
        if job['status'] not in ('completed', 'failed', 'cancelled'):
            raise HTTPException(409, 'Finish or cancel the job before exporting completed frames')
        tokens = dataset().select(job['request']['scene_token'], request.sample_tokens)
        if not set(tokens).issubset(job['request']['sample_tokens']):
            raise ValueError('Export tokens must belong to the job')
        predictions = [app.state.jobs.prediction(request.job_id, token) for token in tokens]
        if len({p['model']['checkpoint_sha256'] for p in predictions}) != 1:
            raise ValueError('Inconsistent model provenance')
        quota()
        payload = request.model_dump()
        payload['sample_tokens'] = tokens
        record = new_record(payload)
        app.state.store.put(record, 'export')
        task = asyncio.create_task(asyncio.to_thread(export_work, record, predictions))
        tasks.add(task)
        task.add_done_callback(tasks.discard)
        return record

    @app.get('/api/exports/{id}')
    def export_status(id: str):
        return app.state.store.get(id, 'export')

    @app.get('/api/exports/{id}/download')
    def download(id: str):
        record = app.state.store.get(id, 'export')
        if record['status'] != 'completed':
            raise HTTPException(409, 'Export is not ready')
        return FileResponse(safe_path(s.runtime_root, f'exports/{id}/bundle.zip'),
                            filename=f'cvat-{id}.zip', media_type='application/zip')

    return app


app = create_app()
