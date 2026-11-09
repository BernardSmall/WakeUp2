from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from backend.config import DetectionSettings


class MonitoringStatus(BaseModel):
    monitoring: bool
    status: str
    eye_status: str
    face_detected: bool
    ear_left: Optional[float] = None
    ear_right: Optional[float] = None
    ear_mean: Optional[float] = None
    closure_duration_seconds: float = 0.0
    consecutive_closed_frames: int = 0
    alert_count: int = 0
    latest_alert_id: int = 0
    latest_alert_at: Optional[datetime] = None
    camera_error: Optional[str] = None
    camera_notice: Optional[str] = None
    session_id: Optional[int] = None
    settings: DetectionSettings
    updated_at: datetime


class SessionRecord(BaseModel):
    id: int
    started_at: datetime
    ended_at: Optional[datetime]
    duration_seconds: float
    alert_count: int
    alert_timestamps: list[datetime]
    settings: DetectionSettings


class SessionHistory(BaseModel):
    sessions: list[SessionRecord]


class CameraDeviceInfo(BaseModel):
    camera_id: str
    name: str
    index: int


class CameraCatalog(BaseModel):
    cameras: list[CameraDeviceInfo]
    selected_camera_id: Optional[str] = None
    notice: Optional[str] = None
    error: Optional[str] = None


class CameraSelectionRequest(BaseModel):
    camera_id: str


class HealthResponse(BaseModel):
    status: str
    version: str
