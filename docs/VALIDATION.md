# Validation evidence — 2026-10-12 (Asia/Saigon)

## Executed

| Command/check | Actual result |
|---|---|
| `backend/.venv/Scripts/python.exe scripts/validate_dataset.py` | 10 scenes, 404 keyframes, 2,424 JPEG camera images, 14,026,208 LiDAR points. All keyframe LiDAR files read and validated, all camera paths/headers checked. |
| `backend/.venv/Scripts/python.exe -m pytest backend/tests -q` | 8 passed. One upstream Starlette/AnyIO deprecation warning. Covers real metadata/order/XYZ binary, finite boxes/yaw/size, calibration/sweep alignment, path containment, API input errors, job fail/cancel/retry/restart, Windows process-tree cancellation, export subset/threshold/PCD payload, async download, Windows↔WSL path mapping. |
| `backend/.venv/Scripts/python.exe -m compileall -q backend/app inference scripts` | Pass. |
| `npm.cmd run build` in frontend | TypeScript strict check + Vite production build pass. Viewer lazy-loaded; split chunks under 500 kB after optimization. |
| `npm.cmd audit --cache .npm-cache` | 0 vulnerabilities after updating Vite to 6.4.4. |
| HTTP `/api/health` at 127.0.0.1:8000 | API ok, real dataset available; no model import at startup. |
| HTTP frontend at 127.0.0.1:5173 | 200. |
| `scripts/download_checkpoint.py` | 19,778,089-byte official PointPillars checkpoint downloaded. SHA256 `f19d00a38e6b775f38a45a9a3ca3ecaec20a5585a3caf44622423e2d5f75d5d0`, official hash prefix verified. |
| Ubuntu WSL2 GPU/mount survey | RTX 4050 visible; dataset metadata readable through `/mnt/d`. Python 3.10.20 installed in project-managed Linux directory, inference env created. |
| `wsl -d Ubuntu -- bash .../scripts/setup_inference.sh` | CUDA torch 2.1.0+cu118, compiled MMCV 2.1.0 ops and mmdet3d 1.4.0 imported successfully; GPU accessible. Exact 134-package runtime recorded in `inference/requirements.verified.txt`. |
| `backend/.venv/Scripts/python.exe scripts/smoke_pipeline.py` | Real frame `ca9a282c9e77460f8360f564131a8af5`, 18 canonical boxes at 0.3 score floor. First successful smoke: 10.606 seconds worker elapsed, 601,026,560 bytes peak allocated VRAM (~573 MiB). Recheck after validating checkpoint/config class order: 10.934 seconds, same box count and VRAM. |
| `backend/.venv/Scripts/python.exe scripts/validate_live_api.py` | Full real scene `scene-0061`: 39 completed frames, 1,412 valid boxes. Observed queued→running→completed; health stayed responsive during inference. API elapsed 82.27 seconds; worker elapsed 73.040 seconds; peak allocated VRAM 2,076,418,048 bytes (~1.934 GiB). |
| Full-scene async export/download | Completed export `43dd17618d4a40be9d8902d96171701c`; bundle 13,825,954 bytes downloaded via HTTP, containing 39 PCDs/annotation items plus provenance. |
| Real WSL cancellation | Cancelled job `05ada5e7e4d646cb9d811c25074fe2f4`; Linux process group no longer existed after cancel returned. |
| `scripts/validate_live_api.py --frames 1` after final logging changes | GPU job `adc00a4c221f4fffb69b808e0a9e2efd` completed, 18 boxes, valid merged log and export download. A second full-scene job was cancelled after one frame: process group terminated, completed prediction remained readable, and no new output appeared after cancellation returned. Evidence: `runtime/live_validation_1frames.json`. |
| `validate_model_geometry.py` in the actual inference interpreter | MMDet3D bottom center `(1,2,0)` with height 2 maps to geometric center `(1,2,1)`; LWH `(4,2,2)` and corners match independent +Z rotation for yaw 0, ±pi/2, pi and 0.3. Backend tests also confirm raw LiDAR axes against every LIDAR_TOP calibration in the real mini dataset. |

## Runtime / integration

The first CUDA PyTorch install failed renaming its unpacked cache directory on `/mnt/d` with `Permission denied (os error 13)`. Setup was corrected to use `/tmp/nuscenes-prelabel-uv-cache` on Linux. Installing into the mounted Windows env then stalled in a Plan9 filesystem RPC; its installer was stopped. A persistent Ubuntu env at `/home/msi/.local/share/nuscenes-prelabel/inference-env` successfully installed the full runtime and ran GPU inference. Only the failed generated NTFS cache/env were cleaned up afterwards; source, dataset, checkpoint and active environments were preserved.

The initial smoke run correctly failed preflight for missing INFERENCE_PYTHON/MODEL_CONFIG/MODEL_CHECKPOINT; it did not fabricate boxes. Tests use clearly named synthetic box/process fixtures in temporary directories only, never runtime production predictions.

Real full-scene evidence: `runtime/live_validation.json`; per-frame canonical files: `runtime/predictions/5901029b7ac6455389fbed9e7f620162/`; worker model/progress/metrics: `runtime/jobs/5901029b7ac6455389fbed9e7f620162/`. Structured model metadata and `metrics.jsonl` avoid WSL stdout/stderr file-offset overlap. API logging now merges output through a pipe and writes the log from one reader.

Upstream runtime warnings include CuDNN's nvrtc workaround, a future meshgrid indexing change, and anchor-head direction-offset deprecation. They did not stop either smoke or full-scene inference. No OOM or silent precision/preprocessing reduction occurred.

## Not yet verified

- Live CVAT at localhost:8080 timed out; no version, sample export, actual import or geometric round-trip evidence. Export packaging follows upstream CVAT/Datumaro source but cannot be declared verified for an unknown installed version.
- Browser tooling reported no available apps/browsers. Frontend compiles and serves; UI clicks, screenshot/layout QA, LiDAR/cuboid visual alignment, and continuous-frame GPU memory observation have not been executed.
- Camera projection overlay is deliberately omitted; calibration metadata is provided and tested mathematically.
- No tracking, training, multi-user scheduling or annotation editor is included.

## Milestones

M1 and T03/T05's actual GPU/API behavior are verified. Full-scene export generation/download is verified. End-to-end web viewer acceptance and live CVAT import remain incomplete for the concrete access limitations above. Checklist items are marked by observed evidence, not by implementation intent.
