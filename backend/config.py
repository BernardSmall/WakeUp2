from pathlib import Path

from typing import Optional

from pydantic import BaseModel, Field

from settings import CAM_INDEX, DRAW_OVERLAY, EAR_THRESHOLD


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data-local"
DATABASE_PATH = DATA_DIR / "wakeup2.sqlite3"
SETTINGS_PATH = DATA_DIR / "settings.json"


class DetectionSettings(BaseModel):
    ear_threshold: float = Field(default=EAR_THRESHOLD, ge=0.1, le=0.4)
    closed_duration_seconds: float = Field(default=1.5, ge=0.3, le=10.0)
    camera_index: int = Field(default=CAM_INDEX, ge=0)
    camera_id: Optional[str] = None
    show_landmarks: bool = DRAW_OVERLAY
    audio_enabled: bool = True
    audio_volume: float = Field(default=0.5, ge=0.0, le=1.0)
