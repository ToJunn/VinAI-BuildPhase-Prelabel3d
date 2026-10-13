#!/usr/bin/env bash
set -euo pipefail
PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT"
mkdir -p .tools
export UV_PYTHON_INSTALL_DIR="$PROJECT/.python-linux"
export UV_CACHE_DIR="/tmp/nuscenes-prelabel-uv-cache"
export UV_LINK_MODE=copy
export UV_HTTP_TIMEOUT=60
if [[ ! -x "$PROJECT/.tools/uv-x86_64-unknown-linux-gnu/uv" ]]; then
  curl --fail --location --retry 2 https://github.com/astral-sh/uv/releases/download/0.12.3/uv-x86_64-unknown-linux-gnu.tar.gz -o .tools/uv-linux.tar.gz
  tar -xzf .tools/uv-linux.tar.gz -C .tools
fi
UV="$PROJECT/.tools/uv-x86_64-unknown-linux-gnu/uv"
"$UV" python install 3.10 --no-bin --mirror https://github.com/astral-sh/python-build-standalone/releases/download
INFERENCE_ENV_DIR="${1:-${XDG_DATA_HOME:-$HOME/.local/share}/nuscenes-prelabel/inference-env}"
if [[ ! -x "$INFERENCE_ENV_DIR/bin/python" ]]; then
  "$UV" venv "$INFERENCE_ENV_DIR" --python 3.10
fi
PYTHON="$INFERENCE_ENV_DIR/bin/python"
"$UV" pip install --python "$PYTHON" torch==2.1.0 torchvision==0.16.0 --index-url https://download.pytorch.org/whl/cu118
# Require a prebuilt wheel: do not silently compile a CUDA extension.
"$UV" pip install --python "$PYTHON" --only-binary mmcv mmcv==2.1.0 -f https://download.openmmlab.com/mmcv/dist/cu118/torch2.1/index.html
"$UV" pip install --python "$PYTHON" -r inference/requirements.txt
if [[ ! -d inference/vendor/mmdetection3d ]]; then
  git clone --depth 1 --branch v1.4.0 https://github.com/open-mmlab/mmdetection3d.git inference/vendor/mmdetection3d
fi
"$PYTHON" -c 'import torch; from mmcv.ops import nms; from mmdet3d.apis import init_model; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))'
"$UV" pip freeze --python "$PYTHON" > inference/requirements.verified.txt
echo 'Runtime dependencies installed. Run scripts/download_checkpoint.py next, then smoke_pipeline.py.'
