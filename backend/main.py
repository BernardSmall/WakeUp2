from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router, websocket_router
from backend.detection.camera_manager import CameraManager
from backend.services.session_service import SessionService
from backend.services.settings_service import SettingsService


@asynccontextmanager
async def lifespan(application: FastAPI):
    settings_service = SettingsService()
    session_service = SessionService()
    camera_manager = CameraManager(settings_service, session_service)
    application.state.settings_service = settings_service
    application.state.session_service = session_service
    application.state.camera_manager = camera_manager
    yield
    camera_manager.stop()


app = FastAPI(title="WakeUp2 local monitoring API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)
app.include_router(router)
app.include_router(websocket_router)
