"""Read every keyframe's LiDAR and camera headers without copying dataset data."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.config import Settings
from app.dataset import NuScenes, CAMERAS

s=Settings();d=NuScenes(s.dataset_root,s.nuscenes_version)
frames=0;cameras=0;points=0
for scene in d.frames.values():
    for frame in scene:
        token=frame['sample_token'];cloud=d.points(token);points+=len(cloud);frames+=1
        for channel in CAMERAS:
            with d.file(d.data[token][channel]).open('rb') as file:
                if file.read(2)!=b'\xff\xd8':raise ValueError(f'Invalid camera JPEG: {token}/{channel}')
            cameras+=1
print(json.dumps({'scenes':len(d.frames),'frames':frames,'camera_images':cameras,'lidar_points':points}))
