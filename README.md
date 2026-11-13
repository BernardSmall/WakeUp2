# WakeUp2

WakeUp2 is a local eye-closure monitoring application for Windows and macOS. Its Python backend owns the webcam, runs MediaPipe Face Mesh, calculates the original six-point Eye Aspect Ratio (EAR), and serves the React dashboard and processed frames from one local server. Video is not uploaded or saved.

> **Safety:** WakeUp2 is experimental computer-vision software, not a certified or medically validated safety device. It is not suitable for safety-critical driver monitoring and must not replace proper rest.

## Features

- Live webcam preview with eye contours and locally drawn EAR overlay
- Real-time eye status, left/right/mean EAR, closure duration, and session alert count
- Time-based closure threshold and one alert per continuous closure event
- Browser-generated audio alerts with enable, volume, and test controls
- macOS camera discovery using AVFoundation names and stable identifiers
- Windows camera discovery using DirectShow names; OpenCV capture prefers DirectShow and falls back to Media Foundation
- Camera switching while monitoring, with resource cleanup and rollback on failure
- EAR trend chart, local monitoring history, settings, and responsive light/dark themes
- Local SQLite session persistence; raw webcam footage is not stored

## Quick Start

Download and extract the GitHub ZIP, then use the setup and launch scripts in the extracted folder.

### Windows 10/11 (x64)

1. Run `setup-windows.bat`. It checks prerequisites and asks before using `winget` to install missing Python or Node.js.
2. Run `start-windows.bat`. WakeUp2 opens in your default browser when ready.
3. Keep the launcher window open; press Ctrl+C in it to stop WakeUp2.

The batch wrappers use PowerShell execution-policy bypass only in the child PowerShell process; they do not change machine or user policy.

### macOS

- Apple Silicon: macOS 11 or later
- Intel: macOS 12 or later

1. Run `setup-macos.command`. If you choose the Homebrew option, it asks before installing missing Python or Node.js packages.
2. Run `start-macos.command`. WakeUp2 opens in your default browser when ready.
3. Keep the Terminal window open; press Control-C to stop WakeUp2.

If macOS will not open a downloaded command script, use Terminal in the extracted folder and run `bash ./setup-macos.command`. Do not remove quarantine attributes or disable Gatekeeper.

Setup creates a local virtual environment, installs pinned Python dependencies, runs `npm ci`, builds the frontend, and validates the app. It can be rerun and does not delete or replace an existing virtual environment or local settings.

## Supported versions and dependencies

- Windows 10/11 x64
- macOS 11+ on Apple Silicon; macOS 12+ on Intel
- Python 3.10, 3.11, or 3.12
- Node.js 22.12+ or 24.x with npm (needed only for setup/build; normal launch does not need Node.js)
- Webcam and operating-system camera permission

Python versions are pinned in `requirements.txt`; the React dependency graph is pinned by `frontend/package-lock.json`. Runtime dependencies include FastAPI 0.115.12, Uvicorn 0.34.0, MediaPipe 0.10.21, OpenCV contrib 4.10.0.84, and NumPy 1.26.4. PyObjC/AVFoundation bindings are installed only on macOS; PyGrabber and COMTypes are installed only on Windows. The OpenCV 4.10 wheels support Windows x64, Apple Silicon macOS 11+, and Intel macOS 12+.

MediaPipe 0.10.21 is pinned because it supports the project's existing `mp.solutions.face_mesh` API; MediaPipe 1.2.x does not. Only one OpenCV Python package is installed to avoid conflicting distributions.

## Camera discovery and identity

On macOS, AVFoundation provides actual device names and stable device identifiers without opening cameras to refresh the list. OpenCV captures the current AVFoundation enumeration index, which WakeUp2 resolves again from the saved ID at startup.

On Windows, DirectShow provides camera names and enumeration indices. WakeUp2 uses the name (and an ordinal for duplicate names) as the saved identifier because this path does not provide a stable persistent device ID. Names/order can change after reconnects; WakeUp2 refreshes the list and resolves the selected name at startup. DirectShow is preferred for capture; Media Foundation is attempted if DirectShow cannot open a usable stream.

Select or refresh the camera from **Settings → Camera**. When monitoring is active, WakeUp2 stops and releases the current capture before opening and verifying the replacement. Failed switches attempt to restore the previous camera.

## Run and development

The launch scripts run one FastAPI server bound to `127.0.0.1:8000`. It serves the production React build, HTTP API, MJPEG stream, and WebSocket endpoint. Camera video is not exposed over the local network. If port 8000 belongs to another application, WakeUp2 reports the conflict and will not terminate that process. If WakeUp2 is already running, the launcher opens the existing app instead of starting another server.

For development, start Vite (`cd frontend && npm run dev`) and FastAPI in separate terminals:

```bash
# macOS, from the repository root
venv/bin/python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

```powershell
# Windows, from the repository root
.\venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

The Vite development server proxies API and WebSocket traffic to FastAPI. `npm run build` updates the production bundle served by FastAPI.

