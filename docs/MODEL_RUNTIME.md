# Model runtime

## Selected candidate

LiDAR-only PointPillars SECFPN, nuScenes, from **MMDetection3D v1.4.0**:

Config checkout commit: `fe25f7a51d36e3702f961e198894580d83c4387b` (v1.4.0 tag). Installed package mmdet3d==1.4.0. Exact successful runtime dependencies are saved in `inference/requirements.verified.txt`.

- [Official model zoo entry](https://github.com/open-mmlab/mmdetection3d/blob/v1.4.0/configs/pointpillars/README.md).
- [Config](https://github.com/open-mmlab/mmdetection3d/blob/v1.4.0/configs/pointpillars/pointpillars_hv_secfpn_sbn-all_8xb4-2x_nus-3d.py).
- [Checkpoint](https://download.openmmlab.com/mmdetection3d/v1.0.0_models/pointpillars/hv_pointpillars_secfpn_sbn-all_4x8_2x_nus-3d/hv_pointpillars_secfpn_sbn-all_4x8_2x_nus-3d_20210826_225857-f19d00a3.pth).
- Framework [Apache-2.0 license](https://github.com/open-mmlab/mmdetection3d/blob/v1.4.0/LICENSE). The model zoo does not state a separate checkpoint license in its table; dataset use remains subject to nuScenes terms. No broader checkpoint license claim is inferred.

PointPillars avoids sparse-convolution dependencies required by many voxel models. The upstream memory figure is for training and is not evidence that inference fits 6 GiB. Batch 1, eval/no_grad are used; VRAM/time are logged by the worker. Suitability is confirmed only after a real smoke run. No preprocessing or precision setting is silently changed on OOM.

Actual validation on this RTX 4050: first-frame smoke produced 18 boxes at threshold 0.3 with 573 MiB peak allocated VRAM. A complete 39-frame scene produced 1,412 boxes with ~1.934 GiB peak allocated VRAM, FP32/no_grad/batch 1 and the registered sweep preprocessing. This validates that scene on 6 GiB; it is not a benchmark for every possible nuScenes frame or machine.

## Separate Linux matrix

The setup script selects Python 3.10, torch 2.1.0/cu118, torchvision 0.16.0, mmcv 2.1.0 with compiled ops, mmengine 0.10.7, mmdet 3.3.0, mmdet3d 1.4.0, NumPy 1.26.4, and nuScenes devkit 1.1.11. See upstream [compatibility table](https://mmdetection3d.readthedocs.io/en/latest/notes/faq.html) and [MMCV installation](https://mmcv.readthedocs.io/en/latest/get_started/installation.html). The script requires a matching prebuilt MMCV wheel and stops rather than compiling CUDA code unexpectedly.

The default inference env is on Ubuntu's native filesystem (`$XDG_DATA_HOME/nuscenes-prelabel/inference-env`, or `~/.local/share/...`) because package installation on this machine's NTFS mount stalled. Dataset, source, model checkpoint and output stay in the Windows workspace. The backend probes the configured Linux interpreter using WSL rather than assuming Linux symlinks are readable from Windows.

Run setup explicitly:

```powershell
wsl -d Ubuntu -- bash /mnt/d/build-phase/nuscenes/scripts/setup_inference.sh
backend/.venv/Scripts/python.exe scripts/download_checkpoint.py
```

The download script validates source Content-Length, free space, actual size and SHA256 prefix from the official filename. Exact downloaded hash is stored in `models/checkpoint.json`. API startup never downloads or deserializes a model.

Downloaded checkpoint: 19,778,089 bytes; SHA256 `f19d00a38e6b775f38a45a9a3ca3ecaec20a5585a3caf44622423e2d5f75d5d0`. Official eight-digit hash prefix verified during this session.

For Windows API + WSL worker, set in `backend/.env` after setup succeeds:

```dotenv
INFERENCE_WSL_DISTRO=Ubuntu
INFERENCE_PYTHON=/home/msi/.local/share/nuscenes-prelabel/inference-env/bin/python
MODEL_CONFIG=D:/build-phase/nuscenes/inference/vendor/mmdetection3d/configs/pointpillars/pointpillars_hv_secfpn_sbn-all_8xb4-2x_nus-3d.py
MODEL_CHECKPOINT=D:/build-phase/nuscenes/models/pointpillars-nuscenes.pth
DEVICE=cuda:0
```

Restart the API after changes. The full upstream checkout is required for config inheritance; copying the single config file is insufficient. Worker imports the installed package, not the checkout, and validates the registered sweep settings before model initialization. Up to 10 previous sweeps are transformed to current LiDAR; see COORDINATES.md.

Run one frame using `scripts/smoke_pipeline.py`. A missing runtime/checkpoint is a failure, never a mock fallback. Logs include checkpoint hash, PyTorch/CUDA, elapsed seconds and peak VRAM. Exact runtime result and limitations are recorded in VALIDATION.md. `inference/requirements.verified.txt` is generated only after runtime import/GPU checks succeed.
