import json
import math
import sys
import time
import zipfile
from pathlib import Path
import numpy as np
import pytest
from fastapi.testclient import TestClient
from app.config import PROJECT, Settings, safe_path
from app.dataset import NuScenes, read_lidar, rotation, transform
from app.exporter import datumaro_item, pcd, write_export
from app.main import create_app
from app.schemas import Box, Prediction
from app.storage import Store, atomic_json, new_record


@pytest.fixture(scope='session')
def data():
    return NuScenes(PROJECT / 'v1.0-mini', 'v1.0-mini')


def test_real_dataset_order_binary_and_sweeps(data):
    assert len(data.frames) == 10
    assert sum(map(len, data.frames.values())) == 404
    for sensor in data.tables['calibrated_sensor'].values():
        if data.tables['sensor'][sensor['sensor_token']]['channel'] == 'LIDAR_TOP':
            basis=rotation(sensor['rotation'])
            assert np.dot(basis[:,0],[0,-1,0])>.95  # Raw X aligns ego right (-Y).
            assert np.dot(basis[:,1],[1,0,0])>.95   # Raw Y aligns ego forward (+X).
            assert np.dot(basis[:,2],[0,0,1])>.95   # Raw Z aligns ego up.
    scene = next(iter(data.frames))
    frames = data.frames[scene]
    assert all(b['timestamp_us'] > a['timestamp_us'] for a,b in zip(frames,frames[1:]))
    token = frames[1]['sample_token']
    cloud = data.points(token)
    assert cloud.shape[1] == 5 and len(cloud)>1000
    inputs = data.model_points(token)
    assert inputs.shape[1] == 5 and np.isfinite(inputs).all()
    assert len(inputs) > len(cloud)
    np.testing.assert_allclose(inputs[:len(cloud), :3], cloud[:, :3])
    assert np.all(inputs[:len(cloud), 4] == 0)
    assert np.all(inputs[len(cloud):, 4] > 0)
    prev = data.tables['sample_data'][data.data[token]['LIDAR_TOP']['prev']]
    raw = read_lidar(data.file(prev))
    T = np.linalg.inv(data.sensor_to_global(data.data[token]['LIDAR_TOP'])) @ data.sensor_to_global(prev)
    expected = (T @ np.append(raw[0,:3],1))[:3]
    np.testing.assert_allclose(inputs[len(cloud),:3],expected,atol=1e-5)


def test_transforms_and_yaw():
    for yaw in (0,math.pi/2,-math.pi/2,math.pi):
        pose={'rotation':[math.cos(yaw/2),0,0,math.sin(yaw/2)],'translation':[2,3,4]}
        T=transform(pose)
        np.testing.assert_allclose(np.linalg.inv(T)@T,np.eye(4),atol=1e-12)
        np.testing.assert_allclose(rotation(pose['rotation'])@[1,0,0],[math.cos(yaw),math.sin(yaw),0],atol=1e-12)
        box=Box(id='1',label='car',score=.8,center=[2,3,4],size_lwh=[4,2,1],yaw_rad=yaw)
        assert -math.pi <= box.yaw_rad < math.pi
    with pytest.raises(ValueError):
        Box(id='1',label='car',score=.8,center=[math.nan,0,0],size_lwh=[4,2,1],yaw_rad=0)
    with pytest.raises(ValueError):
        Box(id='1',label='car',score=.8,center=[0,0,0],size_lwh=[0,2,1],yaw_rad=0)


def test_windows_wsl_path_mapping():
    from app.wsl import to_wsl, to_windows
    if sys.platform != 'win32': pytest.skip('Windows mapping check')
    assert to_wsl(Path('D:/build-phase/nuscenes')) == '/mnt/d/build-phase/nuscenes'
    assert to_windows('/mnt/d/build-phase/nuscenes') == Path('D:/build-phase/nuscenes')
    with pytest.raises(ValueError):to_windows('/home/user/python')