## Manual installation

Python and Node.js should be installed from their official download pages or reputable package managers. The setup scripts never install system software without explicit consent.

```bash
# macOS (choose an installed supported version)
python3.11 -m venv venv
venv/bin/python -m pip install --upgrade pip
venv/bin/python -m pip install -r requirements.txt
cd frontend && npm ci && npm run build
```

```powershell
# Windows
py -3.11 -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt
cd frontend
npm ci
npm run build
```

## Detection and settings

| Setting | Default | Description |
| --- | ---: | --- |
| EAR threshold | `0.20` | Mean EAR below the threshold is considered closed. |
| Eye-closure alert duration | `1.5 s` | Continuous closed-eye duration before a drowsiness alert. |
| Camera device | First available camera, unless a saved device is available | Choose a detected camera by name. A selection is saved locally and can be changed while monitoring. |
| Landmark overlay | On | Draw eye contours on the streamed frame. |
| Browser audio alerts | On | Play a browser-generated tone after the user starts monitoring. |
| Alert volume | `50%` | Relative Web Audio gain level. |

Closure timing uses a monotonic clock, so the alert threshold is time-based rather than tied to camera frame rate. Missing face/landmark measurements do not count as closure and reset the continuous event. A new alert can occur after the eyes reopen and a new closure reaches the threshold.

To try the detector, start monitoring in a well-lit room, center your face, observe the live EAR and eye state, then close your eyes briefly and reopen them. Face pose, camera placement, lighting, and individual features affect accuracy.

## Tests and CI

```bash
# Python backend and mocked camera/platform tests
python -m unittest discover -s tests -v

# Frontend TypeScript check and production build
cd frontend
npm ci
npm run build
```

GitHub Actions runs dependency installation, backend tests, static-serving checks, and frontend builds on Windows and macOS. Automated camera tests use mocks; a green CI job does not prove that every physical webcam works.

## Local data, privacy, and permissions

Session summaries, alert timestamps, and settings are stored under the ignored `data-local/` directory. The application does not persist webcam frames, upload video, or call cloud services. Logs contain server diagnostics only. Both frontend and backend bind to loopback addresses.

On first use, grant camera permission to the terminal or app hosting the backend:

- macOS: **System Settings → Privacy & Security → Camera**
- Windows: **Settings → Privacy & security → Camera**

`python camera_check.py` can help diagnose OpenCV camera access.

## Repair and update

- **Repair setup:** rerun `setup-windows.bat` or `setup-macos.command`. Existing `venv` and `data-local` settings are not deleted. If the existing virtual environment uses an unsupported Python or is incomplete, back it up and rename it yourself before rerunning setup.
- **Update a ZIP installation:** download and extract a fresh ZIP, then copy `data-local/settings.json` and any other data you want to preserve. Run setup in the new folder. Do not copy the old `venv` or `frontend/node_modules`.
- **Change cameras:** open Settings, choose a detected device, and refresh after connecting/disconnecting hardware.
- **Stop:** press Ctrl+C in the Windows launcher window or Control-C in the macOS Terminal window.

## Troubleshooting

- **`mp.solutions` or Face Mesh is missing:** rerun setup; the project requires MediaPipe 0.10.21 in its isolated environment.
- **OpenCV import errors/conflicts:** rerun setup so only the pinned `opencv-contrib-python` distribution is installed inside `venv`.
- **Camera list is empty:** check OS camera permissions, connect the device, then refresh. On Windows, ensure the device appears in the DirectShow device list; on macOS, ensure it appears in AVFoundation.
- **Camera unavailable:** close other apps using the camera and select an available device in Settings. Device names/indices can change after reconnecting.
- **Dashboard says backend reconnecting:** ensure the local server is running at `127.0.0.1:8000`.
- **Port 8000 is occupied:** close the application that owns it or use that app's shutdown control. WakeUp2 does not terminate unrelated processes.
- **No face or tracking lost:** improve lighting, face the camera, and avoid obscuring the eye area.
- **No audio:** click Start Monitoring or Test Audio to satisfy browser audio activation; check browser and OS output/mute settings.
- **macOS blocks a downloaded script:** run it from Terminal as `bash ./setup-macos.command`; do not disable Gatekeeper or remove quarantine metadata.
- **Windows prerequisite installer is unavailable:** install supported Python and Node.js from [python.org](https://www.python.org/downloads/windows/) and [nodejs.org](https://nodejs.org/en/download), then rerun setup.

## Project layout

- `backend/` — FastAPI API, platform camera discovery/capture, detection, settings, and history
- `frontend/` — React dashboard, chart, API/WebSocket client, and styles
- `scripts/` — prerequisite checks and Windows launch helper
- `tests/` — Python regression, camera, setup-check, and static-serving tests
- `setup-*.command`, `setup-windows.*`, `start-*.command`, `start-windows.bat` — setup and launch entry points
- `requirements.txt` — pinned Python runtime dependencies with OS markers
- `frontend/package-lock.json` — pinned frontend dependency graph
