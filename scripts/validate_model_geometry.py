"""Validate actual MMDet3D bottom origin, dimension order and positive-Z yaw."""
import itertools
import json
import math
import numpy as np
import torch
from mmdet3d.structures import LiDARInstance3DBoxes


def ordered(points):
    keys=np.round(points,5)
    return points[np.lexsort((keys[:,2],keys[:,1],keys[:,0]))]


yaws=[0,math.pi/2,-math.pi/2,math.pi,.3]
for yaw in yaws:
    boxes=LiDARInstance3DBoxes(torch.tensor([[1.,2.,0.,4.,2.,2.,yaw]]))
    np.testing.assert_allclose(boxes.gravity_center.numpy(),[[1.,2.,1.]])
    np.testing.assert_allclose(boxes.dims.numpy(),[[4.,2.,2.]])
    local=np.array(list(itertools.product((-.5,.5),repeat=3))) * [4,2,2]
    c,s=math.cos(yaw),math.sin(yaw)
    rotation=np.array([[c,-s,0],[s,c,0],[0,0,1]])
    expected=local@rotation.T+[1,2,1]
    np.testing.assert_allclose(ordered(boxes.corners.numpy()[0]),ordered(expected),atol=1e-6)
print(json.dumps({'framework':'mmdet3d 1.4.0','bottom_to_geometric_center_verified':True,
    'size_lwh_verified':True,'positive_z_yaw_verified':True,'tested_yaws':yaws}))
