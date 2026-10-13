"""Real GPU scene + export + WSL cancel checks against a running local API."""
import json
import argparse
import subprocess
import sys
import time
from pathlib import Path
import httpx

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'backend'))
from app.config import Settings

s = Settings()
parser = argparse.ArgumentParser()
parser.add_argument('--frames', type=int, help='Limit the completed inference/export check; cancellation still uses a full scene')
args = parser.parse_args()
if args.frames is not None and args.frames <= 0:
    parser.error('--frames must be positive')
client = httpx.Client(base_url=f'http://127.0.0.1:{s.api_port}', timeout=60)
def get(path):
    response=client.get(path);response.raise_for_status();return response.json()
def post(path,payload=None):
    response=client.post(path,json=payload);response.raise_for_status();return response.json()

health=get('/api/health')
assert health['model']['available'], health
scene=get('/api/scenes')['items'][0]
tokens=[f['sample_token'] for f in get(f'/api/scenes/{scene["token"]}/frames')]
all_tokens=tokens.copy()
if args.frames is not None:
    tokens=tokens[:args.frames]
job=post('/api/jobs',{'scene_token':scene['token'],'sample_tokens':tokens,'threshold':.3})
id=job['id'];observed=[];started=time.monotonic()
while True:
    record=get(f'/api/jobs/{id}')
    observed.append(record['status'])
    assert get('/api/health')['status']=='ok'
    print(json.dumps({'job':id,'status':record['status'],'processed':record['processed'],'total':record['total']}),flush=True)
    if record['status'] in ('completed','failed','cancelled'):break
    if time.monotonic()-started>900:
        post(f'/api/jobs/{id}/cancel');raise RuntimeError('Scene job timed out')
    time.sleep(1)
assert record['status']=='completed',record
predictions=[get(f'/api/jobs/{id}/predictions/{token}') for token in tokens]
assert len(predictions)==len(tokens)
boxes=sum(len(p['boxes']) for p in predictions)
export=post('/api/exports',{'job_id':id,'sample_tokens':tokens,'threshold':.3,
    'classes':['car','truck','trailer','bus','construction_vehicle','bicycle','motorcycle','pedestrian','traffic_cone','barrier']})
eid=export['id'];deadline=time.monotonic()+300
while True:
    result=get(f'/api/exports/{eid}')
    if result['status'] in ('completed','failed'):break
    if time.monotonic()>deadline:raise RuntimeError('Export timed out')
    time.sleep(.5)
assert result['status']=='completed',result
download=client.get(result['download_url']);download.raise_for_status();assert download.content[:2]==b'PK'

cancelled=post('/api/jobs',{'scene_token':scene['token'],'sample_tokens':all_tokens,'threshold':.3})
cid=cancelled['id'];pid_path=s.runtime_root/'jobs'/cid/'worker.pid';deadline=time.monotonic()+120
while not pid_path.exists() or get(f'/api/jobs/{cid}')['processed'] < 1:
    if time.monotonic()>deadline:raise RuntimeError('Cancellation worker did not start')
    time.sleep(.1)
pid=int(pid_path.read_text())
cancelled=post(f'/api/jobs/{cid}/cancel');assert cancelled['status']=='cancelled'
time.sleep(.5)
probe=subprocess.run(['wsl.exe','-d',s.inference_wsl_distro,'--','/bin/kill','-0','--',f'-{pid}'],capture_output=True)
assert probe.returncode != 0, 'Linux worker process group survived cancellation'
retained=list((s.runtime_root/'predictions'/cid).glob('*.json'))
assert retained, 'Completed predictions were not retained on cancel'
for file in retained:
    assert get(f'/api/jobs/{cid}/predictions/{file.stem}')['sample_token'] == file.stem
time.sleep(.5)
assert len(retained)==len(list((s.runtime_root/'predictions'/cid).glob('*.json'))), 'Outputs changed after cancellation returned'
summary={'scene_token':scene['token'],'job_id':id,'frames':len(tokens),'boxes':boxes,
    'status':record['status'],'observed_states':sorted(set(observed)),'job_elapsed':record['elapsed'],
    'export_id':eid,'download_bytes':len(download.content),'cancel_job_id':cid,'linux_process_group_cancel_verified':True,
    'retained_completed_predictions':len(retained),
    'runtime_verified':get('/api/health')['model']['runtime_verified'],'live_cvat_import_verified':False}
output=s.runtime_root/(f'live_validation_{len(tokens)}frames.json' if args.frames is not None else 'live_validation.json')
output.write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary),flush=True)
