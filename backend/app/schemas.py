import math
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

LABELS = ['car', 'truck', 'trailer', 'bus', 'construction_vehicle', 'bicycle',
          'motorcycle', 'pedestrian', 'traffic_cone', 'barrier']


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Box(Strict):
    id: str
    label: str
    score: float = Field(ge=0, le=1)
    center: tuple[float, float, float]
    size_lwh: tuple[float, float, float]
    yaw_rad: float

    @field_validator('label')
    @classmethod
    def label_valid(cls, value):
        if value not in LABELS:
            raise ValueError('Unsupported nuScenes detection label')
        return value

    @field_validator('size_lwh')
    @classmethod
    def size_valid(cls, value):
        if any(v <= 0 for v in value):
            raise ValueError('Box dimensions must be positive')
        return value

    @field_validator('yaw_rad')
    @classmethod
    def yaw_valid(cls, value):
        return (value + math.pi) % (2 * math.pi) - math.pi


class ModelInfo(Strict):
    name: str
    checkpoint_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')


class Prediction(Strict):
    schema_version: Literal['1.0'] = '1.0'
    job_id: str
    scene_token: str
    sample_token: str
    lidar_sample_data_token: str
    frame_index: int = Field(ge=0)
    timestamp_us: int
    coordinate_frame: Literal['LIDAR_TOP'] = 'LIDAR_TOP'
    units: Literal['meters'] = 'meters'
    box_origin: Literal['geometric_center'] = 'geometric_center'
    axis_convention: Literal['x_right_y_forward_z_up'] = 'x_right_y_forward_z_up'
    model: ModelInfo
    boxes: list[Box]


class JobRequest(Strict):
    scene_token: str
    sample_tokens: list[str] = Field(min_length=1)
    model: Literal['pointpillars-nuscenes'] = 'pointpillars-nuscenes'
    threshold: float = Field(.3, ge=0, le=1)


class ExportRequest(Strict):
    job_id: str
    sample_tokens: list[str] = Field(min_length=1)
    threshold: float = Field(.3, ge=0, le=1)
    classes: list[str] = Field(default_factory=lambda: LABELS.copy())

    @field_validator('classes')
    @classmethod
    def classes_valid(cls, value):
        if not value or not set(value).issubset(LABELS):
            raise ValueError('Choose at least one supported class')
        return sorted(set(value))
