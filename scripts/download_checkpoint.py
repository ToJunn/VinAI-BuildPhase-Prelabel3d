"""Explicit download only; never executed at API startup."""
import hashlib
import json
import shutil
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
URL=('https://download.openmmlab.com/mmdetection3d/v1.0.0_models/pointpillars/'
     'hv_pointpillars_secfpn_sbn-all_4x8_2x_nus-3d/'
     'hv_pointpillars_secfpn_sbn-all_4x8_2x_nus-3d_20210826_225857-f19d00a3.pth')
target=ROOT/'models/pointpillars-nuscenes.pth'
target.parent.mkdir(exist_ok=True)
with urllib.request.urlopen(urllib.request.Request(URL,method='HEAD'),timeout=30) as response:
    size=int(response.headers.get('Content-Length',0))
if not 0<size<1024**3:
    raise RuntimeError(f'Unexpected checkpoint size: {size}; review before download')
if shutil.disk_usage(target.parent).free < size*2:
    raise RuntimeError('Insufficient free disk space')
if not target.exists():
    temp=target.with_suffix('.download')
    urllib.request.urlretrieve(URL,temp)
    if temp.stat().st_size != size: raise RuntimeError('Download size mismatch')
    temp.replace(target)
with target.open('rb') as file: digest=hashlib.file_digest(file,'sha256') if hasattr(hashlib,'file_digest') else None
if digest is None:
    digest=hashlib.sha256()
    with target.open('rb') as file:
        for chunk in iter(lambda:file.read(1024**2),b''):digest.update(chunk)
checksum=digest.hexdigest()
# Official filename embeds the first eight SHA256 hex digits.
if not checksum.startswith('f19d00a3'):raise RuntimeError(f'Checkpoint checksum mismatch: {checksum}')
manifest={'source_url':URL,'size_bytes':size,'sha256':checksum}
(target.parent/'checkpoint.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps(manifest))
