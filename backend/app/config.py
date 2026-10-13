from pathlib import Path
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT / 'backend/.env', extra='ignore')
    dataset_root: Path = PROJECT / 'v1.0-mini'
    nuscenes_version: str = 'v1.0-mini'
    runtime_root: Path = PROJECT / 'runtime'
    model_root: Path = PROJECT / 'models'
    api_host: str = '127.0.0.1'
    api_port: int = Field(8000, ge=1, le=65535)
    frontend_origin: str = 'http://localhost:5173'
    inference_python: str = ''
    inference_wsl_distro: str = ''
    model_config_path: str = Field('', validation_alias='MODEL_CONFIG')
    model_checkpoint: str = ''
    device: str = 'cuda:0'
    max_concurrent_jobs: int = Field(1, ge=1, le=1)
    default_score_threshold: float = Field(.3, ge=0, le=1)
    preview_max_points: int = Field(100000, ge=100, le=1000000)
    runtime_quota_gb: float = Field(10, gt=0)
    cvat_url: str = 'http://localhost:8080'

    @model_validator(mode='after')
    def paths(self):
        for name in ('dataset_root', 'runtime_root', 'model_root'):
            setattr(self, name, Path(getattr(self, name)).resolve())
        data = self.dataset_root
        for output in (self.runtime_root, self.model_root):
            if output == data or output.is_relative_to(data):
                raise ValueError('Runtime/model roots must be outside the dataset root')
        return self


def safe_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Path escapes allowed root')
    return path
