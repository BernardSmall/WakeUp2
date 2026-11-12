from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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

FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if (FRONTEND_DIST / "index.html").is_file():
    assets = FRONTEND_DIST / "assets"
    if assets.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=assets),
            name="frontend-assets",
        )

    @app.get("/", include_in_schema=False)
    def frontend_index():
        return FileResponse(FRONTEND_DIST / "index.html")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend_route(path: str):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API endpoint not found.")

        requested = (FRONTEND_DIST / path).resolve()
        try:
            requested.relative_to(FRONTEND_DIST.resolve())
        except ValueError:
            return FileResponse(FRONTEND_DIST / "index.html")
        if requested.is_file():
            return FileResponse(requested)
        return FileResponse(FRONTEND_DIST / "index.html")
