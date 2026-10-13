# nuScenes Prelabel 3D

Local React/Three.js frontend + FastAPI backend for browsing real nuScenes LiDAR and camera frames, scheduling isolated 3D inference workers, and preparing CVAT exports.

Source lives in `D:/build-phase/nuscenes`; the original dataset lives in its nested `v1.0-mini/` directory and is read-only. No dataset copies are made.

## Start on Windows

Dependencies and actual env files have been created in `backend/.venv`, `backend/.env`, `frontend/node_modules`, and `frontend/.env`. To recreate them:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
```

Open two terminals:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_backend.ps1
powershell -ExecutionPolicy Bypass -File scripts/start_frontend.ps1
```

Frontend: <http://127.0.0.1:5173>. API docs: <http://127.0.0.1:8000/docs>.

## Workflow

1. Open Dataset and choose a scene. Workspace displays real LiDAR and one of six cameras.
2. Configure the inference interpreter/config/checkpoint in `backend/.env` following [MODEL_RUNTIME.md](docs/MODEL_RUNTIME.md), then restart the backend. Dataset browsing does not require a model.
3. Select a frame range (zero-based indices) and the inference score floor, then Run Prelabel. Jobs shows progress, errors, cancel and retry.
4. Choose a prediction job, browse frames, click boxes and filter classes/scores. A view threshold cannot recover boxes omitted by the inference score floor.
5. Export the selected range. Failed/cancelled jobs may export only explicitly selected frames with completed output files. The bundle contains separate `data.zip`, `annotations.zip`, and provenance manifest. Follow [CVAT_IMPORT.md](docs/CVAT_IMPORT.md).

Model and live CVAT verification status is recorded in [VALIDATION.md](docs/VALIDATION.md); test fixtures are never served as model results. See [SETUP.md](docs/SETUP.md) for environment details and [COORDINATES.md](docs/COORDINATES.md) for the corrected raw LiDAR convention.

## Checks

```powershell
backend/.venv/Scripts/python.exe -m pytest backend/tests -q
cd frontend
npm.cmd run build
npm.cmd audit --cache .npm-cache
```

Real model smoke check, from project root:

```powershell
backend/.venv/Scripts/python.exe scripts/smoke_pipeline.py
```

Real scene/API/export/cancel integration check while the backend is running:

```powershell
backend/.venv/Scripts/python.exe scripts/validate_live_api.py
```

Actual validation completed a 39-frame scene with 1,412 boxes and downloaded its export. Live CVAT import and interactive viewer QA are still pending; see VALIDATION.md.

The API never downloads a checkpoint or imports PyTorch on startup. Outputs are under `runtime/`, checkpoints under `models/`; both are ignored by Git. Runtime disk quota defaults to 10 GiB. Preview points are bounded and are not used for inference/export. To free space, stop the app and explicitly remove selected old job/prediction/export directories; do not delete dataset files.
