# Environment survey — 2026-10-12 (Asia/Saigon)

No existing application or AGENTS.md was found in the workspace. The task document was the only source file. All application source was created under the permitted workspace `D:/build-phase/nuscenes` instead of writing to its parent.

## Dataset

Actual root: `D:/build-phase/nuscenes/v1.0-mini`. The archive has an extra directory level: this root contains `samples/`, `sweeps/`, `maps/`, and metadata in `v1.0-mini/`. Metadata inspection/tests found 10 scenes and 404 samples. Adapter traverses `sample.next` and validates timestamps, sample membership, count, and last token.

## Windows API/frontend

- System `python` was not on PATH; `py --list-paths` reported no installations.
- uv 0.12.3 installed standalone CPython 3.11.15 inside `.python/`, then created `backend/.venv`.
- Node v24.19.0 and npm 11.17.0 available.
- API dependencies: `backend/requirements.txt`; exact installed transitive versions: `backend/requirements.lock.txt`.
- Frontend dependencies: `frontend/package-lock.json`. Vite 6.4.4 after correcting advisories reported by npm audit.
- Run scripts load `backend/.env` and Vite's `frontend/.env`; adjust API_PORT, FRONTEND_ORIGIN, VITE_API_BASE_URL and VITE_DEV_PORT together when changing ports.
- Backend env contains operational paths only. No tokens or passwords are required. `.env` files are ignored by Git.

## GPU / WSL

- NVIDIA RTX 4050 Laptop, 6141 MiB VRAM, Windows driver 610.47; nvidia-smi reported CUDA UMD 13.3. This is driver capability, not an installed CUDA toolkit version.
- Ubuntu WSL2 and docker-desktop WSL2 were stopped initially. WSL enumeration inside the restricted shell returned E_ACCESSDENIED; the approved unrestricted read succeeded.
- Ubuntu starts and exposes the GPU (WSL driver 610.43.02 / Windows KMD 610.47). Existing Python is 3.14.4, unsuitable for the selected old compiled wheel matrix; no pip/uv/nvcc found there.
- D: had about 43 GiB free before inference setup. Linux filesystem reported ample free space.
- Inference uses a separate Python 3.10 virtualenv on Ubuntu's native filesystem, `/home/msi/.local/share/nuscenes-prelabel/inference-env`. The failed `inference/.venv` on NTFS was cleaned up and is not the configured runtime. Setup defaults to the current Linux user's local data directory and uses official uv, PyTorch and OpenMMLab sources only.
- Linux dependency cache uses `/tmp/nuscenes-prelabel-uv-cache` and UV_LINK_MODE=copy. The initial `/mnt/d` cache failed an atomic rename while preparing PyTorch; the script now avoids that NTFS failure.
- Package installation on the mounted Windows virtualenv then stalled in a Plan9 filesystem RPC after copying PyTorch. Its installer was stopped and a native Linux virtualenv was used, avoiding that mount write bottleneck.
- Windows API + WSL worker is supported with INFERENCE_WSL_DISTRO=Ubuntu. `/mnt/<drive>/...` mapping is explicit, and submit probes read/write visibility between API and worker before launch. The worker records its Linux process group so cancel can terminate it.
- Alternatively run both API and worker in WSL and use native Linux paths with INFERENCE_WSL_DISTRO empty; install API requirements in its own Linux env.

## Troubleshooting

Missing dataset is reported in `/api/health`; API startup still works. Missing interpreter/config/checkpoint produces a specific 400 response before queueing a job. Worker stderr is retained locally and filtered in the returned error. Start only one API process: the local SQLite scheduler supports a single API instance and one GPU worker.

If WSL execution is denied by the development sandbox, use a normal Windows terminal with access to your existing Ubuntu distro. No WSL installation or OS configuration changes are performed by the scripts.