def test_safe_paths_and_parser(tmp_path):
    with pytest.raises(ValueError): safe_path(tmp_path,'../escape')
    invalid=tmp_path/'invalid.bin';invalid.write_bytes(b'bad')
    with pytest.raises(ValueError):read_lidar(invalid)
    try:
        (tmp_path/'link').symlink_to(tmp_path.parent,target_is_directory=True)
    except OSError:
        return
    with pytest.raises(ValueError):safe_path(tmp_path,'link/escape')


def prediction(data, token, job='test'):
    frame=data.frame(token)
    return Prediction(job_id=job,scene_token=frame['scene_token'],sample_token=token,
        lidar_sample_data_token=frame['lidar_sample_data_token'],frame_index=frame['frame_index'],
        timestamp_us=frame['timestamp_us'],model={'name':'test-fixture-only','checkpoint_sha256':'0'*64},
        boxes=[Box(id='1',label='car',score=.8,center=[1,2,3],size_lwh=[4,2,1],yaw_rad=math.pi/2),
               Box(id='2',label='truck',score=.2,center=[0,0,0],size_lwh=[6,2,3],yaw_rad=0)]).model_dump(mode='json')


def test_export_subset_and_threshold(data,tmp_path):
    scene=next(iter(data.frames));tokens=[f['sample_token'] for f in data.frames[scene]][1:3]
    assert data.select(scene,tokens[::-1])==tokens
    with pytest.raises(ValueError):data.select(scene,[tokens[0],tokens[0]])
    request={'job_id':'test','sample_tokens':tokens,'threshold':.5,'classes':['car']}
    write_export(tmp_path,data,[prediction(data,t) for t in tokens],request,lambda n:None)
    with zipfile.ZipFile(tmp_path/'data.zip') as z:
        assert z.namelist()==['000000.pcd','000001.pcd']
        payload=z.read('000000.pcd');header,body=payload.split(b'DATA binary\n',1)
        assert b'FIELDS x y z' in header
        np.testing.assert_array_equal(np.frombuffer(body,dtype='<f4').reshape(-1,3),data.points(tokens[0])[:,:3])
    with zipfile.ZipFile(tmp_path/'annotations.zip') as z:
        doc=json.loads(z.read('annotations/default.json'))
        assert len(doc['items'][0]['annotations'])==1
        ann=doc['items'][0]['annotations'][0]
        assert ann['rotation']==[0,0,math.pi/2] and ann['scale']==[4,2,1]
        assert [i['id'] for i in doc['items']]==['000000','000001']
    manifest=json.loads((tmp_path/'manifest.json').read_text())
    assert manifest['mapping'][0]['scene_frame_index']==1


def test_api_real_frame_and_validation(data,tmp_path):
    s=Settings(runtime_root=tmp_path/'runtime',model_root=tmp_path/'models',
               inference_python='',inference_wsl_distro='',MODEL_CONFIG='',model_checkpoint='')
    with TestClient(create_app(s)) as client:
        assert client.get('/api/health').json()['dataset_available']
        scene=client.get('/api/scenes').json()['items'][0]['token']
        token=client.get(f'/api/scenes/{scene}/frames').json()[0]['sample_token']
        assert len(client.get(f'/api/frames/{token}').json()['cameras'])==6
        points=client.get(f'/api/frames/{token}/points')
        assert points.status_code==200
        assert len(points.content)==int(points.headers['X-Point-Count'])*12
        assert client.get(f'/api/frames/{token}/camera/CAM_FRONT').content[:2]==b'\xff\xd8'
        assert client.get(f'/api/frames/{token}/camera/nope').status_code==400
        assert client.get('/api/frames/unknown').status_code==404
        assert client.post('/api/jobs',json={'scene_token':scene,'sample_tokens':[token],'threshold':2}).status_code==422
        response=client.post('/api/jobs',json={'scene_token':scene,'sample_tokens':[token]})
        assert response.status_code==400 and 'MODEL_CHECKPOINT' in response.json()['detail']


def wait_status(client,id,status):
    for _ in range(100):
        record=client.get(f'/api/jobs/{id}').json()
        if record['status']==status:return record
        time.sleep(.05)
    pytest.fail(f'Expected {status}, got {record}')


