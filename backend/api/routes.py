import asyncio

from fastapi import APIRouter, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from backend.config import DetectionSettings
from backend.models import (
    CameraCatalog,
    CameraSelectionRequest,
    HealthResponse,
    MonitoringStatus,
    SessionHistory,
    SessionRecord,
)


router = APIRouter(prefix="/api")
websocket_router = APIRouter()


def _manager(request: Request):
    return request.app.state.camera_manager


@router.get("/health", response_model=HealthResponse)
def health():
    return {"status": "ok", "version": "1.0.0"}


@router.get("/status", response_model=MonitoringStatus)
def status(request: Request):
    return _manager(request).snapshot()


@router.post("/monitoring/start", response_model=MonitoringStatus)
async def start_monitoring(request: Request):
    manager = _manager(request)
    if manager.snapshot()["status"] == "CAMERA_ERROR":
        await asyncio.to_thread(manager.stop)
    return await asyncio.to_thread(manager.start)


@router.post("/monitoring/stop", response_model=MonitoringStatus)
async def stop_monitoring(request: Request):
    return await asyncio.to_thread(_manager(request).stop)


@router.get("/settings", response_model=DetectionSettings)
def get_settings(request: Request):
    return _manager(request).settings_service.get()


@router.put("/settings", response_model=DetectionSettings)
def update_settings(settings: DetectionSettings, request: Request):
    try:
        return _manager(request).update_settings(settings)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/cameras", response_model=CameraCatalog)
def get_cameras(request: Request):
    return _manager(request).cameras()


@router.post("/cameras/select", response_model=CameraCatalog)
async def select_camera(selection: CameraSelectionRequest, request: Request):
    try:
        return await asyncio.to_thread(
            _manager(request).select_camera, selection.camera_id
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/sessions", response_model=SessionHistory)
def get_sessions(request: Request, limit: int = Query(default=100, ge=1, le=500)):
    return {"sessions": request.app.state.session_service.list_sessions(limit)}


@router.get("/sessions/{session_id}", response_model=SessionRecord)
def get_session(session_id: int, request: Request):
    session = request.app.state.session_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Monitoring session not found.")
    return session


@router.delete("/sessions")
def clear_sessions(request: Request, confirm: bool = Query(default=False)):
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Set confirm=true to permanently clear local session history.",
        )
    request.app.state.session_service.clear()
    return {"cleared": True}


@router.get("/video")
async def video(request: Request):
    manager = _manager(request)
    if not manager.snapshot()["monitoring"]:
        raise HTTPException(status_code=409, detail="Start monitoring to view the camera.")

    async def stream():
        last_frame = None
        while manager.snapshot()["monitoring"]:
            frame = manager.latest_frame()
            if frame is not None and frame is not last_frame:
                last_frame = frame
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            await asyncio.sleep(1 / 15)

    return StreamingResponse(
        stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store"},
    )


@websocket_router.websocket("/ws/monitoring")
async def monitoring_websocket(websocket: WebSocket):
    await websocket.accept()
    manager = websocket.app.state.camera_manager
    try:
        while True:
            await websocket.send_json(
                MonitoringStatus(**manager.snapshot()).model_dump(mode="json")
            )
            await asyncio.sleep(0.2)
    except WebSocketDisconnect:
        return