def test_job_fail_cancel_retry_restart(data,tmp_path):
    # An ordinary interpreter + invalid model config intentionally triggers worker failure.
    config=tmp_path/'config.py';config.write_text('# test fixture')
    checkpoint=tmp_path/'checkpoint.pth';checkpoint.write_bytes(b'test fixture')
    s=Settings(runtime_root=tmp_path/'runtime',model_root=tmp_path/'models',
        inference_python=sys.executable,inference_wsl_distro='',MODEL_CONFIG=str(config),model_checkpoint=str(checkpoint))
    scene=next(iter(data.frames));token=data.frames[scene][0]['sample_token']
    request={'scene_token':scene,'sample_tokens':[token],'threshold':.3}
    with TestClient(create_app(s)) as client:
        wrong=client.post('/api/jobs',json={**request,'sample_tokens':['unknown']})
        assert wrong.status_code==400
        id=client.post('/api/jobs',json=request).json()['id']
        failed=wait_status(client,id,'failed');assert failed['error']
        retry=client.post(f'/api/jobs/{id}/retry').json();assert retry['id']!=id and retry['parent_job_id']==id
        cancelled=client.post(f'/api/jobs/{retry["id"]}/cancel').json();assert cancelled['status']=='cancelled'
        assert client.post(f'/api/jobs/{retry["id"]}/cancel').json()['status']=='cancelled'
        # Verify process-tree cancellation using a sleeping fixture worker (no mock model).
        import asyncio
        service=client.app.state.jobs
        running=new_record(request);running['status']='running';service.store.put(running)
        child_pid=tmp_path/'child.pid'
        async def start_sleep():
            code=('import subprocess,sys,time; from pathlib import Path; '
                  'p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"]); '
                  'Path(sys.argv[1]).write_text(str(p.pid)); time.sleep(60)')
            service.process=await asyncio.create_subprocess_exec(sys.executable,'-c',code,str(child_pid))
            service.active=running['id']
        client.portal.call(start_sleep)
        for _ in range(100):
            if child_pid.exists():break
            time.sleep(.02)
        assert child_pid.exists()
        pid=int(child_pid.read_text())
        assert client.post(f'/api/jobs/{running["id"]}/cancel').json()['status']=='cancelled'
        assert service.process.returncode is not None
        if sys.platform == 'win32':
            import ctypes
            handle=ctypes.windll.kernel32.OpenProcess(0x1000,False,pid)
            if handle:
                code=ctypes.c_ulong()
                ctypes.windll.kernel32.GetExitCodeProcess(handle,ctypes.byref(code))
                ctypes.windll.kernel32.CloseHandle(handle)
                assert code.value != 259, 'Worker child process survived cancellation'
        service.process=None;service.active=None
    store=Store(s.runtime_root);orphan=new_record(request);orphan['status']='running';store.put(orphan)
    with TestClient(create_app(s)) as client:
        assert client.get(f'/api/jobs/{orphan["id"]}').json()['status']=='failed'


def test_api_export_fixture_only(data,tmp_path):
    s=Settings(runtime_root=tmp_path/'runtime',model_root=tmp_path/'models',
               inference_python='',inference_wsl_distro='',MODEL_CONFIG='',model_checkpoint='')
    scene=next(iter(data.frames));token=data.frames[scene][0]['sample_token']
    with TestClient(create_app(s)) as client:
        record=new_record({'scene_token':scene,'sample_tokens':[token],'threshold':.3});record['status']='completed'
        client.app.state.store.put(record)
        atomic_json(s.runtime_root/'predictions'/record['id']/f'{token}.json',prediction(data,token,record['id']))
        export=client.post('/api/exports',json={'job_id':record['id'],'sample_tokens':[token],'classes':['car']})
        assert export.status_code==202
        id=export.json()['id']
        for _ in range(100):
            result=client.get(f'/api/exports/{id}').json()
            if result['status'] in ('completed','failed'):break
            time.sleep(.05)
        assert result['status']=='completed',result
        assert client.get(result['download_url']).content[:2]==b'PK'
